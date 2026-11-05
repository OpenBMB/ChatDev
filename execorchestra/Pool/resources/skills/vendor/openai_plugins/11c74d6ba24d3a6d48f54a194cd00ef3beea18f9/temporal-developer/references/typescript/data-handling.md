# TypeScript SDK Data Handling

## Overview

The TypeScript SDK uses data converters to serialize/deserialize workflow inputs, outputs, and activity parameters.

## Default Data Converter

The default converter handles:
- `undefined` and `null`
- `Uint8Array` (as binary)
- JSON-serializable types

Note: Protobuf support requires using a data converter (`DefaultPayloadConverterWithProtobufs`). See the Protobuf Support section below.

## Custom Data Converter

Create custom converters for special serialization needs.

```typescript
// payload-converter.ts
import {
  PayloadConverter,
  Payload,
  defaultPayloadConverter,
} from '@temporalio/common';

class CustomPayloadConverter implements PayloadConverter {
  toPayload<T>(value: T): Payload | undefined {
    // Custom serialization logic
    return defaultPayloadConverter.toPayload(value);
  }

  fromPayload<T>(payload: Payload): T {
    // Custom deserialization logic
    return defaultPayloadConverter.fromPayload(payload);
  }
}

export const payloadConverter = new CustomPayloadConverter();
```

```typescript
// client.ts
import { Client } from '@temporalio/client';

const client = new Client({
  dataConverter: {
    payloadConverterPath: require.resolve('./payload-converter'),
  },
});
```

```typescript
// worker.ts
import { Worker } from '@temporalio/worker';

const worker = await Worker.create({
  dataConverter: {
    payloadConverterPath: require.resolve('./payload-converter'),
  },
  // ...
});
```

## Composition of Payload Converters

```typescript
import { CompositePayloadConverter } from '@temporalio/common';

// The order matters — converters are tried in sequence until one returns a non-null Payload
export const payloadConverter = new CompositePayloadConverter(
  new PayloadConverterFoo(),
  new PayloadConverterBar(),
);
```

## Protobuf Support

Using Protocol Buffers for type-safe serialization.

**Note:** JSON serialization (the default) is preferred for TypeScript applications—it's simpler and more performant. Use Protobuf only when interoperating with services that require it.

```typescript
import { DefaultPayloadConverterWithProtobufs } from '@temporalio/common/lib/protobufs';

const dataConverter: DataConverter = {
  payloadConverter: new DefaultPayloadConverterWithProtobufs({
    protobufRoot: myProtobufRoot,
  }),
};
```

## Payload Codec (Encryption)

Encrypt sensitive workflow data.

```typescript
import { PayloadCodec, Payload } from '@temporalio/common';

class EncryptionCodec implements PayloadCodec {
  private readonly encryptionKey: Uint8Array;

  constructor(key: Uint8Array) {
    this.encryptionKey = key;
  }

  async encode(payloads: Payload[]): Promise<Payload[]> {
    return Promise.all(
      payloads.map(async (payload) => ({
        metadata: {
          encoding: 'binary/encrypted',
        },
        data: await this.encrypt(payload.data ?? new Uint8Array()),
      }))
    );
  }

  async decode(payloads: Payload[]): Promise<Payload[]> {
    return Promise.all(
      payloads.map(async (payload) => {
        if (payload.metadata?.encoding === 'binary/encrypted') {
          return {
            ...payload,
            data: await this.decrypt(payload.data ?? new Uint8Array()),
          };
        }
        return payload;
      })
    );
  }

  private async encrypt(data: Uint8Array): Promise<Uint8Array> {
    // Implement encryption (e.g., using Web Crypto API)
    return data;
  }

  private async decrypt(data: Uint8Array): Promise<Uint8Array> {
    // Implement decryption
    return data;
  }
}

// Apply codec
const dataConverter: DataConverter = {
  payloadCodecs: [new EncryptionCodec(encryptionKey)],
};
```

## Search Attributes

Custom searchable fields for workflow visibility.

### Setting Search Attributes at Start

```typescript
import { Client } from '@temporalio/client';

const client = new Client();

await client.workflow.start('orderWorkflow', {
  taskQueue: 'orders',
  workflowId: `order-${orderId}`,
  args: [order],
  searchAttributes: {
    OrderId: [orderId],
    CustomerType: ['premium'],
    OrderTotal: [99.99],
    CreatedAt: [new Date()],
  },
});
```

### Upserting Search Attributes from Workflow

```typescript
import { upsertSearchAttributes, workflowInfo } from '@temporalio/workflow';

export async function orderWorkflow(order: Order): Promise<string> {
  // Update status as workflow progresses
  upsertSearchAttributes({
    OrderStatus: ['processing'],
  });

  await processOrder(order);

  upsertSearchAttributes({
    OrderStatus: ['completed'],
  });

  return 'done';
}
```

### Reading Search Attributes

```typescript
import { workflowInfo } from '@temporalio/workflow';

export async function orderWorkflow(): Promise<void> {
  const info = workflowInfo();
  const searchAttrs = info.searchAttributes;
  const orderId = searchAttrs?.OrderId?.[0];
  // ...
}
```

### Querying Workflows by Search Attributes

```typescript
const client = new Client();

// List workflows using search attributes
for await (const workflow of client.workflow.list({
  query: 'OrderStatus = "processing" AND CustomerType = "premium"',
})) {
  console.log(`Workflow ${workflow.workflowId} is still processing`);
}
```

## Workflow Memo

Store arbitrary metadata with workflows (not searchable).

```typescript
// Set memo at workflow start
await client.workflow.start('orderWorkflow', {
  taskQueue: 'orders',
  workflowId: `order-${orderId}`,
  args: [order],
  memo: {
    customerName: order.customerName,
    notes: 'Priority customer',
  },
});

// Read memo from workflow
import { workflowInfo } from '@temporalio/workflow';

export async function orderWorkflow(): Promise<void> {
  const info = workflowInfo();
  const customerName = info.memo?.customerName;
  // ...
}
```

## Best Practices

1. Keep payloads small—see `references/core/gotchas.md` for limits
2. Use search attributes for business-level visibility and filtering
3. Encrypt sensitive data with PayloadCodec
4. Use memo for non-searchable metadata
5. Configure the same data converter on both client and worker
