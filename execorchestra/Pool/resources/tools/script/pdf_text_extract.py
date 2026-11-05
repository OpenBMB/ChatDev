"""Extract complete per-page text from a requested PDF page range."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pdfplumber


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def fail(message: str, code: int = 1) -> None:
    emit({"status": "error", "tool": "pdfplumber", "message": message})
    raise SystemExit(code)


def optional_positive(position: int, name: str) -> int | None:
    if len(sys.argv) <= position or not str(sys.argv[position]).strip():
        return None
    try:
        value = int(sys.argv[position])
    except ValueError:
        fail(f"{name} must be an integer", 2)
    if value < 1:
        fail(f"{name} must be at least 1", 2)
    return value


def main() -> int:
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        fail("usage: pdf_text_extract.py <pdf_path> [start_page] [end_page]", 2)
    target = Path(sys.argv[1])
    if not target.is_file():
        fail("pdf_path is not a readable file", 2)
    start_page = optional_positive(2, "start_page") or 1
    end_page = optional_positive(3, "end_page")
    try:
        with pdfplumber.open(target) as document:
            page_count = len(document.pages)
            selected_end = page_count if end_page is None else end_page
            if start_page > selected_end or selected_end > page_count:
                fail(
                    f"requested page range {start_page}-{selected_end} is outside 1-{page_count}",
                    2,
                )
            pages = [
                {
                    "page": number,
                    "text": document.pages[number - 1].extract_text() or "",
                }
                for number in range(start_page, selected_end + 1)
            ]
    except (OSError, ValueError) as exc:
        fail(f"{type(exc).__name__}: {exc}")
    emit(
        {
            "status": "success",
            "tool": "pdfplumber",
            "page_count": page_count,
            "range_start": start_page,
            "range_end": selected_end,
            "range_complete": True,
            "pages": pages,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
