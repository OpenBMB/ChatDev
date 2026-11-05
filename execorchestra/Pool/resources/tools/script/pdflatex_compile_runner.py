#!/usr/bin/env python3
"""Run pdflatex deterministically inside the current task container.

The external substrate supplies task-container paths.  This wrapper never
translates or opens host paths; it compiles one ``.tex`` source in its own
directory and reports the PDF plus compiler log as produced artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print(json.dumps({"status": "invalid", "error": "expected source_path [output_dir]"}))
        return 2
    source = Path(sys.argv[1]).resolve()
    if not source.is_absolute() or source.suffix.lower() != ".tex":
        print(json.dumps({"status": "invalid", "error": "source_path_must_be_tex_file"}))
        return 2
    if not source.is_file():
        print(json.dumps({"status": "missing", "error": "source_file_missing"}))
        return 2
    output_dir = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else source.parent
    if not output_dir.is_dir():
        print(json.dumps({"status": "invalid", "error": "output_dir_must_exist"}))
        return 2
    if output_dir != source.parent:
        print(json.dumps({"status": "invalid", "error": "output_dir_must_match_source_directory"}))
        return 2

    started = time.monotonic()
    try:
        process = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                source.name,
            ],
            cwd=str(source.parent),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except FileNotFoundError:
        print(json.dumps({"status": "failed", "error": "pdflatex_not_available_in_task_image"}))
        return 127
    except subprocess.TimeoutExpired as exc:
        print(json.dumps({
            "status": "timeout",
            "error": "pdflatex_timeout",
            "stdout": str(exc.stdout or ""),
            "stderr": str(exc.stderr or ""),
        }))
        return 124

    pdf = source.with_suffix(".pdf")
    log = source.with_suffix(".log")
    produced = [str(path) for path in (pdf, log) if path.is_file()]
    payload = {
        "status": "ok" if process.returncode == 0 and pdf.is_file() else "failed",
        "source_path": str(source),
        "output_path": str(pdf),
        "produced_files": produced,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "ok" else (process.returncode or 1)


if __name__ == "__main__":
    raise SystemExit(main())
