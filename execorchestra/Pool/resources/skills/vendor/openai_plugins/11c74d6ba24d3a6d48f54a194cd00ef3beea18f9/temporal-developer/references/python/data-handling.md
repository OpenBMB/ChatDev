# Python SDK Data Handling

## Overview

The Python SDK uses data converters to serialize/deserialize workflow inputs, outputs, and activity parameters.

## Default Data Converter

The default converter handles:
- `None`
- `bytes` (as binary)
- Protobuf messages
- JSON-serializable types (dict, list, str, int, float, bool)

## Pydantic Integration

Use Pydantic models for validated, typed data.

In your workflow definition, just use input and result types that subclass `pydantic.BaseModel`:

```python
from pydantic import BaseModel

class OrderInput(BaseModel):
    order_id: str
    items: list[str]
    total: float
    customer_email: str

class OrderResult(BaseModel):
    order_id: str
    status: str
    tracking_number: str | None = None

@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, input: OrderInput) -> OrderResult:
        # Pydantic validation happens automatically
        return OrderResult(
            order_id=input.order_id,
            status="completed",
            tracking_number="TRK123",
        )
```

And when you configure the client, pass the `pydantic_data_converter`:

```python
from temporalio.contrib.pydantic import pydantic_data_converter
# Configure client with Pydantic support
client = await Client.connect(
    "localhost:7233",
    namespace="default",
    data_converter=pydantic_data_converter,
)
```

## Custom Data Conversion

Usually the easiest way to do this is via implementing an EncodingPayloadConverter and CompositePayloadConverter. See:
- https://raw.githubusercontent.com/temporalio/samples-python/refs/heads/main/custom_converter/shared.py
- https://raw.githubusercontent.com/temporalio/samples-python/refs/heads/main/custom_converter/starter.py

for an extended example.

## Payload Encryption

Encrypt sensitive workflow data.

```python
from temporalio.converter import PayloadCodec
from temporalio.api.common.v1 import Payload
from cryptography.fernet import Fernet
from typing import Sequence

class EncryptionCodec(PayloadCodec):
    def __init__(self, key: bytes):
        self._fernet = Fernet(key)

    async def encode(self, payloads: Sequence[Payload]) -> list[Payload]:
        return [
            Payload(
                metadata={"encoding": b"binary/encrypted"},
                # Since encryption uses C extensions that give up the GIL, we can avoid blocking the async event loop here.
                data=await asyncio.to_thread(self._fernet.encrypt, p.SerializeToString()),
            )
            for p in payloads
        ]

    async def decode(self, payloads: Sequence[Payload]) -> list[Payload]:
        result = []
        for p in payloads:
            if p.metadata.get("encoding") == b"binary/encrypted":
                decrypted = await asyncio.to_thread(self._fernet.decrypt, p.data)
                decoded = Payload()
                decoded.ParseFromString(decrypted)
                result.append(decoded)
            else:
                result.append(p)
        return result

# Apply encryption codec
client = await Client.connect(
    "localhost:7233",
    namespace="default",
    data_converter=DataConverter(
        payload_codec=EncryptionCodec(encryption_key),
    ),
)
```

## Search Attributes

Custom searchable fields for workflow visibility. These can be created at workflow start:

```python
from temporalio.common import (
    SearchAttributeKey,
    SearchAttributePair,
    TypedSearchAttributes,
)
from datetime import datetime
from datetime import timezone

ORDER_ID = SearchAttributeKey.for_keyword("OrderId")
ORDER_STATUS = SearchAttributeKey.for_keyword("OrderStatus")
ORDER_TOTAL = SearchAttributeKey.for_float("OrderTotal")
CREATED_AT = SearchAttributeKey.for_datetime("CreatedAt")

# At workflow start
handle = await client.start_workflow(
    OrderWorkflow.run,
    order,
    id=f"order-{order.id}",
    task_queue="orders",
    search_attributes=TypedSearchAttributes([
        SearchAttributePair(ORDER_ID, order.id),
        SearchAttributePair(ORDER_STATUS, "pending"),
        SearchAttributePair(ORDER_TOTAL, order.total),
        SearchAttributePair(CREATED_AT, datetime.now(timezone.utc)),
    ]),
)
```

Or upserted during workflow execution:

```python
from temporalio import workflow
from temporalio.common import SearchAttributeKey, SearchAttributePair, TypedSearchAttributes

ORDER_STATUS = SearchAttributeKey.for_keyword("OrderStatus")

@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, order: Order) -> str:
        # ... process order ...

        # Update search attribute
        workflow.upsert_search_attributes(TypedSearchAttributes([
            SearchAttributePair(ORDER_STATUS, "completed"),
        ]))
        return "done"
```

### Querying Workflows by Search Attributes

```python
# List workflows using search attributes
async for workflow in client.list_workflows(
    'OrderStatus = "processing" OR OrderStatus = "pending"'
):
    print(f"Workflow {workflow.id} is still processing")
```

## Workflow Memo

Store arbitrary metadata with workflows (not searchable).

```python
# Set memo at workflow start
await client.execute_workflow(
    OrderWorkflow.run,
    order,
    id=f"order-{order.id}",
    task_queue="orders",
    memo={
        "customer_name": order.customer_name,
        "notes": "Priority customer",
    },
)
```

```python
# Read memo from workflow
@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, order: Order) -> str:
        notes: str = workflow.memo_value("notes", type_hint=str)
        ...
```

## Deterministic APIs for Values

Use these APIs within workflows for deterministic random values and UUIDs:

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        # Deterministic UUID (same on replay)
        unique_id = workflow.uuid4()

        # Deterministic random (same on replay)
        rng = workflow.random()
        value = rng.randint(1, 100)

        return str(unique_id)
```

## Best Practices

1. Use Pydantic for input/output validation
2. Keep payloads small—see `references/core/gotchas.md` for limits
3. Encrypt sensitive data with PayloadCodec
4. Use dataclasses for simple data structures
5. Use `workflow.uuid4()` and `workflow.random()` for deterministic values
