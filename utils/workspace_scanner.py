"""Utilities for scanning nested code_workspace directories."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional


@dataclass
class WorkspaceEntry:
    """Metadata about a workspace file or directory."""

    path: str  # relative path from workspace root
    type: str  # "file" | "directory"
    size: Optional[int]
    modified_ts: Optional[float]
    depth: int


def iter_workspace_entries(
    root: Path | str,
    *,
    recursive: bool = True,
    max_depth: int = 5,
    include_hidden: bool = False,
) -> Iterator[WorkspaceEntry]:
    """Yield entries under the workspace root respecting depth/hidden filters."""

    base = Path(root).resolve()
    if not base.exists():
        return

    stack: List[tuple[Path, int]] = [(base, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except FileNotFoundError:
            continue
        except PermissionError:
            continue
        for child in children:
            try:
                rel = child.relative_to(base)
            except ValueError:
                continue
            if not include_hidden and _is_hidden(rel):
                continue
            entry_type = "directory" if child.is_dir() else "file"
            size = None
            modified = None
            try:
                stat = child.stat()
                modified = stat.st_mtime
                if child.is_file():
                    size = stat.st_size
            except (FileNotFoundError, PermissionError, OSError):
                pass
            child_depth = depth + 1
            yield WorkspaceEntry(
                path=str(rel),
                type=entry_type,
                size=size,
                modified_ts=modified,
                depth=child_depth,
            )
            if recursive and child.is_dir() and child_depth < max_depth:
                stack.append((child, child_depth))


def _is_hidden(relative_path: Path) -> bool:
    return any(part.startswith(".") for part in relative_path.parts)
