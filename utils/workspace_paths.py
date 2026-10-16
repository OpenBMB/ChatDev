"""Validate names and confine generated files to their workspace."""

import re
from pathlib import Path

from utils.exceptions import ValidationError


def validate_path_component(name: str, *, field: str = "name") -> str:
    """Accept a single directory name on both POSIX and Windows."""
    if (
        name.strip() in {"", ".", ".."}
        or re.search(r"[/\\:\x00-\x1f\x7f]", name)
    ):
        raise ValidationError(
            f"Invalid {field}: expected a single directory name without path separators, "
            "drive prefixes, or control characters",
            field=field,
        )
    return name


def resolve_workspace_path(root: Path | str, *parts: str) -> Path:
    """Resolve a child path, rejecting traversal and existing escaping symlinks."""
    for part in parts:
        validate_path_component(part)
    try:
        resolved_root = Path(root).resolve()
        candidate = resolved_root.joinpath(*parts).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValidationError("Unable to resolve workspace path", field="workspace") from exc
    if candidate == resolved_root or not candidate.is_relative_to(resolved_root):
        raise ValidationError("Workspace path escapes its root directory", field="workspace")
    return candidate


def session_directory_name(session_id: str) -> str:
    """Map a raw transport session ID to one distinct directory name."""
    return f"session_{validate_path_component(session_id, field='session_id')}"
