"""Process-local binding for an explicitly selected retrieval policy."""

from __future__ import annotations

from pathlib import Path


_ACTIVE_RETRIEVAL_POLICY_PATH: Path | None = None


def bind_retrieval_policy_path(path: str | Path) -> Path:
    global _ACTIVE_RETRIEVAL_POLICY_PATH
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise RuntimeError("runtime_retrieval_policy_missing")
    if (
        _ACTIVE_RETRIEVAL_POLICY_PATH is not None
        and _ACTIVE_RETRIEVAL_POLICY_PATH != resolved
    ):
        raise RuntimeError("runtime_retrieval_policy_rebind")
    _ACTIVE_RETRIEVAL_POLICY_PATH = resolved
    return resolved


def active_retrieval_policy_path() -> Path | None:
    return _ACTIVE_RETRIEVAL_POLICY_PATH


__all__ = ["active_retrieval_policy_path", "bind_retrieval_policy_path"]
