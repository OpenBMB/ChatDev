#!/usr/bin/env python3
"""Run Coq's deterministic compiler inside the task container.

The external substrate is responsible for mapping SGAR logical paths to the
image's actual working directory and for rejecting host paths.  This wrapper
therefore validates the task-container path it receives, rather than assuming
that every image uses ``/app`` as its physical working directory.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print(json.dumps({"status": "invalid", "error": "expected source_path [output_path]"}))
        return 2
    source = Path(sys.argv[1]).resolve()
    if not source.is_absolute() or source.suffix.lower() != ".v":
        print(json.dumps({"status": "invalid", "error": "source_path_must_be_coq_v_file"}))
        return 2
    if not source.is_file():
        print(json.dumps({"status": "missing", "error": "source_file_missing"}))
        return 2
    output = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else source.with_suffix(".vo")
    if output.suffix.lower() != ".vo" or output.parent != source.parent:
        print(json.dumps({"status": "invalid", "error": "output_path_must_be_sibling_vo_file"}))
        return 2
    started = time.monotonic()
    try:
        process = subprocess.run(
            ["coqc", source.name],
            cwd=str(source.parent),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except FileNotFoundError:
        print(json.dumps({"status": "failed", "error": "coqc_not_available_in_task_image"}))
        return 127
    except subprocess.TimeoutExpired as exc:
        print(json.dumps({"status": "timeout", "error": "coqc_timeout", "stdout": str(exc.stdout or ""), "stderr": str(exc.stderr or "")}))
        return 124
    payload = {
        "status": "ok" if process.returncode == 0 and output.is_file() else "failed",
        "source_path": str(source),
        "output_path": str(output),
        "produced_files": [str(output)] if output.is_file() else [],
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "ok" else (process.returncode or 1)


if __name__ == "__main__":
    raise SystemExit(main())
