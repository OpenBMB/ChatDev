# Python Workflow Sandbox

## Overview

The Python SDK runs workflows in a sandbox that provides automatic protection against non-deterministic operations. This is unique to the Python SDK.

## How the Sandbox Works

The sandbox:
- Isolates global state via `exec` compilation
- Restricts non-deterministic library calls via proxy objects
- Passes through standard library with restrictions
- Reloads workflow files on each execution

## Forbidden Operations

These operations will fail in the sandbox:

- **Direct I/O**: Network calls, file reads/writes
- **Threading**: `threading` module operations
- **Subprocess**: `subprocess` calls
- **Global state**: Modifying mutable global variables
- **Blocking sleep**: `time.sleep()` (use `workflow.sleep(timedelta(...))`)

## Pass-Through Pattern

Third-party libraries that aren't sandbox-aware need explicit pass-through:

```python
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    import pydantic
    from my_module import my_dataclass
```

**When to use pass-through:**
- Data classes and models (Pydantic, dataclasses)
- Serialization libraries
- Type definitions
- Any library that doesn't do I/O or non-deterministic operations
- Performance, as many non-passthrough imports can be slower

**Note:** The imports, even when using `imports_passed_through`, should all be at the top of the file. Runtime imports are an anti-pattern.

## Importing Activities

Activities should be imported through pass-through since they're defined outside the sandbox:

```python
# workflows/order.py
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities.payment import process_payment
    from activities.shipping import ship_order

@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, order_id: str) -> str:
        await workflow.execute_activity(
            process_payment,
            order_id,
            start_to_close_timeout=timedelta(minutes=5),
        )
        return await workflow.execute_activity(
            ship_order,
            order_id,
            start_to_close_timeout=timedelta(minutes=10),
        )
```

## Disabling the Sandbox

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        with workflow.unsafe.sandbox_unrestricted():
            # Unrestricted code block
            pass
        return "result"
```

- Per‑block escape hatch from runtime restrictions; imports unchanged.
- Use when: You need to call something the sandbox would normally block (e.g., a restricted stdlib call) in a very small, controlled section.
- **IMPORTANT:** Use it sparingly; you lose determinism checks inside the block
- Genuinely non-deterministic code still *MUST* go into activities.

## Customizing Invalid Module Members

`invalid_module_members` includes modules that cannot be accessed.

Checks are compared against the fully qualified path to the item.

```python
import dataclasses
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import (
  SandboxedWorkflowRunner,
  SandboxMatcher,
  SandboxRestrictions,
)

# Example 1: Remove a restriction on datetime.date.today():
restrictions = dataclasses.replace(
    SandboxRestrictions.default,
    invalid_module_members=SandboxRestrictions.invalid_module_members_default.with_child_unrestricted(
      "datetime", "date", "today",
    ),
)

# Example 2: Restrict the datetime.date class from being used
restrictions = dataclasses.replace(
    SandboxRestrictions.default,
    invalid_module_members=SandboxRestrictions.invalid_module_members_default | SandboxMatcher(
      children={"datetime": SandboxMatcher(use={"date"})},
    ),
)

worker = Worker(
    ...,
    workflow_runner=SandboxedWorkflowRunner(restrictions=restrictions),
)
```

## Import Notification Policy

Control warnings/errors for sandbox import issues. Recommended for catching potential problems:

```python
from temporalio import workflow
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

restrictions = SandboxRestrictions.default.with_import_notification_policy(
    workflow.SandboxImportNotificationPolicy.WARN_ON_DYNAMIC_IMPORT
    | workflow.SandboxImportNotificationPolicy.WARN_ON_UNINTENTIONAL_PASSTHROUGH
)

worker = Worker(
    ...,
    workflow_runner=SandboxedWorkflowRunner(restrictions=restrictions),
)
```

- `WARN_ON_DYNAMIC_IMPORT` (default) - warns on imports after initial workflow load
- `WARN_ON_UNINTENTIONAL_PASSTHROUGH` - warns when modules are imported into sandbox without explicit passthrough (not default, but highly recommended for catching missing passthroughs)
- `RAISE_ON_UNINTENTIONAL_PASSTHROUGH` - raise instead of warn

Override per-import with the context manager:

```python
with workflow.unsafe.sandbox_import_notification_policy(
    workflow.SandboxImportNotificationPolicy.SILENT
):
    import pydantic  # No warning for this import
```

## Disable Lazy sys.modules Passthrough

By default, passthrough modules are lazily added to the sandbox's `sys.modules` when accessed. To require explicit imports:

```python
import dataclasses
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

restrictions = dataclasses.replace(
    SandboxRestrictions.default,
    disable_lazy_sys_module_passthrough=True,
)

worker = Worker(
    ...,
    workflow_runner=SandboxedWorkflowRunner(restrictions=restrictions),
)
```

When `True`, passthrough modules must be explicitly imported to appear in the sandbox's `sys.modules`.

## File Organization

**Critical**: Keep workflow definitions in separate files from activity definitions.

The sandbox reloads workflow definition files on every execution. Minimizing file contents improves Worker performance.

```
my_temporal_app/
├── workflows/
│   └── order.py         # Only workflow classes
├── activities/
│   └── payment.py       # Only activity functions
├── models/
│   └── order.py         # Shared data models
├── worker.py            # Worker setup, imports both
└── starter.py           # Client code
```

## Common Issues

### Import Errors

```
Error: Cannot import 'pydantic' in sandbox
```

**Fix**: Use pass-through:

```python
with workflow.unsafe.imports_passed_through():
    import pydantic
```

### Non-Determinism from Libraries

Some libraries do internal caching or use current time:

```python
# May cause non-determinism
import some_library
result = some_library.cached_operation()  # Cache changes between replays
```

**Fix**: Move to activity or use pass-through with caution.

## Best Practices

1. **Separate workflow and activity files** for performance
2. **Use pass-through explicitly** for third-party libraries
3. **Keep workflow files small** to minimize reload time
4. **Move I/O to activities** always
5. **Test with replay** to catch sandbox issues early
