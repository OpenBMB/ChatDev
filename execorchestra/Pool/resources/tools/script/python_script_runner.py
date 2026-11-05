#!/usr/bin/env python3
"""Run a workspace-local Python script and report produced files as JSON."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import argparse
import tempfile
import locale
import signal
from typing import Dict, List


def _workspace_root() -> str:
    return os.path.abspath(os.environ.get("SGAR_WORKSPACE_ROOT") or os.getcwd())


def _resolve_path(value: str, root: str) -> str:
    path = str(value or "").strip().strip("'\"")
    if path.startswith("file://"):
        path = path[len("file://") :]
    workspace_root = os.path.abspath(root)
    host_root = os.environ.get("SGAR_HOST_WORKSPACE_ROOT", "").replace("\\", "/").rstrip("/")
    normalized = path.replace("\\", "/")
    if normalized.startswith("/app/") and os.path.isdir("/app"):
        path = os.path.join("/app", normalized[len("/app/") :])
    elif normalized.startswith("/") and os.path.isdir("/app") and not normalized.startswith("/app/"):
        path = normalized
    elif len(normalized) > 2 and normalized[1:3] == ":/":
        if host_root and normalized.lower().startswith(host_root.lower()):
            suffix = normalized[len(host_root):].lstrip("/")
            path = os.path.join(workspace_root, suffix)
        else:
            return os.path.abspath(os.path.join(os.sep, "__outside_workspace__", normalized[2:].lstrip("/")))
    if not os.path.isabs(path):
        path = os.path.join(workspace_root, path)
    return os.path.abspath(path)


def _is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False


def _snapshot(directory: str) -> Dict[str, float]:
    snapshot: Dict[str, float] = {}
    for current_root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", ".venv", "node_modules"}]
        for name in files:
            path = os.path.join(current_root, name)
            try:
                snapshot[os.path.abspath(path)] = os.path.getmtime(path)
            except OSError:
                continue
    return snapshot


def _changed_files(before: Dict[str, float], directory: str) -> List[str]:
    after = _snapshot(directory)
    changed: List[str] = []
    for path, mtime in after.items():
        if path not in before or mtime > before[path] + 1e-6:
            changed.append(path)
    return sorted(changed)


def _parse_extra_args(raw_args: List[str], arg_json: str = "") -> List[str]:
    if arg_json:
        try:
            parsed = json.loads(arg_json)
            if isinstance(parsed, list):
                return [str(item) for item in parsed] + [str(item) for item in raw_args]
        except json.JSONDecodeError:
            pass
    if not raw_args:
        return []
    if len(raw_args) == 1:
        raw = raw_args[0].strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
    return [str(item) for item in raw_args]


def _run_script(child_argv: List[str], run_cwd: str) -> subprocess.CompletedProcess:
    """Observe the script's exit independently of inherited output descriptors."""
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        proc = subprocess.Popen(
            child_argv, cwd=run_cwd, stdout=stdout_file, stderr=stderr_file,
            start_new_session=(os.name == "posix"),
        )
        try:
            returncode = proc.wait()
        except BaseException:
            if os.name == "posix":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                proc.kill()
            proc.wait()
            raise
        if returncode != 0 and os.name == "posix":
            # This group belongs only to this invocation. A failed script must
            # not leave workers holding its output stream or consuming resources.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        encoding = locale.getpreferredencoding(False)
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read().decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
        stderr = stderr_file.read().decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
        return subprocess.CompletedProcess(child_argv, returncode, stdout, stderr)


def main() -> int:
    start = time.time()
    root = _workspace_root()
    parser = argparse.ArgumentParser()
    parser.add_argument("script_path", nargs="?")
    parser.add_argument("extra_args", nargs="*")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--arg-json", default="")
    args, unknown = parser.parse_known_args()

    if not args.script_path:
        print(json.dumps({"status": "invalid", "error": "missing script_path"}))
        return 2

    script_path = _resolve_path(args.script_path, root)
    if not script_path.endswith(".py"):
        print(json.dumps({"status": "invalid", "error": "script_path must end with .py"}))
        return 2
    if not _is_within(script_path, root):
        print(json.dumps({"status": "blocked", "error": "script_path escaped workspace"}))
        return 2
    if not os.path.isfile(script_path):
        print(json.dumps({"status": "missing", "error": f"script not found: {script_path}"}))
        return 2

    run_cwd = _resolve_path(args.cwd, root) if args.cwd else root
    if not _is_within(run_cwd, root) or not os.path.isdir(run_cwd):
        print(json.dumps({"status": "blocked", "error": f"cwd escaped workspace or is missing: {run_cwd}"}))
        return 2

    before = _snapshot(run_cwd)
    extra_args = _parse_extra_args(args.extra_args + unknown, args.arg_json)
    child_argv = [sys.executable, script_path, *extra_args]
    args_file = None
    try:
        if sum(len(value.encode("utf-8")) + 1 for value in child_argv) >= 65536:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json",
                                             delete=False) as stream:
                args_file = stream.name
                json.dump(child_argv[1:], stream, ensure_ascii=False)
            bootstrap = (
                "import json,os,runpy,sys; "
                "a=json.load(open(sys.argv[1],encoding='utf-8')); "
                "sys.argv=a; sys.path.insert(0,os.path.dirname(os.path.abspath(a[0]))); "
                "runpy.run_path(a[0],run_name='__main__')"
            )
            child_argv = [sys.executable, "-c", bootstrap, args_file]
        proc = _run_script(child_argv, run_cwd)
    finally:
        if args_file is not None:
            os.unlink(args_file)
    produced_files = _changed_files(before, run_cwd)
    payload = {
        "status": "ok" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "script_path": script_path,
        "cwd": run_cwd,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "produced_files": produced_files,
        "latency_ms": int((time.time() - start) * 1000),
    }
    if proc.returncode != 0 and proc.stderr:
        sys.stderr.write(proc.stderr)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return proc.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        print(json.dumps({"status": "timeout", "error": str(exc)}))
        raise SystemExit(124)
