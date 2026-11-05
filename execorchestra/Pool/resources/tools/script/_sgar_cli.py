"""Shared adapter for S-GAR tool wrappers around recognized open-source CLIs.

Every CLI-backed tool in the pool is a thin, declarative wrapper that invokes
the *real* upstream binary (flake8, shellcheck, rustfmt, stylelint, ...) which
is pre-installed and version-pinned in the sgar-runtime image. The adapter:

  * validates the input path exists,
  * fails loudly (non-zero exit + error JSON) if the upstream tool is missing —
    there is NO simulated fallback,
  * runs the command and returns a uniform JSON envelope with the real exit
    code and (parsed) output.

This keeps each wrapper auditable and reproducible: the substance is the
recognized tool, the wrapper is a standard adapter.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Callable, List, Optional


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def run_cli(
    tool: str,
    argv: List[str],
    *,
    input_path: Optional[str] = None,
    json_native: bool = False,
    timeout: int = 120,
    cwd: Optional[str] = None,
    ok_returncodes=(0, 1),
) -> None:
    """Invoke a recognized CLI and print a uniform JSON envelope.

    tool          binary name (must be resolvable on PATH in the runtime)
    argv          full argument vector, argv[0] == tool
    input_path    optional file/dir that must exist before running
    json_native   parse stdout as JSON (for tools with `-f json` output)
    ok_returncodes return codes that count as a successful *run* (lint findings
                  typically exit 1); anything else is surfaced as a tool error
    """
    if input_path is not None and not os.path.exists(input_path):
        emit({"status": "error", "tool": tool, "message": f"{input_path} not found"})
        sys.exit(2)
    if shutil.which(tool) is None:
        emit({"status": "error", "tool": tool,
              "message": f"{tool} not available in runtime image"})
        sys.exit(3)

    try:
        res = subprocess.run(
            argv, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        emit({"status": "error", "tool": tool, "message": f"timeout after {timeout}s"})
        sys.exit(4)

    parsed = None
    if json_native:
        for stream in (res.stdout, res.stderr):
            if stream and stream.strip():
                try:
                    parsed = json.loads(stream)
                    break
                except json.JSONDecodeError:
                    continue

    envelope = {
        "status": "success" if res.returncode in ok_returncodes else "tool_error",
        "tool": tool,
        "target": input_path,
        "exit_code": res.returncode,
        "result": parsed,
        "stdout": None if parsed is not None else (res.stdout or ""),
        "stderr": res.stderr or None,
    }
    emit(envelope)
    # Propagate a hard tool error so the orchestrator sees a real failure.
    if res.returncode not in ok_returncodes:
        sys.exit(res.returncode)


def first_arg(usage: str) -> str:
    if len(sys.argv) < 2:
        print(usage, file=sys.stderr)
        sys.exit(1)
    return sys.argv[1]
