"""Extract pipe-table structure from a UTF-8 Markdown file with markdown-it-py."""

from __future__ import annotations

import os
import sys

from markdown_it import MarkdownIt

from _sgar_cli import emit


def extract_tables(source: str) -> list[dict[str, object]]:
    """Parse Markdown table tokens into headers and body rows."""
    tokens = MarkdownIt("commonmark").enable("table").parse(source)
    tables: list[dict[str, object]] = []
    table: dict[str, object] | None = None
    current_row: list[str] | None = None
    current_cell: list[str] | None = None
    in_header = False

    for token in tokens:
        if token.type == "table_open":
            table = {"headers": [], "rows": []}
        elif token.type == "thead_open":
            in_header = True
        elif token.type == "thead_close":
            in_header = False
        elif token.type == "tr_open" and table is not None:
            current_row = []
        elif token.type in {"th_open", "td_open"} and current_row is not None:
            current_cell = []
        elif token.type == "inline" and current_cell is not None:
            current_cell.append(token.content)
        elif token.type in {"th_close", "td_close"} and current_row is not None:
            current_row.append("".join(current_cell or []))
            current_cell = None
        elif token.type == "tr_close" and table is not None and current_row is not None:
            target = "headers" if in_header else "rows"
            table[target].append(current_row)
            current_row = None
        elif token.type == "table_close" and table is not None:
            tables.append(table)
            table = None

    return tables


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python markdown_table_extractor.py <file_path>",
            file=sys.stderr,
        )
        return 1

    path = sys.argv[1]
    if not os.path.isfile(path):
        emit({"status": "error", "message": f"{path} not found"})
        return 2

    try:
        with open(path, encoding="utf-8") as handle:
            tables = extract_tables(handle.read())
    except (OSError, UnicodeError, ValueError) as exc:
        emit(
            {
                "status": "error",
                "tool": "markdown-it-py",
                "target": path,
                "message": f"{type(exc).__name__}: {exc}",
            }
        )
        return 1

    emit(
        {
            "status": "success",
            "tool": "markdown-it-py",
            "target": path,
            "table_count": len(tables),
            "tables": tables,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
