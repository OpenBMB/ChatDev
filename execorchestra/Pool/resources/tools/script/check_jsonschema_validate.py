#!/usr/bin/env python3
"""Offline adapter for the upstream check-jsonschema CLI."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local JSON/YAML instances")
    parser.add_argument("schema_path")
    parser.add_argument("instance_path", nargs="+")
    args = parser.parse_args()
    schema = Path(args.schema_path).resolve()
    instances = [Path(item).resolve() for item in args.instance_path]
    if not schema.is_file() or any(not path.is_file() for path in instances):
        print(json.dumps({"status": "error", "tool": "check-jsonschema", "message": "schema or instance path missing"}))
        return 2
    # Invoke the installed upstream module with the current interpreter so a
    # runtime entrypoint cannot accidentally reference a host shebang path.
    command = [sys.executable, "-m", "check_jsonschema"]
    command += ["--schemafile", str(schema), *(str(path) for path in instances)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except subprocess.TimeoutExpired:
        print(json.dumps({"status": "error", "tool": "check-jsonschema", "message": "timeout after 60s"}))
        return 4
    diagnostics = [line for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]
    payload = {"status": "success" if proc.returncode == 0 else "validation_error", "tool": "check-jsonschema", "valid": proc.returncode == 0, "diagnostics": diagnostics, "exit_code": proc.returncode}
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
