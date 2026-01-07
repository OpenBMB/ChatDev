"""Deep research tools for search results and report management."""

import json
import re
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Tuple

from filelock import FileLock

from entity.messages import MessageBlock, MessageBlockType
from functions.function_calling.file import FileToolContext
from utils.function_catalog import ParamMeta

# Constants for file paths (relative to workspace root)
SEARCH_RESULTS_FILE = "deep_research/search_results.json"
SEARCH_LOCK_FILE = "deep_research/search_results.lock"
REPORT_FILE = "deep_research/report.md"
REPORT_LOCK_FILE = "deep_research/report.lock"


def _get_files(ctx: FileToolContext) -> Tuple[Path, Path]:
    search_file = ctx.resolve_under_workspace(SEARCH_RESULTS_FILE)
    report_file = ctx.resolve_under_workspace(REPORT_FILE)
    return search_file, report_file


def _get_locks(ctx: FileToolContext) -> Tuple[Path, Path]:
    search_lock = ctx.resolve_under_workspace(SEARCH_LOCK_FILE)
    report_lock = ctx.resolve_under_workspace(REPORT_LOCK_FILE)
    return search_lock, report_lock


def _load_search_results(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_search_results(file_path: Path, data: Dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _format_search_result(url: str, data: Dict[str, Any], concise: bool) -> str:
    keys = data.get("highlight_keys", [])
    highlight_str = f" [IMPORTANT MATCHES: {', '.join(keys)}]" if keys else ""
    
    if concise:
        return (
            f"URL: {url}{highlight_str}\n"
            f"Title: {data.get('title', '')}\n"
            f"Abstract: {data.get('abs', '')}\n"
            f"{'-' * 40}"
        )
    else:
        return (
            f"URL: {url}{highlight_str}\n"
            f"Title: {data.get('title', '')}\n"
            f"Abstract: {data.get('abs', '')}\n"
            f"Detail: {data.get('detail', '')}\n"
            f"{'-' * 40}"
        )


def search_save_result(
    url: Annotated[str, ParamMeta(description="URL of the search result (used as key)")],
    title: Annotated[str, ParamMeta(description="Title of the search result")],
    abs: Annotated[str, ParamMeta(description="Abstract/Summary of the content")],
    detail: Annotated[str, ParamMeta(description="Detailed content")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Save or update a search result.
    """
    ctx = FileToolContext(_context)
    search_file, _ = _get_files(ctx)
    search_lock, _ = _get_locks(ctx)
    
    with FileLock(search_lock):
        data = _load_search_results(search_file)
        current = data.get(url, {})
        
        # Preserve existing keys if updating
        highlight_keys = current.get("highlight_keys", [])
        
        data[url] = {
            "title": title,
            "abs": abs,
            "detail": detail,
            "highlight_keys": highlight_keys,
        }
        
        _save_search_results(search_file, data)
    return f"Saved result for {url}"


def search_load_all(
    # concise: Annotated[bool, ParamMeta(description="If True, only show concise information")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Load all saved search results.
    """
    ctx = FileToolContext(_context)
    search_file, _ = _get_files(ctx)
    search_lock, _ = _get_locks(ctx)

    with FileLock(search_lock):
        data = _load_search_results(search_file)
    
    if not data:
        return "No search results found."
        
    results = []
    for url, content in data.items():
        results.append(_format_search_result(url, content, concise=True))
        
    return "\n\n".join(results)


def search_load_by_url(
    url: Annotated[str, ParamMeta(description="URL to retrieve")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Load a specific search result by URL.
    """
    ctx = FileToolContext(_context)
    search_file, _ = _get_files(ctx)
    search_lock, _ = _get_locks(ctx)

    with FileLock(search_lock):
        data = _load_search_results(search_file)
    
    if url not in data:
        return f"No result found for {url}"
        
    return _format_search_result(url, data[url], concise=False)


def search_high_light_key(
    url: Annotated[str, ParamMeta(description="URL to highlight keys for")],
    keys: Annotated[List[str], ParamMeta(description="List of keys/terms to highlight")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Save highlighted keys for a specific search result.
    """
    ctx = FileToolContext(_context)
    search_file, _ = _get_files(ctx)
    search_lock, _ = _get_locks(ctx)

    with FileLock(search_lock):
        data = _load_search_results(search_file)
        
        if url not in data:
            return f"URL {url} not found in results. Please save it first."
        
        current_keys = set(data[url].get("highlight_keys", []))
        current_keys.update(keys)
        data[url]["highlight_keys"] = list(current_keys)
        
        _save_search_results(search_file, data)
    return f"Updated highlights for {url}: {list(current_keys)}"


# Report Helpers

def _read_report_lines(file_path: Path) -> List[str]:
    if not file_path.exists():
        return []
    return file_path.read_text(encoding="utf-8").splitlines()


def _save_report(file_path: Path, lines: List[str]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure final newline
    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    file_path.write_text(content, encoding="utf-8")


def _parse_header(line: str) -> Tuple[int, str]:
    """Returns (level, title) if line is a header, else (0, "")."""
    match = re.match(r"^(#+)\s+(.+)$", line)
    if match:
        return len(match.group(1)), match.group(2).strip()
    return 0, ""


def _find_chapter_range(lines: List[str], title_path: str) -> Tuple[int, int]:
    """
    Find the start and end indices (inclusive, exclusive) of a chapter.
    title_path is like "Chapter 1/Section 2"
    """
    titles = [t.strip() for t in title_path.split("/")]
    current_level_idx = 0
    start_idx = -1
    
    # We need to find the sequence of headers
    search_start = 0
    
    for i, target_title in enumerate(titles):
        found = False
        
        for idx in range(search_start, len(lines)):
            level, text = _parse_header(lines[idx])
            if level > 0 and text == target_title:
                # Found the current segment
                search_start = idx + 1
                found = True
                if i == len(titles) - 1:
                    start_idx = idx
                    current_level_idx = level
                break
        
        if not found:
            return -1, -1

    if start_idx == -1:
        return -1, -1
        
    # Find end: next header of same or lower level (higher importance, smaller integer)
    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        level, _ = _parse_header(lines[idx])
        if level > 0 and level <= current_level_idx:
            end_idx = idx
            break
            
    return start_idx, end_idx


def report_read(
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Read the current content of the report.
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)
    
    with FileLock(report_lock):
        if not report_file.exists():
            return "Report is empty."
        return report_file.read_text(encoding="utf-8")


def report_read_chapter(
    title: Annotated[str, ParamMeta(description="Chapter title to read (supports multi-level index e.g. 'Intro/Background')")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Read the content of a specific chapter.
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)
    
    with FileLock(report_lock):
        lines = _read_report_lines(report_file)
        
        start, end = _find_chapter_range(lines, title)
        if start == -1:
            return f"Chapter '{title}' not found."
            
        # Return content (excluding header)
        # start is the header line, so start+1
        return "\\n".join(lines[start+1:end])


def report_outline(
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Get the outline of the report (headers).
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)

    with FileLock(report_lock):
        lines = _read_report_lines(report_file)
    
    outline = []
    for line in lines:
        level, title = _parse_header(line)
        if level > 0:
            outline.append(f"{'#' * level} {title}")
            
    if not outline:
        return "No headers found in report."
    return "\n".join(outline)


def report_create_chapter(
    title: Annotated[str, ParamMeta(description="Chapter title (supports 'Parent/NewChild' to insert into existing). Use '|' to specify insertion point e.g. 'Prev|New' to insert after 'Prev', or '|New' to insert at start.")],
    level: Annotated[int, ParamMeta(description="Header level (1-6)")],
    content: Annotated[str, ParamMeta(description="Content of the chapter")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Create a new chapter in the report.
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)

    with FileLock(report_lock):
        lines = _read_report_lines(report_file)
        
        # Check for routing path
        parent_path = None
        display_title = title
        p_start, p_end = -1, len(lines)

        if "/" in title:
            # Handle recursive "Parent/Child" structure, where Child might contain "|"
            parent_path, new_title = title.rsplit("/", 1)
            p_start, p_end = _find_chapter_range(lines, parent_path)
            
            if p_start == -1:
                return f"Parent chapter '{parent_path}' not found. Cannot create '{new_title}' inside it."
            
            display_title = new_title

        # Check for "|" syntax in the leaf title
        insert_after_target = None # None means append, "" means start, "str" means after that chapter
        if "|" in display_title:
            target, real_title = display_title.split("|", 1)
            display_title = real_title
            insert_after_target = target
        
        # Determine insertion index
        insert_idx = -1
        
        if insert_after_target is not None:
            if insert_after_target == "":
                # Insert at the beginning of the context
                if parent_path:
                    # Inside parent: Insert after parent header (and its intro text), before first subchapter
                    insert_idx = p_end # Default to appending if no subchapters found
                    
                    # Scan for first header inside parent
                    for idx in range(p_start + 1, len(lines)):
                        if idx >= p_end:
                            break
                        lvl, _ = _parse_header(lines[idx])
                        if lvl > 0:
                            insert_idx = idx
                            break
                else:
                    # Top level: Insert at start of file
                    insert_idx = 0
            else:
                # Insert after the specified chapter
                # If we are inside a parent, the target must be relative to the parent?
                # The user requirement says "Prev|New". 
                # If inside "Parent", "Prev" should be a sibling inside "Parent".
                
                search_target = insert_after_target
                if parent_path:
                     # Construct full path for search if we are scoped
                     search_target = f"{parent_path}/{insert_after_target}"
                
                a_start, a_end = _find_chapter_range(lines, search_target)
                if a_start == -1:
                    return f"Target chapter '{search_target}' not found."
                insert_idx = a_end
        else:
            # Default: Append to parent context or file end
            insert_idx = p_end if parent_path else len(lines)
        
        header = f"{'#' * level} {display_title}"
        new_section = [header] + content.splitlines() + [""]
        
        # Insert
        lines[insert_idx:insert_idx] = new_section
        
        _save_report(report_file, lines)
    
    final_path = f"{parent_path}/{display_title}" if parent_path else display_title
    return f"Created chapter '{final_path}' at level {level}"


def report_rewrite_chapter(
    title: Annotated[str, ParamMeta(description="Chapter title to rewrite (supports multi-level index e.g. 'Intro/Background')")],
    content: Annotated[str, ParamMeta(description="New content")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Rewrite the content of an existing chapter.
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)

    with FileLock(report_lock):
        lines = _read_report_lines(report_file)
        
        start, end = _find_chapter_range(lines, title)
        if start == -1:
            return f"Chapter '{title}' not found."
        
        # Keep the header, replace the body
        # new body should not contain the header itself, just the content
        new_body = [lines[start]] + content.splitlines() + [""]
        
        # Replace slice
        lines[start:end] = new_body
        
        _save_report(report_file, lines)
    return f"Rewrote chapter '{title}'"


def report_continue_chapter(
    title: Annotated[str, ParamMeta(description="Chapter title to append to (supports multi-level index e.g. 'Intro/Background')")],
    content: Annotated[str, ParamMeta(description="Content to append")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Append content to an existing chapter.
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)

    with FileLock(report_lock):
        lines = _read_report_lines(report_file)
        
        start, end = _find_chapter_range(lines, title)
        if start == -1:
            return f"Chapter '{title}' not found."
            
        # Append content before 'end' (which is the start of next section or end of file)
        new_lines = content.splitlines() + [""]
        lines[end:end] = new_lines
        
        _save_report(report_file, lines)
    return f"Appended content to chapter '{title}'"


def report_reorder_chapters(
    new_order: Annotated[List[str], ParamMeta(description="List of chapter titles in the new desired order")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Reorder chapters in the report.
    This swaps the positions of the specified chapters, preserving their content and valid text between them.
    All specified chapters must exist and must not overlap (e.g. cannot reorder a parent and its child).
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)

    with FileLock(report_lock):
        lines = _read_report_lines(report_file)
        
        # 1. Find all ranges
        chapters = [] # (index in new_order, title, start, end)
        for i, title in enumerate(new_order):
            s, e = _find_chapter_range(lines, title)
            if s == -1:
                return f"Chapter '{title}' not found."
            chapters.append({
                "target_order_idx": i,
                "title": title,
                "content": lines[s:e],
                "start": s,
                "end": e
            })
        
        # 2. Sort by original position in file to identify slots
        chapters_sorted_by_pos = sorted(chapters, key=lambda x: x["start"])
        
        # 3. Validation: Check for overlaps
        for i in range(len(chapters_sorted_by_pos) - 1):
            curr = chapters_sorted_by_pos[i]
            next_ch = chapters_sorted_by_pos[i+1]
            if curr["end"] > next_ch["start"]:
                return f"Chapters '{curr['title']}' and '{next_ch['title']}' overlap. Cannot reorder nested or overlapping chapters."
        
        # 4. Construct new line list
        result_lines = []
        current_idx = 0
        
        for k, original_slot_holder in enumerate(chapters_sorted_by_pos):
            # Append text before this slot
            result_lines.extend(lines[current_idx : original_slot_holder["start"]])
            
            # Append the content of the chapter that belongs in this k-th slot
            # The slot sequence corresponds to the input list order
            desired_chapter = chapters[k]
            result_lines.extend(desired_chapter["content"])
            
            current_idx = original_slot_holder["end"]
        
        # Append remaining file content
        result_lines.extend(lines[current_idx:])
        
        _save_report(report_file, result_lines)
        
    return "Reordered chapters successfully."


def report_del_chapter(
    title: Annotated[str, ParamMeta(description="Chapter title to delete (supports multi-level index e.g. 'Intro/Background')")],
    _context: Dict[str, Any] | None = None,
) -> str:
    """
    Delete a chapter and its content.
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)

    with FileLock(report_lock):
        lines = _read_report_lines(report_file)
        
        start, end = _find_chapter_range(lines, title)
        if start == -1:
            return f"Chapter '{title}' not found."
            
        del lines[start:end]
        
        _save_report(report_file, lines)
    return f"Deleted chapter '{title}'"

def report_export_pdf(
    _context: Dict[str, Any] | None = None,
) -> List[MessageBlock]:
    """
    Export the report to PDF.
    """
    ctx = FileToolContext(_context)
    _, report_file = _get_files(ctx)
    _, report_lock = _get_locks(ctx)

    with FileLock(report_lock):
        if not report_file.exists():
            raise FileNotFoundError("Report file does not exist.")
        text = report_file.read_text(encoding="utf-8")

    text = re.sub(r"([^\n])\n(#{1,6}\s)", r"\1\n\n\2", text)
    text = re.sub(r"(?m)^(?!\s*(?:[*+-]|\d+\.)\s)(.+)\n(\s*(?:[*+-]|\d+\.)\s)", r"\1\n\n\2", text)

    try:
        import markdown
        from xhtml2pdf import pisa
    except ImportError:
        raise ImportError(
            "Error: strict dependencies 'markdown' and 'xhtml2pdf' are missing."
        )

    pdf_file = report_file.with_suffix(".pdf")

    # Convert to HTML
    extensions = ["extra", "codehilite", "nl2br", "tables"]
    html_content = markdown.markdown(text, extensions=extensions)

    styled_html = f"""
        <html>
        <head>
            <style>
                @page {{
                    size: A4;
                    margin: 2cm;
                }}
                body {{ 
                    font-family: sans-serif; 
                    line-height: 1.6; 
                    font-size: 10pt;
                    word-wrap: break-word; 
                    word-break: break-all;
                }}
                h1, h2, h3 {{ 
                    color: #2c3e50; 
                    margin-top: 25px; /* Add spacing above the title */
                    margin-bottom: 15px; 
                    border-bottom: 1px solid #eee; /* Add an underline to the main title for clarity */
                    padding-bottom: 5px;
                }}

                /* --- Table style fixes --- */
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                    border: 1px solid #ddd;
                }}
                th, td {{
                    border: 1px solid #ddd; /* Explicitly add borders */
                    padding: 8px;
                    text-align: left;
                    vertical-align: top;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                    color: #333;
                }}
                /* ------------------ */

                code {{ background-color: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-family: monospace; }}
                pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; }}
                ul, ol {{ margin-top: 8px; margin-bottom: 8px; padding-left: 20px; }}
                li {{ margin-bottom: 4px; }}
                blockquote {{ border-left: 4px solid #ccc; padding-left: 10px; color: #666; margin: 10px 0; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

    # Convert to PDF
    try:
        with open(pdf_file, "wb") as f:
            pisa_status = pisa.CreatePDF(styled_html, dest=f)

        if pisa_status.err:
            raise RuntimeError("Failed to generate PDF: xhtml2pdf error")
    except Exception as e:
        raise RuntimeError(f"Failed to generate PDF: {e}")

    record = ctx.attachment_store.register_file(
        pdf_file,
        kind=MessageBlockType.FILE,
        display_name=pdf_file.name,
        mime_type="application/pdf",
        copy_file=False,
        persist=False,
        deduplicate=True,
        extra={
            "source": "generated_report",
            "workspace_path": str(pdf_file),
        },
    )
    return [record.as_message_block()]
