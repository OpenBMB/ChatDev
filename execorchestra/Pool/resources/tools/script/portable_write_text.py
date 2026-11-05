#!/usr/bin/env python3
"""Write one UTF-8 text artifact inside the task workspace with stdlib only."""

import json
import os
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"status": "error", "reason": "arguments_invalid"}))
        return 2
    configured_root = Path(os.environ.get("SGAR_WORKSPACE_ROOT") or "")
    root = (configured_root if configured_root.is_dir() else Path.cwd()).resolve()
    destination = Path(sys.argv[1])
    if not destination.is_absolute():
        destination = root / destination
    destination = destination.resolve()
    try:
        inside = os.path.commonpath((str(root), str(destination))) == str(root)
    except ValueError:
        inside = False
    if not inside or destination == root:
        print(json.dumps({"status": "error", "reason": "destination_outside_workspace"}))
        return 2
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(sys.argv[2], encoding="utf-8")
    except OSError:
        print(json.dumps({"status": "error", "reason": "write_failed"}))
        return 1
    print(json.dumps({"status": "success", "written": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
