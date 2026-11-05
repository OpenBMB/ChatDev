#!/usr/bin/env python3
"""Read-only DuckDB query adapter with explicit local input references."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb


FORBIDDEN_MUTATION = re.compile(r"\b(attach|copy|create|delete|drop|export|install|insert|load|pragma|replace|set|update|vacuum)\b|https?://", re.I)
FILE_READ = re.compile(r"read_(?:csv|json|parquet)_auto\s*\(\s*'([^']+)'", re.I)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded read-only DuckDB query")
    parser.add_argument("sql")
    parser.add_argument("--input-ref", action="append", default=[])
    parser.add_argument("--output-format", choices=("json", "csv"), default="json")
    parser.add_argument("--max-rows", type=int, default=1000)
    args = parser.parse_args()
    if args.max_rows < 1 or args.max_rows > 10000:
        print(json.dumps({"status": "error", "tool": "duckdb", "message": "max_rows must be 1..10000"}))
        return 2
    refs = {str(Path(item).resolve()) for item in args.input_ref}
    for ref in refs:
        if not Path(ref).is_file():
            print(json.dumps({"status": "error", "tool": "duckdb", "message": f"input_ref not found: {ref}"}))
            return 2
    if FORBIDDEN_MUTATION.search(args.sql):
        print(json.dumps({"status": "error", "tool": "duckdb", "message": "query violates read-only/external-access policy"}))
        return 2
    for match in FILE_READ.finditer(args.sql):
        if str(Path(match.group(1)).resolve()) not in refs:
            print(json.dumps({"status": "error", "tool": "duckdb", "message": "file read is not in input_refs"}))
            return 2
    try:
        # DuckDB must read explicitly supplied local files; the adapter keeps
        # external access bounded by input_refs and rejects remote URLs above.
        con = duckdb.connect(database=":memory:", config={"enable_external_access": True})
        con.execute("SET autoinstall_known_extensions=false")
        con.execute("SET threads=2")
        con.execute("SET memory_limit='256MB'")
        cursor = con.execute(args.sql)
        columns = [item[0] for item in (cursor.description or [])]
        rows = cursor.fetchmany(args.max_rows + 1)
        truncated = len(rows) > args.max_rows
        rows = rows[:args.max_rows]
        result = {"status": "success", "tool": "duckdb", "columns": columns, "rows": [list(row) for row in rows], "row_count": len(rows), "truncated": truncated}
        print(json.dumps(result, ensure_ascii=False, default=str))
        con.close()
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "tool": "duckdb", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
