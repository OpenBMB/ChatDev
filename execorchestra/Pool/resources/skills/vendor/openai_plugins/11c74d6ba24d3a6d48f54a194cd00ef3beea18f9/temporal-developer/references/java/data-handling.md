# Java SDK Data Handling

## Overview

The Java SDK uses data converters to serialize/deserialize workflow inputs, outputs, and activity parameters. The `DataConverter` interface controls how values are converted to and from Temporal `Payload` protobufs.

## Default Data Converter

`DefaultDataConverter` applies converters in order, using the first that accepts the value:

1. `NullPayloadConverter` — `null` values
2. `ByteArrayPayloadConverter` — `byte[]` as raw binary
3. `ProtobufJsonPayloadConverter` — Protobuf `Message` instances as JSON
4. `ProtobufPayloadConverter` — Protobuf `Message` instances as binary
5. `JacksonJsonPayloadConverter` — Everything else via Jackson `ObjectMapper`

## Jackson Integration

Use `JacksonJsonPayloadConverter` with a custom `ObjectMapper` for advanced serialization (e.g., Java 8 time module, custom serializers):

```java
ObjectMapper mapper = new ObjectMapper()
    .registerModule(new JavaTimeModule())
    .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

DefaultDataConverter converter = DefaultDataConverter.newDefaultInstance()
    .withPayloadConverterOverrides(
        new JacksonJsonPayloadConverter(mapper)
    );

WorkflowServiceStubs service = WorkflowServiceStubs.newLocalServiceStubs();
WorkflowClient client = WorkflowClient.newInstance(
    service,
    WorkflowClientOptions.newBuilder()
        .setDataConverter(converter)
        .build()
);
```

## Custom Data Converter

Implement `PayloadConverter` for custom serialization:

```java
public class MyCustomPayloadConverter implements PayloadConverter {
    @Override
    public String getEncodingType() {
        return "json/my-custom";
    }

    @Override
    public Optional<Payload> toData(Object value) throws DataConverterException {
        // Return Optional.empty() if this converter doesn't handle the type
        if (!(value instanceof MyCustomType)) {
            return Optional.empty();
        }
        // Serialize to Payload
        byte[] data = serialize(value);
        return Optional.of(
            Payload.newBuilder()
                .putMetadata("encoding", ByteString.copyFromUtf8(getEncodingType()))
                .setData(ByteString.copyFrom(data))
                .build()
        );
    }

    @Override
    public <T> T fromData(Payload content, Class<T> valueClass, Type valueType)
        throws DataConverterException {
        // Deserialize from Payload
        return deserialize(content.getData().toByteArray(), valueClass);
    }
}
```

Override specific converters in the default chain:

```java
DefaultDataConverter converter = DefaultDataConverter.newDefaultInstance()
    .withPayloadConverterOverrides(new MyCustomPayloadConverter());
```

## Composition of Payload Converters

`DefaultDataConverter` holds a list of `PayloadConverter` instances tried in order. The first converter whose `toData()` returns a non-empty `Optional` wins. When using `withPayloadConverterOverrides()`, converters with matching encoding types replace existing ones.

```java
DefaultDataConverter converter = DefaultDataConverter.newDefaultInstance()
    .withPayloadConverterOverrides(
        new MyCustomPayloadConverter(),       // encoding: "json/my-custom"
        new JacksonJsonPayloadConverter(mapper) // replaces default Jackson converter
    );
```

## Protobuf Support

Protobuf messages are handled by `ProtobufJsonPayloadConverter` (enabled by default). It serializes `com.google.protobuf.Message` instances as JSON for human readability in the Temporal UI.

```java
// Protobuf messages work out of the box as workflow/activity params
@WorkflowInterface
public interface MyWorkflow {
    @WorkflowMethod
    MyProtoResult run(MyProtoInput input);
}
```

For binary protobuf encoding instead of JSON, use `ProtobufPayloadConverter`:

```java
DefaultDataConverter converter = DefaultDataConverter.newDefaultInstance()
    .withPayloadConverterOverrides(new ProtobufPayloadConverter());
```

## Payload Encryption

Use `PayloadCodec` with `CodecDataConverter` to encrypt/compress payloads:

```java
public class EncryptionCodec implements PayloadCodec {
    private final SecretKey key;

    public EncryptionCodec(SecretKey key) {
        this.key = key;
    }

    @Override
    public List<Payload> encode(List<Payload> payloads) {
        return payloads.stream().map(payload -> {
            // Encrypt payload.toByteArray() using your chosen algorithm (e.g., AES/GCM)
            byte[] encrypted = encryptBytes(payload.toByteArray(), key);
            return Payload.newBuilder()
                .putMetadata("encoding", ByteString.copyFromUtf8("binary/encrypted"))
                .setData(ByteString.copyFrom(encrypted))
                .build();
        }).collect(Collectors.toList());
    }

    @Override
    public List<Payload> decode(List<Payload> payloads) {
        return payloads.stream().map(payload -> {
            String encoding = payload.getMetadataOrDefault(
                "encoding", ByteString.EMPTY).toStringUtf8();
            if (!"binary/encrypted".equals(encoding)) return payload;
            // Decrypt and reconstruct the original Payload
            byte[] decrypted = decryptBytes(payload.getData().toByteArray(), key);
            return Payload.parseFrom(decrypted);
        }).collect(Collectors.toList());
    }
}
```

Apply the codec to the client:

```java
CodecDataConverter codecDataConverter = new CodecDataConverter(
    DefaultDataConverter.newDefaultInstance(),
    Collections.singletonList(new EncryptionCodec(secretKey))
);

WorkflowClient client = WorkflowClient.newInstance(
    service,
    WorkflowClientOptions.newBuilder()
        .setDataConverter(codecDataConverter)
        .build()
);
```

## Search Attributes

Custom searchable fields for workflow visibility.

```java
import io.temporal.common.SearchAttributeKey;
import io.temporal.common.SearchAttributes;

// Define typed search attribute keys
static final SearchAttributeKey<String> ORDER_ID =
    SearchAttributeKey.forKeyword("OrderId");
static final SearchAttributeKey<String> ORDER_STATUS =
    SearchAttributeKey.forKeyword("OrderStatus");
static final SearchAttributeKey<Double> ORDER_TOTAL =
    SearchAttributeKey.forDouble("OrderTotal");
static final SearchAttributeKey<OffsetDateTime> CREATED_AT =
    SearchAttributeKey.forOffsetDateTime("CreatedAt");

// Set at workflow start
WorkflowOptions options = WorkflowOptions.newBuilder()
    .setWorkflowId("order-" + orderId)
    .setTaskQueue("orders")
    .setTypedSearchAttributes(
        SearchAttributes.newBuilder()
            .set(ORDER_ID, orderId)
            .set(ORDER_STATUS, "pending")
            .set(ORDER_TOTAL, 99.99)
            .set(CREATED_AT, OffsetDateTime.now())
            .build()
    )
    .build();
```

Upsert during workflow execution:

```java
@WorkflowInterface
public interface OrderWorkflow {
    @WorkflowMethod
    String run(Order order);
}

public class OrderWorkflowImpl implements OrderWorkflow {
    static final SearchAttributeKey<String> ORDER_STATUS =
        SearchAttributeKey.forKeyword("OrderStatus");

    @Override
    public String run(Order order) {
        // ... process order ...

        Workflow.upsertTypedSearchAttributes(
            ORDER_STATUS.valueSet("completed")
        );
        return "done";
    }
}
```

### Querying Workflows by Search Attributes

```java
ListWorkflowExecutionsRequest request = ListWorkflowExecutionsRequest.newBuilder()
    .setNamespace("default")
    .setQuery("OrderStatus = 'processing' OR OrderStatus = 'pending'")
    .build();
```

## Workflow Memo

Store arbitrary metadata with workflows (not searchable).

```java
// Set memo at workflow start
WorkflowOptions options = WorkflowOptions.newBuilder()
    .setWorkflowId("order-" + orderId)
    .setTaskQueue("orders")
    .setMemo(Map.of(
        "customer_name", order.getCustomerName(),
        "notes", "Priority customer"
    ))
    .build();
```

```java
// Read memo from workflow
@Override
public String run(Order order) {
    String notes = Workflow.getMemo("notes", String.class);
    // ...
}
```

## Deterministic APIs for Values

Use these APIs within workflows for deterministic values:

```java
@Override
public String run() {
    // Deterministic UUID (same on replay)
    String uniqueId = Workflow.randomUUID().toString();

    // Deterministic random (same on replay)
    Random rng = Workflow.newRandom();
    int value = rng.nextInt(100);

    // Deterministic current time (same on replay)
    long now = Workflow.currentTimeMillis();

    return uniqueId;
}
```

## Best Practices

1. Use Jackson `ObjectMapper` customization for complex serialization needs
2. Keep payloads small — see `references/core/gotchas.md` for limits
3. Encrypt sensitive data with `PayloadCodec` and `CodecDataConverter`
4. Use POJOs or Protobuf messages for workflow/activity parameters
5. Use `Workflow.randomUUID()`, `Workflow.newRandom()`, and `Workflow.currentTimeMillis()` for deterministic values
