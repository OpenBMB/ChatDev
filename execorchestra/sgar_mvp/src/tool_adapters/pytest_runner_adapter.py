"""
System-owned pytest runner adapter.

This shim keeps S-GAR compatible with legacy pytest runner manifests without
editing the resource pool. It accepts the same single target path shape and
emits JSON status for the orchestrator semantic gate.
"""

import json
import os
import re
import subprocess
import sys
from typing import Dict


def _workspace_root() -> str:
    return os.path.abspath(os.environ.get("SGAR_WORKSPACE_ROOT") or os.getcwd())


def _host_workspace_root() -> str:
    return os.environ.get("SGAR_HOST_WORKSPACE_ROOT") or ""


def _resolve_path(raw: str) -> str:
    text = str(raw or "").strip().strip("'\"`")
    workspace = _workspace_root()
    host_root = _host_workspace_root()
    if text.startswith("/app/"):
        return os.path.abspath(os.path.join(workspace, text[len("/app/"):]))
    if "\\" in text or re.match(r"^[A-Za-z]:", text):
        raise ValueError("pytest_target_must_use_posix_path")
    if host_root:
        normalized_text = text.lower()
        normalized_host = host_root.lower().rstrip("/")
        if normalized_text.startswith(normalized_host + "/"):
            rel = text[len(normalized_host):].lstrip("/")
            return os.path.abspath(os.path.join(workspace, rel))
    if os.path.isabs(text):
        return os.path.abspath(text)
    return os.path.abspath(os.path.join(workspace, text))


def _parse_summary(output: str) -> Dict[str, int]:
    summary = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for key in tuple(summary.keys()):
        match = re.search(rf"(\d+)\s+{key}", output, flags=re.IGNORECASE)
        if match:
            summary[key] = int(match.group(1))
    return summary


def main() -> int:
    if len(sys.argv) != 2:
        print(
            json.dumps(
                {
                    "status": "error",
                    "exit_code": 2,
                    "summary": {"passed": 0, "failed": 0, "errors": 0, "skipped": 0},
                    "stdout": "",
                    "stderr": "usage: python pytest_runner_adapter.py <target_path>",
                },
                ensure_ascii=False,
            )
        )
        return 0

    target_path = _resolve_path(sys.argv[1])
    if not os.path.exists(target_path):
        print(
            json.dumps(
                {
                    "status": "missing",
                    "exit_code": 2,
                    "summary": {"passed": 0, "failed": 0, "errors": 0, "skipped": 0},
                    "stdout": "",
                    "stderr": f"target_path not found: {sys.argv[1]}",
                },
                ensure_ascii=False,
            )
        )
        return 0

    target_dir = os.path.dirname(target_path)
    artifact_dir = os.path.dirname(target_dir) if os.path.basename(target_dir) == "generated_artifacts" else target_dir
    env = os.environ.copy()
    pythonpath_parts = [target_dir, artifact_dir, _workspace_root()]
    extra_pythonpath = env.get("SGAR_EXTRA_PYTHONPATH", "")
    for item in re.split(r"[;:]", extra_pythonpath):
        if item.strip():
            pythonpath_parts.append(_resolve_path(item))
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(part for part in pythonpath_parts if part)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", target_path, "--tb=short", "-v"],
        cwd=_workspace_root(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = stdout + "\n" + stderr
    summary = _parse_summary(combined)
    if proc.returncode == 0:
        status = "passed"
    elif summary["failed"] or summary["errors"]:
        status = "failed"
    else:
        status = "error"
    print(
        json.dumps(
            {
                "status": status,
                "exit_code": proc.returncode,
                "summary": summary,
                "stdout": stdout,
                "stderr": stderr,
                "effective_pythonpath": env.get("PYTHONPATH", ""),
                "target_path": target_path,
                "cwd": _workspace_root(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
