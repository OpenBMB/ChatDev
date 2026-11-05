"""Method agnostic execution boundary for SGAR resources.

The default executor remains the legacy implementation. Integrations may inject
an implementation that executes in an externally owned environment.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import posixpath
from typing import Any, Protocol


_BOUND_RUNTIME: ContextVar[Any] = ContextVar("sgar_execution_substrate", default=None)


class RuntimeInjectionError(RuntimeError):
    """Raised when an injected runtime cannot safely service an action."""


def normalize_task_runtime_path(path: str) -> str:
    """Resolve a POSIX path inside an externally owned task filesystem.

    Absolute paths belong to the task container, not the control host.  Only
    the stable working-directory alias is special: relative names use /app.
    This does not open or mount a host path; source staging has its own boundary.
    """
    if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
        raise RuntimeInjectionError("UNBOUND_RUNTIME_PATH:task_path_outside_runtime")
    if any(part == ".." for part in path.split("/")):
        raise RuntimeInjectionError("UNBOUND_RUNTIME_PATH:task_path_outside_runtime")
    return posixpath.normpath(path if path.startswith("/") else "/app/" + path)


class ExecutionSubstrate(Protocol):
    runtime_id: str

    async def execute(self, *, prepared: Any, request: Any) -> Any:
        """Execute one already lowered action and return ExecutionResult."""

    async def read_text(self, path: str) -> str:
        """Read task-state text through the bound execution substrate."""

    async def read_bytes(self, path: str) -> bytes:
        """Read verified task-state bytes through the bound execution substrate."""

    async def write_text(self, path: str, text: str) -> None:
        """Write task-state text through the bound execution substrate."""

    async def exists(self, path: str) -> bool:
        """Check task-state path through the bound execution substrate."""

    def require_pipeline_ready(self) -> None:
        """Validate that formal scope and artifact operations are available."""

    def step_scope(
        self, *, step_id: str, depends_on: tuple[str, ...], attempt: int
    ) -> dict[str, Any]:
        """Return a task-backed scope for one formal step."""


def require_execution_substrate(substrate: Any, *, mode: str) -> Any:
    if mode not in {"default", "external"}:
        raise RuntimeInjectionError("invalid_runtime_mode")
    if mode == "external" and substrate is None:
        raise RuntimeInjectionError(
            "UNBOUND_RUNTIME_PATH: external mode requires an execution substrate"
        )
    if substrate is not None and mode != "external":
        raise RuntimeInjectionError("execution_substrate_mode_mismatch")
    if substrate is not None and not callable(getattr(substrate, "execute", None)):
        raise RuntimeInjectionError("invalid_execution_substrate")
    return substrate


@contextmanager
def runtime_binding(substrate: Any, *, mode: str):
    substrate = require_execution_substrate(substrate, mode=mode)
    token = _BOUND_RUNTIME.set(substrate)
    try:
        yield substrate
    finally:
        _BOUND_RUNTIME.reset(token)


def require_legacy_runtime(operation: str) -> None:
    if _BOUND_RUNTIME.get() is not None:
        raise RuntimeInjectionError(f"UNBOUND_RUNTIME_PATH:{operation}")


def bound_pipeline(function):
    """Bind fail-closed legacy guards for this async run and its child tasks."""
    @wraps(function)
    async def run(*args, **kwargs):
        substrate = kwargs.get("execution_substrate")
        mode = kwargs.get("execution_substrate_mode", "default")
        with runtime_binding(substrate, mode=mode):
            if substrate is not None:
                substrate.require_pipeline_ready()
            return await function(*args, **kwargs)
    return run
