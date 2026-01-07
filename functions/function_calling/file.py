"""File-related function tools for model-invoked file access."""

import fnmatch
import locale
import mimetypes
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    MutableSequence,
    Optional,
    Sequence,
)

from entity.messages import MessageBlock, MessageBlockType
from utils.attachments import AttachmentStore
from utils.workspace_scanner import iter_workspace_entries
from utils.function_catalog import ParamMeta


class FileToolContext:
    """Helper to read runtime context injected via `_context` kwarg."""

    def __init__(self, ctx: Dict[str, Any] | None):
        if ctx is None:
            raise ValueError("_context is required for file tools")
        self._ctx = ctx
        self.attachment_store = self._require_store(ctx.get("attachment_store"))
        self.workspace_root = self._require_workspace(ctx.get("python_workspace_root"))
        self.session_root = self._require_session_root(ctx.get("graph_directory"), self.workspace_root)

    @staticmethod
    def _require_store(store: Any) -> AttachmentStore:
        if not isinstance(store, AttachmentStore):
            raise ValueError("attachment_store missing from _context")
        return store

    @staticmethod
    def _require_workspace(root: Any) -> Path:
        if root is None:
            raise ValueError("python_workspace_root missing from _context")
        path = Path(root).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _require_session_root(root: Any, workspace_root: Path) -> Path:
        base = root or workspace_root.parent
        path = Path(base).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_under_workspace(self, relative_path: str | Path) -> Path:
        rel = Path(relative_path)
        target = rel.resolve() if rel.is_absolute() else (self.workspace_root / rel).resolve()
        if self.workspace_root not in target.parents and target != self.workspace_root:
            raise ValueError("Path is outside workspace")
        return target

    def resolve_under_session(self, relative_path: str | Path) -> Path:
        raw = Path(relative_path)
        candidates = []
        if raw.is_absolute():
            candidates.append(raw.resolve())
        else:
            candidates.append((self.session_root / raw).resolve())
            candidates.append(raw.resolve())
        for target in candidates:
            if self.session_root in target.parents or target == self.session_root:
                return target
        raise ValueError("Path is outside session directory")

    def to_session_relative(self, absolute_path: str | Path | None) -> Optional[str]:
        if not absolute_path:
            return None
        target = Path(absolute_path).resolve()
        if self.session_root in target.parents or target == self.session_root:
            return target.relative_to(self.session_root).as_posix()
        return str(target)

    def to_workspace_relative(self, absolute_path: str | Path | None) -> Optional[str]:
        if not absolute_path:
            return None
        target = Path(absolute_path).resolve()
        if self.workspace_root in target.parents or target == self.workspace_root:
            rel = target.relative_to(self.workspace_root)
            return rel.as_posix() or "."
        return None


def _check_attachments_not_modified(path: str) -> None:
    if path.startswith("attachments"):
        raise ValueError("Modifications to the attachments directory are not allowed")

def describe_available_files(
    *,
    recursive: bool = True,
    limit: int = 200,
    include_hidden: bool = False,
    # max_depth: int = 5,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    List accessible files from the attachment store and the current code_workspace.
    """

    max_depth = 8
    ctx = FileToolContext(_context)
    entries: List[Dict[str, Any]] = []
    total_limit = max(1, limit)

    # # Attachment store (user uploads or files registered via load_file)
    # for attachment_id, record in ctx.attachment_store.list_records().items():
    #     ref = record.ref
    #     workspace_path = ctx.to_workspace_relative(ref.local_path)
    #     session_path = ctx.to_session_relative(ref.local_path)
    #     display_path = workspace_path or session_path or ref.local_path
    #     entries.append(
    #         {
    #             "id": attachment_id,
    #             "name": ref.name,
    #             "source": record.extra.get("source") if record.extra else "attachment",
    #             "mime": ref.mime_type,
    #             "size": ref.size,
    #             "type": "file",
    #             "path": display_path,
    #         }
    #     )
    #     if len(entries) >= total_limit:
    #         return {"files": entries}

    # Workspace files (includes attachments directory because it sits inside workspace)
    for entry in iter_workspace_entries(
        ctx.workspace_root,
        recursive=recursive,
        max_depth=max_depth,
        include_hidden=include_hidden,
    ):
        if len(entries) >= total_limit:
            break
        abs_path = (ctx.workspace_root / entry.path).resolve()
        workspace_path = Path(entry.path)
        # session_path = ctx.to_session_relative(abs_path)
        entries.append(
            {
                "id": entry.path,
                "name": Path(entry.path).name,
                "source": "workspace",
                "path": workspace_path,
                "absolute_path": abs_path,
                "type": entry.type,
                "size": entry.size,
                "depth": entry.depth,
            }
        )

    return {"files": entries[:total_limit]}


def list_directory(
    path: Annotated[str, ParamMeta(description="Workspace-relative directory path")]=".",
    *,
    recursive: Annotated[bool, ParamMeta(description="Traverse subdirectories")] = False,
    max_depth: Annotated[int, ParamMeta(description="Maximum depth when recursive=True")] = 3,
    include_hidden: Annotated[bool, ParamMeta(description="Include entries starting with '.'")] = False,
    limit: Annotated[int, ParamMeta(description="Maximum entries to return")] = 500,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """List contents of a workspace-relative directory."""

    ctx = FileToolContext(_context)
    target = ctx.resolve_under_workspace(path)
    if not target.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    if not target.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    if limit <= 0:
        raise ValueError("limit must be positive")
    if recursive and max_depth < 1:
        raise ValueError("max_depth must be >= 1 when recursive")

    entries: List[Dict[str, Any]] = []
    stack: List[tuple[Path, int]] = [(target, 0)]
    base_relative = ctx.to_workspace_relative(target) or "."

    while stack and len(entries) < limit:
        current, depth = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except (FileNotFoundError, PermissionError):
            continue
        for child in children:
            rel = child.relative_to(target)
            if not include_hidden and _path_is_hidden(rel):
                continue
            stat_size = None
            modified = None
            try:
                stat = child.stat()
                modified = stat.st_mtime
                if child.is_file():
                    stat_size = stat.st_size
            except (FileNotFoundError, PermissionError, OSError):
                pass
            entry = {
                "name": child.name,
                "relative_path": rel.as_posix(),
                "absolute_path": str(child),
                "type": "directory" if child.is_dir() else "file",
                "size": stat_size,
                "modified_ts": modified,
                "depth": depth,
            }
            entries.append(entry)
            if len(entries) >= limit:
                break
            if recursive and child.is_dir() and depth + 1 < max_depth:
                stack.append((child, depth + 1))

    return {
        "directory": base_relative,
        "entries": entries[:limit],
        "truncated": len(entries) >= limit,
        "recursive": recursive,
    }


def create_folder(
    path: Annotated[str, ParamMeta(description="Workspace-relative folder path")],
    *,
    parents: Annotated[bool, ParamMeta(description="Create missing parent directories")]
    = True,
    exist_ok: Annotated[bool, ParamMeta(description="Do not raise if folder already exists")]
    = True,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Create a directory tree under the workspace."""

    if not path:
        raise ValueError("path must be provided")
    _check_attachments_not_modified(path)

    ctx = FileToolContext(_context)
    target = ctx.resolve_under_workspace(path)

    if target.exists() and not target.is_dir():
        raise ValueError("Target exists and is not a directory")

    previously_exists = target.exists()
    target.mkdir(parents=parents, exist_ok=exist_ok)

    return {
        "path": ctx.to_workspace_relative(target),
        "absolute_path": str(target),
        "created": not previously_exists,
    }


def delete_path(
    path: Annotated[str, ParamMeta(description="Workspace-relative file or folder path")],
    *,
    recursive: Annotated[
        bool,
        ParamMeta(description="Allow deleting non-empty directories recursively"),
    ] = False,
    missing_ok: Annotated[bool, ParamMeta(description="Suppress error if path is missing")]
    = False,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Delete a workspace file or directory."""

    if not path:
        raise ValueError("path must be provided")

    _check_attachments_not_modified(path)

    ctx = FileToolContext(_context)
    target = ctx.resolve_under_workspace(path)

    if not target.exists():
        if missing_ok:
            return {
                "path": ctx.to_workspace_relative(target),
                "absolute_path": str(target),
                "deleted": False,
                "reason": "missing",
            }
        raise FileNotFoundError(f"Path not found: {path}")

    if target.is_dir():
        if not recursive:
            raise IsADirectoryError("Set recursive=True to delete directories")
        shutil.rmtree(target)
        deleted_type = "directory"
    else:
        target.unlink()
        deleted_type = "file"

    return {
        "path": ctx.to_workspace_relative(target),
        "absolute_path": str(target),
        "deleted": True,
        "type": deleted_type,
    }


def load_file(
    path_or_id: str,
    *,
    # mime_override: Optional[str] = None,
    _context: Dict[str, Any] | None = None,
) -> List[MessageBlock]:
    """
    Load an attachment by ID or register a workspace file as a new attachment.
    """

    ctx = FileToolContext(_context)

    # First, try existing attachment id
    record = ctx.attachment_store.get(path_or_id)
    if record:
        return [record.as_message_block()]

    # Otherwise treat as workspace path
    target = ctx.resolve_under_workspace(path_or_id)
    if not target.exists() or not target.is_file():
        raise ValueError(f"Workspace file not found: {path_or_id}")

    # mime_type = mime_override or (mimetypes.guess_type(target.name)[0] or "application/octet-stream")
    mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    record = ctx.attachment_store.register_file(
        target,
        kind=MessageBlockType.from_mime_type(mime_type),
        display_name=target.name,
        mime_type=mime_type,
        copy_file=False,
        persist=False,
        deduplicate=True,
        extra={
            "source": "workspace",
            "workspace_path": path_or_id,
            "storage": "reference",
        },
    )
    return [record.as_message_block()]


def save_file(
    path: str,
    content: str,
    *,
    encoding: str = "utf-8",
    mode: Literal["overwrite", "append"] = "overwrite",
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Persist data to a workspace file while optionally registering it as an attachment.

    Args:
        path: Relative path where the file will be written.
        content: Plain-text payload encoded with `encoding`.
        encoding: Text encoding used when `content` is provided.
        mode: Whether to replace the file (`overwrite`) or append to it (`append`).

    Returns:
        A dictionary describing the persisted file, including workspace path, absolute path,
        and byte size.

    Raises:
        ValueError: If arguments are missing/invalid or the path escapes the workspace.
        OSError: If the file cannot be written.
    """

    if mode not in {"overwrite", "append"}:
        raise ValueError("mode must be either 'overwrite' or 'append'")

    ctx = FileToolContext(_context)
    target = ctx.resolve_under_workspace(path)
    if target.exists() and target.is_dir():
        raise ValueError("Target path points to a directory")
    target.parent.mkdir(parents=True, exist_ok=True)

    data = content.encode(encoding)

    write_mode = "wb" if mode == "overwrite" else "ab"
    try:
        with target.open(write_mode) as handle:
            handle.write(data)
    except OSError as exc:
        raise OSError(f"Failed to write file '{target}': {exc}") from exc

    size = target.stat().st_size if target.exists() else None
    return {
        "path": ctx.to_workspace_relative(target),
        "absolute_path": str(target),
        "size": size,
        # "mode": mode,
        # "encoding": encoding if content is not None else None,
    }


def read_text_file_snippet(
    path: str,
    *,
    offset: int = 0,
    limit: int = 4000,
    encoding: str = "utf-8",
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Read a snippet of a workspace text file without loading entire content."""

    ctx = FileToolContext(_context)
    target: Path | None = None
    try:
        candidate = ctx.resolve_under_workspace(path)
    except ValueError:
        candidate = None

    if candidate and candidate.exists() and candidate.is_file():
        target = candidate

    if target is None:
        target = ctx.resolve_under_session(path)
        if not target.exists() or not target.is_file():
            raise ValueError(f"File not found in session attachments/workspace: {path}")

    data = target.read_text(encoding=encoding, errors="replace")
    snippet = data[offset : offset + limit]
    return {
        "snippet": snippet,
        "truncated": offset + limit < len(data),
        "length": len(data),
        "offset": offset,
    }


def read_file_segment(
    path: Annotated[str, ParamMeta(description="Workspace-relative text file path")],
    *,
    start_line: Annotated[int, ParamMeta(description="1-based line to begin the snippet")]=1,
    line_count: Annotated[int, ParamMeta(description="Number of lines to include starting from start_line")]=40,
    inline_line_numbers: Annotated[
        bool,
        ParamMeta(description="If true, prefix each snippet line with its line number inside the snippet"),
    ] = False,
    encoding: Annotated[str, ParamMeta(description="Explicit encoding or 'auto'")]="auto",
    include_line_offsets: Annotated[
        bool,
        ParamMeta(description="Include 1-based line metadata for the returned snippet"),
    ] = False,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Read a line range plus metadata from a workspace file."""

    if start_line < 1:
        raise ValueError("start_line must be >= 1")
    if line_count < 1:
        raise ValueError("line_count must be >= 1")

    ctx = FileToolContext(_context)
    target = ctx.resolve_under_workspace(path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    text, used_encoding = _read_text_content(target, encoding)
    newline_style = _detect_newline(text)
    stat = target.stat()

    lines_with_breaks = text.splitlines(keepends=True)
    if not lines_with_breaks:
        lines_with_breaks = [""]
    total_lines = len(lines_with_breaks)
    start_idx = start_line - 1
    if start_idx >= total_lines:
        raise ValueError("start_line is beyond the total number of lines in the file")

    lines_returned = min(line_count, total_lines - start_idx)
    end_idx = start_idx + lines_returned
    segment_lines = lines_with_breaks[start_idx:end_idx]
    snippet = "".join(segment_lines)
    raw_snippet = snippet

    line_starts: List[int] = [0]
    for line in lines_with_breaks:
        line_starts.append(line_starts[-1] + len(line))
    start_char = line_starts[start_idx]

    response: Dict[str, Any] = {
        "path": ctx.to_workspace_relative(target),
        "encoding": used_encoding,
        "newline": newline_style,
        "start_line": start_line,
        "end_line": start_line + lines_returned - 1,
        "line_count": line_count,
        "lines_returned": lines_returned,
        "total_lines": total_lines,
        "snippet": raw_snippet,
        "truncated": end_idx < total_lines,
        "file_size": stat.st_size,
        "modified_ts": stat.st_mtime,
        "mode": "line_range",
    }

    if inline_line_numbers:
        snippet = _render_snippet_with_line_numbers(
            segment_lines,
            start_line,
            newline_style,
            raw_snippet.endswith(("\r\n", "\n", "\r")),
        )
        response["snippet"] = snippet

    if include_line_offsets:
        response.update(_describe_segment_line_offsets(text, start_char, raw_snippet))

    return response


@dataclass(frozen=True)
class TextEdit:
    """Normalized representation of a single line edit."""

    start_line: int
    end_line: int
    replacement_lines: List[str]


def apply_text_edits(
    path: Annotated[str, ParamMeta(description="Workspace-relative file to edit")],
    *,
    start_line: Annotated[int, ParamMeta(description="1-based line where the replacement should begin")],
    end_line: Annotated[
        Optional[int],
        ParamMeta(description="Last line (>= start_line-1) to replace; defaults to start_line"),
    ] = None,
    replacement: Annotated[
        Optional[str],
        ParamMeta(description="Text that should replace the selected line range"),
    ] = "",
    encoding: Annotated[str, ParamMeta(description="Text encoding or 'auto'")]="auto",
    newline: Annotated[
        str,
        ParamMeta(description="Newline style: 'preserve', 'lf', 'crlf', or 'cr'"),
    ]="preserve",
    ensure_trailing_newline: Annotated[
        Optional[bool],
        ParamMeta(description="Force presence/absence of trailing newline; default preserves original"),
    ] = None,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Apply ordered line edits with newline and encoding preservation."""

    ctx = FileToolContext(_context)
    target = ctx.resolve_under_workspace(path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    _check_attachments_not_modified(path)

    normalized = _normalize_edits(_build_single_edit(start_line, end_line, replacement))
    original_text, used_encoding = _read_text_content(target, encoding)
    lines, had_trailing_newline = _split_lines(original_text)
    newline_style = _resolve_newline_choice(newline, _detect_newline(original_text))

    _apply_edits_in_place(lines, normalized)

    if ensure_trailing_newline is None:
        final_trailing = had_trailing_newline
    else:
        final_trailing = ensure_trailing_newline

    rendered = newline_style.join(lines)
    if final_trailing:
        rendered += newline_style

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding=used_encoding)
    stat = target.stat()
    return {
        "path": ctx.to_workspace_relative(target),
        "encoding": used_encoding,
        "newline": newline_style,
        "line_count": len(lines),
        "applied_edits": len(normalized),
        "trailing_newline": final_trailing,
        "file_size": stat.st_size,
        "modified_ts": stat.st_mtime,
    }


def rename_path(
    src: Annotated[str, ParamMeta(description="Existing workspace-relative path")],
    dst: Annotated[str, ParamMeta(description="New workspace-relative path")],
    *,
    overwrite: Annotated[
        bool,
        ParamMeta(description="Allow replacing an existing destination"),
    ] = False,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Rename files or directories inside the workspace."""

    ctx = FileToolContext(_context)
    source = ctx.resolve_under_workspace(src)
    destination = ctx.resolve_under_workspace(dst)
    _check_attachments_not_modified(src)
    _check_attachments_not_modified(dst)

    if not source.exists():
        raise FileNotFoundError(f"Source does not exist: {src}")
    if source == destination:
        return {
            "path": ctx.to_workspace_relative(destination),
            "operation": "rename",
            "skipped": True,
        }

    _clear_destination(destination, overwrite)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)
    return {
        "path": ctx.to_workspace_relative(destination),
        "previous_path": ctx.to_workspace_relative(source),
        "operation": "rename",
    }


def copy_path(
    src: Annotated[str, ParamMeta(description="Source workspace-relative path")],
    dst: Annotated[str, ParamMeta(description="Destination workspace-relative path")],
    *,
    overwrite: Annotated[
        bool,
        ParamMeta(description="Allow replacing destination if it exists"),
    ] = False,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Copy a file tree within the workspace."""

    ctx = FileToolContext(_context)
    source = ctx.resolve_under_workspace(src)
    destination = ctx.resolve_under_workspace(dst)
    _check_attachments_not_modified(dst)

    if not source.exists():
        raise FileNotFoundError(f"Source does not exist: {src}")
    if destination.exists():
        if not overwrite:
            raise FileExistsError(f"Destination already exists: {dst}")
        _clear_destination(destination, overwrite=True)

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)
    return {
        "path": ctx.to_workspace_relative(destination),
        "source": ctx.to_workspace_relative(source),
        "operation": "copy",
    }


def move_path(
    src: Annotated[str, ParamMeta(description="Source workspace-relative path")],
    dst: Annotated[str, ParamMeta(description="Destination workspace-relative path")],
    *,
    overwrite: Annotated[
        bool,
        ParamMeta(description="Allow replacing destination path"),
    ] = False,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Move files or directories, mirroring `mv` semantics across platforms."""

    ctx = FileToolContext(_context)
    source = ctx.resolve_under_workspace(src)
    destination = ctx.resolve_under_workspace(dst)
    _check_attachments_not_modified(src)
    _check_attachments_not_modified(dst)

    if not source.exists():
        raise FileNotFoundError(f"Source does not exist: {src}")
    if source == destination:
        return {
            "path": ctx.to_workspace_relative(destination),
            "operation": "move",
            "skipped": True,
        }
    _clear_destination(destination, overwrite)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(source, destination)
    return {
        "path": ctx.to_workspace_relative(destination),
        "source": ctx.to_workspace_relative(source),
        "operation": "move",
    }


def search_in_files(
    pattern: Annotated[str, ParamMeta(description="Plain text or regex pattern")],
    *,
    globs: Annotated[
        Optional[Sequence[str]],
        ParamMeta(description="Restrict search to these glob patterns"),
    ] = None,
    exclude_globs: Annotated[
        Optional[Sequence[str]],
        ParamMeta(description="Glob patterns to exclude"),
    ] = None,
    use_regex: Annotated[bool, ParamMeta(description="Treat pattern as regex")]=True,
    case_sensitive: Annotated[bool, ParamMeta(description="Match case when True")]=False,
    max_results: Annotated[int, ParamMeta(description="Stop after this many matches")]=200,
    before_context: Annotated[int, ParamMeta(description="Lines to include before match")]=2,
    after_context: Annotated[int, ParamMeta(description="Lines to include after match")]=2,
    include_hidden: Annotated[bool, ParamMeta(description="Search hidden files/folders")]=False,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Search workspace files and return structured matches."""

    if max_results <= 0:
        raise ValueError("max_results must be positive")

    ctx = FileToolContext(_context)
    include_patterns = _normalize_globs(globs) or ["**/*"]
    exclude_patterns = _normalize_globs(exclude_globs)

    matches: List[Dict[str, Any]] = []
    searched_files = 0
    compiled_regex: Optional[re.Pattern[str]] = None
    literal = pattern if case_sensitive else pattern.lower()
    if use_regex:
        flags = re.MULTILINE
        if not case_sensitive:
            flags |= re.IGNORECASE
        compiled_regex = re.compile(pattern, flags)

    for candidate in _iter_candidate_files(
        ctx.workspace_root,
        include_patterns,
        exclude_patterns,
        include_hidden,
    ):
        searched_files += 1
        lines = _read_file_lines_for_search(candidate)
        if not lines:
            continue
        for match in _iter_line_matches(
            lines,
            compiled_regex,
            literal,
            pattern,
            case_sensitive,
            use_regex,
        ):
            before = _slice_context(lines, match["line_number"], before_context, before=True)
            after = _slice_context(lines, match["line_number"], after_context, before=False)
            matches.append(
                {
                    "file": ctx.to_workspace_relative(candidate),
                    "line": match["line_number"],
                    "column": match["column"],
                    "line_text": match["line_text"],
                    "before": before,
                    "after": after,
                }
            )
            if len(matches) >= max_results:
                return {
                    "matches": matches,
                    "limited": True,
                    "engine": "python",
                    "searched_files": searched_files,
                }

    return {
        "matches": matches,
        "limited": False,
        "engine": "python",
        "searched_files": searched_files,
    }


def _read_text_content(path: Path, encoding: str) -> tuple[str, str]:
    if encoding != "auto":
        return path.read_text(encoding=encoding), encoding

    raw = path.read_bytes()
    for candidate in _candidate_encodings():
        try:
            return raw.decode(candidate), candidate
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def _candidate_encodings() -> List[str]:
    preferred = locale.getpreferredencoding(False) or ""
    ordered = [
        "utf-8-sig",
        "utf-8",
        preferred,
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "latin-1",
    ]
    seen: set[str] = set()
    result: List[str] = []
    for item in ordered:
        normalized = (item or "").lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(item)
    return result


_LINE_BREAK_RE = re.compile(r"\r\n|\r|\n")


def _detect_newline(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text and "\n" not in text:
        return "\r"
    return "\n"


def _split_lines(text: str) -> tuple[List[str], bool]:
    if not text:
        return [], False
    has_trailing = text.endswith(("\r\n", "\n", "\r"))
    return text.splitlines(), has_trailing


def _describe_segment_line_offsets(full_text: str, start_index: int, snippet: str) -> Dict[str, Any]:
    """Return 1-based line metadata (columns are 0-based) for a snippet extracted from full_text."""

    before_segment = full_text[:start_index]
    start_line = 1
    last_break_end = 0
    for match in _LINE_BREAK_RE.finditer(before_segment):
        start_line += 1
        last_break_end = match.end()
    start_column = start_index - last_break_end

    line_offsets: List[Dict[str, int]] = [
        {"line": start_line, "offset": 0, "column": start_column},
    ]
    line_number = start_line
    last_break_inside = 0
    for match in _LINE_BREAK_RE.finditer(snippet):
        last_break_inside = match.end()
        line_number += 1
        line_offsets.append({"line": line_number, "offset": match.end(), "column": 0})

    if snippet:
        if last_break_inside:
            end_column = len(snippet) - last_break_inside
        else:
            end_column = start_column + len(snippet)
    else:
        end_column = start_column

    return {
        "start_line": start_line,
        "start_column": start_column,
        "end_line": line_number,
        "end_column": end_column,
        "line_offsets": line_offsets,
    }


def _render_snippet_with_line_numbers(
    lines: Sequence[str],
    start_line: int,
    newline_style: str,
    preserve_trailing_newline: bool,
) -> str:
    numbered: List[str] = []
    for idx, line in enumerate(lines):
        body = line.rstrip("\r\n")
        numbered.append(f"{start_line + idx}:{body}")
    rendered = newline_style.join(numbered)
    if preserve_trailing_newline and numbered:
        rendered += newline_style
    return rendered


def _normalize_edits(edits: Sequence[Mapping[str, Any]]) -> List[TextEdit]:
    if not edits:
        raise ValueError("at least one edit instruction is required")
    normalized: List[TextEdit] = []
    for item in edits:
        if not isinstance(item, Mapping):
            raise ValueError("each edit entry must be a mapping object")
        try:
            start_line = int(item["start_line"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("start_line is required for each edit") from exc
        end_line_raw = item.get("end_line", start_line)
        try:
            end_line = int(end_line_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("end_line must be an integer") from exc
        if start_line < 1:
            raise ValueError("start_line must be >= 1")
        if end_line < start_line - 1:
            raise ValueError("end_line must be >= start_line - 1")
        replacement = item.get("replacement", "")
        if not isinstance(replacement, str):
            raise ValueError("replacement must be a string")
        normalized.append(
            TextEdit(
                start_line=start_line,
                end_line=end_line,
                replacement_lines=replacement.splitlines(),
            )
        )

    normalized.sort(key=lambda edit: (edit.start_line, edit.end_line))
    _validate_edit_ranges(normalized)
    return normalized


def _build_single_edit(
    start_line: int,
    end_line: Optional[int],
    replacement: Optional[str],
) -> List[Mapping[str, Any]]:
    effective_end = end_line if end_line is not None else start_line
    payload = {
        "start_line": start_line,
        "end_line": effective_end,
        "replacement": replacement if replacement is not None else "",
    }
    return [payload]


def _validate_edit_ranges(edits: Sequence[TextEdit]) -> None:
    previous_range_end = 0
    for edit in edits:
        effective_end = max(edit.end_line, edit.start_line - 1)
        if edit.start_line <= previous_range_end and previous_range_end > 0:
            raise ValueError("edit ranges overlap; merge them before calling apply_text_edits")
        previous_range_end = max(previous_range_end, effective_end)


def _apply_edits_in_place(lines: MutableSequence[str], edits: Sequence[TextEdit]) -> None:
    for edit in reversed(edits):
        current_line_count = len(lines)
        if edit.start_line > current_line_count + 1:
            raise ValueError("start_line is beyond the end of the file")
        start_idx = min(edit.start_line - 1, current_line_count)
        if start_idx > current_line_count:
            raise ValueError("start_line is beyond the end of the file")
        removal_count = max(edit.end_line - edit.start_line + 1, 0)
        if removal_count > 0:
            end_line = min(edit.end_line, len(lines))
            removal_count = max(end_line - edit.start_line + 1, 0)
        end_idx = start_idx + removal_count
        lines[start_idx:end_idx] = edit.replacement_lines


def _resolve_newline_choice(preference: str, detected: str) -> str:
    normalized = (preference or "").lower()
    if normalized == "lf":
        return "\n"
    if normalized == "crlf":
        return "\r\n"
    if normalized == "cr":
        return "\r"
    return detected or os.linesep


def _clear_destination(destination: Path, overwrite: bool) -> None:
    if not destination.exists():
        return
    if not overwrite:
        raise FileExistsError(f"Destination already exists: {destination}")
    if destination.is_dir():
        shutil.rmtree(destination)
    else:
        destination.unlink()


def _normalize_globs(patterns: Optional[Sequence[str]]) -> List[str]:
    if not patterns:
        return []
    normalized: List[str] = []
    for raw in patterns:
        if not raw:
            continue
        normalized.append(str(raw))
    return normalized


def _iter_candidate_files(
    root: Path,
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
    include_hidden: bool,
) -> Iterable[Path]:
    yielded: set[str] = set()
    for pattern in include_patterns:
        for candidate in root.glob(pattern):
            if not candidate.is_file():
                continue
            rel = candidate.relative_to(root)
            rel_key = rel.as_posix()
            if rel_key in yielded:
                continue
            if not include_hidden and _path_is_hidden(rel):
                continue
            if _is_excluded(rel_key, exclude_patterns):
                continue
            yielded.add(rel_key)
            yield candidate


def _path_is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _is_excluded(relative_posix: str, exclude_patterns: Sequence[str]) -> bool:
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(relative_posix, pattern):
            return True
    return False


def _read_file_lines_for_search(path: Path) -> List[str]:
    raw, _ = _read_text_content(path, encoding="auto")
    return raw.splitlines()


def _iter_line_matches(
    lines: Sequence[str],
    compiled_regex: Optional[re.Pattern[str]],
    literal_lower: str,
    original_pattern: str,
    case_sensitive: bool,
    use_regex: bool,
) -> Iterable[Dict[str, Any]]:
    for idx, raw_line in enumerate(lines):
        line_number = idx + 1
        line_text = raw_line
        if use_regex and compiled_regex is not None:
            for match in compiled_regex.finditer(line_text):
                yield {
                    "line_number": line_number,
                    "column": match.start() + 1,
                    "line_text": line_text,
                }
        else:
            if not original_pattern:
                continue
            haystack = line_text if case_sensitive else line_text.lower()
            needle = original_pattern if case_sensitive else literal_lower
            start = haystack.find(needle)
            while start != -1:
                yield {
                    "line_number": line_number,
                    "column": start + 1,
                    "line_text": line_text,
                }
                start = haystack.find(needle, start + max(len(needle), 1))


def _slice_context(
    lines: Sequence[str],
    center_line: int,
    span: int,
    *,
    before: bool,
) -> List[str]:
    if span <= 0:
        return []
    if before:
        start_line = max(center_line - span, 1)
        end_line = center_line - 1
    else:
        start_line = center_line + 1
        end_line = min(center_line + span, len(lines))
    if end_line < start_line:
        return []
    start_idx = start_line - 1
    end_idx = end_line
    return list(lines[start_idx:end_idx])
