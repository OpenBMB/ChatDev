"""Path-length-safe helpers for same-directory atomic persistence.

Atomic replacement requires the temporary object to live beside its target.
The temporary basename must not repeat the target basename: doing so can push
otherwise valid Windows paths beyond the legacy ``MAX_PATH`` boundary.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path


def temporary_sibling_path(target: str | Path) -> Path:
    """Return a collision-resistant, target-name-independent sibling path."""

    path = Path(target)
    # An 80-bit random component is ample for an exclusive-create temporary
    # file and leaves substantially more headroom under the Windows MAX_PATH
    # compatibility boundary than a full UUID plus a long prefix.
    return path.parent / f".s-{uuid.uuid4().hex[:20]}.tmp"


def bounded_path_component(
    value: object,
    *,
    fallback: str = "item",
    max_length: int = 64,
) -> str:
    """Return a portable component with deterministic collision resistance."""

    if max_length < 18:
        raise ValueError("path_component_max_length_too_small")
    source = str(value)
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", source).strip("._")
    normalized = normalized or fallback
    if len(normalized) <= max_length:
        return normalized
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    prefix_length = max_length - len(digest) - 1
    return f"{normalized[:prefix_length]}-{digest}"


__all__ = ["bounded_path_component", "temporary_sibling_path"]
