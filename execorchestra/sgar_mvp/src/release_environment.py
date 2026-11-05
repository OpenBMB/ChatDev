"""Checkout-bound branch policy and local storage boundaries for release tooling."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast


_POLICY_PATH = Path(__file__).resolve().parents[1] / "config/release_environment.json"
_STORAGE_ROOT_ENV = "SGAR_RELEASE_STORAGE_ROOT"


def is_approved_release_branch(branch: object) -> bool:
    """Read the committed policy included in the release source collection."""
    try:
        raw: object = json.loads(_POLICY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("release_environment_policy_invalid") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("release_environment_policy_invalid")
    policy = cast(dict[str, object], raw)
    if (
        set(policy) != {"protocol", "allowed_branches"}
        or policy.get("protocol") != "sgar-release-environment-v1"
    ):
        raise RuntimeError("release_environment_policy_invalid")
    raw_branches = policy.get("allowed_branches")
    if not isinstance(raw_branches, list) or not raw_branches:
        raise RuntimeError("release_environment_policy_invalid")
    branches: list[str] = []
    for item in cast(list[object], raw_branches):
        if not isinstance(item, str) or not item.strip() or item in branches:
            raise RuntimeError("release_environment_policy_invalid")
        branches.append(item)
    return isinstance(branch, str) and bool(branch) and branch in branches


def release_storage_root() -> Path:
    """Use an explicit native absolute root, retaining the Windows D:/ default."""
    configured = os.environ.get(_STORAGE_ROOT_ENV)
    if configured is None:
        if os.name != "nt":
            raise RuntimeError("release_storage_root_required")
        configured = "D:/"
    root = Path(configured).expanduser()
    if not configured.strip() or not root.is_absolute():
        raise RuntimeError("release_storage_root_must_be_absolute")
    resolved = root.resolve()
    if resolved.exists() and not resolved.is_dir():
        raise RuntimeError("release_storage_root_not_directory")
    return resolved


def require_release_storage_path(path: Path, *, code: str) -> Path:
    """Reject traversal and resolved symlink/junction escapes from the local root."""
    root = release_storage_root()
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(root):
        raise RuntimeError(code)
    return resolved
