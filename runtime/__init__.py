"""Runtime package — public API surface.

Uses lazy imports to avoid the circular dependency chain
check.check -> runtime.bootstrap.schema -> runtime -> runtime.sdk -> check.check
that occurs when this module eagerly imports runtime.sdk at load time.
"""

from typing import Any

__all__ = ["WorkflowMetaInfo", "WorkflowRunResult", "run_workflow"]


def __getattr__(name: str) -> Any:
    """Resolve the public SDK names on first access (PEP 562)."""
    if name in __all__:
        from runtime import sdk

        return getattr(sdk, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
