#!/usr/bin/env python3
"""Read-only, bounded adapter for upstream ripgrep JSON output."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Search a path with ripgrep")
    parser.add_argument("pattern")
    parser.add_argument("root")
    parser.add_argument("--glob", action="append", default=[])
    parser.add_argument("--type", dest="file_type")
    parser.add_argument("--context-lines", type=int, default=0)
    parser.add_argument("--max-matches", type=int, default=1000)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not root.exists() or args.max_matches < 1 or args.max_matches > 10000 or args.context_lines < 0 or args.context_lines > 20:
        print(json.dumps({"status": "error", "tool": "ripgrep", "message": "invalid root or bounds"}))
        return 2
    command = ["rg", "--json", "--color", "never", "--no-heading"]
    if args.context_lines:
        command += ["-C", str(args.context_lines)]
    if args.file_type:
        command += ["--type", args.file_type]
    for glob in args.glob:
        command += ["--glob", glob]
    command += ["--", args.pattern, str(root)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except FileNotFoundError:
        print(json.dumps({"status": "error", "tool": "ripgrep", "message": "rg not available"}))
        return 3
    except subprocess.TimeoutExpired:
        print(json.dumps({"status": "error", "tool": "ripgrep", "message": "timeout after 60s"}))
        return 4
    matches = []
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "match":
            continue
        data = event.get("data") or {}
        path = (data.get("path") or {}).get("text")
        lines = data.get("lines") or {}
        matches.append({"path": path, "line": data.get("line_number"), "text": lines.get("text", "")})
        if len(matches) >= args.max_matches:
            break
    payload = {"status": "success" if proc.returncode in (0, 1) else "tool_error", "tool": "ripgrep", "root": str(root), "matches": matches, "truncated": len(matches) >= args.max_matches, "exit_code": proc.returncode}
    if proc.stderr:
        payload["stderr"] = proc.stderr[:4000]
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if proc.returncode in (0, 1) else proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
