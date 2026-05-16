#!/usr/bin/env python3
"""
DevAll Debug Entry Point
========================
Based on start.ps1, provides a debug-friendly startup with:
  - Backend runs IN-PROCESS (breakpoints work in IDEs)
  - --reload + --log-level debug by default
    - Reload mode uses factory to avoid circular import
  - Frontend as subprocess with proper env
  - Signal handling for graceful shutdown

Usage:
  uv run python start_debug.py                 # default: host=0.0.0.0, port=6400
  uv run python start_debug.py --port 8080     # custom port
  uv run python start_debug.py --no-frontend   # backend only
  uv run python start_debug.py --no-reload     # disable auto-reload
"""

import argparse
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_PORT_DEFAULT = 6400
FRONTEND_PORT_DEFAULT = 5173

# Colors for terminal output
class _C:
    CYAN  = "\033[36m"
    GREEN = "\033[32m"
    YELLOW= "\033[33m"
    RED   = "\033[31m"
    GRAY  = "\033[90m"
    BOLD  = "\033[1m"
    END   = "\033[0m"


def _print(tag: str, msg: str, color: str = _C.GREEN) -> None:
    print(f"  {color}[{tag}]{_C.END} {msg}")


# ---------------------------------------------------------------------------
# Pre-flight checks (mirrors start.ps1 steps 1-6)
# ---------------------------------------------------------------------------
def _check_python() -> None:
    ver = sys.version_info
    if ver.major != 3 or ver.minor < 12:
        _print("ERROR", f"Python 3.12+ required, got {sys.version}", _C.RED)
        sys.exit(1)
    _print("INFO", f"Python: {sys.version.split()[0]}")


def _check_node() -> None:
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=10
        )
        _print("INFO", f"Node.js: {result.stdout.strip()}")
    except FileNotFoundError:
        _print("ERROR", "Node.js not found. Please install Node.js 18+.", _C.RED)
        sys.exit(1)


def _check_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        example = PROJECT_ROOT / ".env.example"
        if example.exists():
            shutil.copy2(example, env_path)
            _print("WARN", ".env created from .env.example — edit API_KEY before using LLM.", _C.YELLOW)
        else:
            _print("ERROR", ".env.example not found. Create .env manually.", _C.RED)
            sys.exit(1)
    else:
        _print("INFO", ".env file found.")


def _check_uv() -> None:
    try:
        subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=10, check=True)
        _print("INFO", "uv is available.")
    except (FileNotFoundError, subprocess.CalledProcessError):
        _print("INFO", "uv not found, installing via pip ...", _C.YELLOW)
        subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True)


def _check_venv() -> None:
    venv_path = PROJECT_ROOT / ".venv"
    if not venv_path.exists():
        _print("INFO", "Virtual environment not found, running uv sync ...", _C.YELLOW)
        subprocess.run(["uv", "sync"], cwd=PROJECT_ROOT, check=True)
    else:
        _print("INFO", "Virtual environment found, skipping uv sync.")


def _check_frontend_deps() -> None:
    node_modules = PROJECT_ROOT / "frontend" / "node_modules"
    if not node_modules.exists():
        _print("INFO", "Frontend node_modules not found, running npm install ...", _C.YELLOW)
        subprocess.run(
            ["npm", "install"],
            cwd=PROJECT_ROOT / "frontend",
            check=True,
        )
    else:
        _print("INFO", "Frontend dependencies found, skipping npm install.")


def preflight() -> None:
    """Run all pre-flight checks."""
    print()
    print(f"  {_C.CYAN}{'=' * 40}{_C.END}")
    print(f"  {_C.CYAN}      DevAll Debug Start{_C.END}")
    print(f"  {_C.CYAN}{'=' * 40}{_C.END}")
    print()

    _check_python()
    _check_node()
    _check_env()
    _check_uv()
    _check_venv()
    _check_frontend_deps()


# ---------------------------------------------------------------------------
# Frontend subprocess
# ---------------------------------------------------------------------------
_frontend_proc: subprocess.Popen | None = None


def _start_frontend(backend_port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = f"http://localhost:{backend_port}"

    proc = subprocess.Popen(
        ["npx", "cross-env", f"VITE_API_BASE_URL=http://localhost:{backend_port}", "npm", "run", "dev"],
        cwd=PROJECT_ROOT / "frontend",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------
def _setup_signals() -> None:
    def _shutdown(signum, frame):
        print()
        _print("STOP", "Received shutdown signal, cleaning up ...", _C.YELLOW)
        if _frontend_proc and _frontend_proc.poll() is None:
            _frontend_proc.terminate()
            try:
                _frontend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _frontend_proc.kill()
        _print("INFO", "All services stopped. Goodbye!", _C.GREEN)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DevAll Debug Entry Point")
    p.add_argument("--host", default="0.0.0.0", help="Backend host (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=BACKEND_PORT_DEFAULT, help=f"Backend port (default: {BACKEND_PORT_DEFAULT})")
    p.add_argument("--log-level", default="debug", choices=["debug", "info", "warning", "error", "critical"])
    p.add_argument("--no-frontend", action="store_true", help="Skip frontend startup (backend only)")
    p.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    p.add_argument("--no-preflight", action="store_true", help="Skip pre-flight dependency checks")
    p.add_argument("--skip-npm", action="store_true", help="Skip npm install check even if node_modules missing")
    return p


def create_app():
    """ASGI app factory for uvicorn (especially reload mode).

    Pre-imports ``runtime.bootstrap.schema`` to break the circular import
    between ``check.check`` and ``runtime.__init__``.  When uvicorn spawns
    a reload subprocess it imports the target directly — without this
    factory, ``server.app`` would be the first import and the circular
    dependency would fire.
    """
    from runtime.bootstrap.schema import ensure_schema_registry_populated
    ensure_schema_registry_populated()
    from server.app import app
    return app


def _trigger_workflow_after_startup(port: int) -> None:
    """Auto-trigger a workflow via the sync API if DEVALL_TRIGGER_* env vars are set."""
    yaml_file = os.environ.get("DEVALL_TRIGGER_WORKFLOW")
    task_prompt = os.environ.get("DEVALL_TRIGGER_TASK")
    if not yaml_file or not task_prompt:
        return

    import urllib.request
    import urllib.error
    import json

    url = f"http://localhost:{port}/api/workflow/execute-sync"
    payload = json.dumps({
        "yaml_file": yaml_file,
        "task_prompt": task_prompt,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )

    _print("TRIGGER", f"Auto-triggering workflow: {yaml_file}", _C.CYAN)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            status = body.get("status", "unknown")
            _print("TRIGGER", f"Workflow result: {status}", _C.GREEN)
            final_msg = body.get("final_message", "")
            if final_msg:
                preview = final_msg[:300] + ("..." if len(final_msg) > 300 else "")
                _print("TRIGGER", f"Output: {preview}", _C.GREEN)
    except urllib.error.HTTPError as e:
        _print("ERROR", f"Trigger failed: HTTP {e.code} - {e.read().decode('utf-8', errors='replace')[:200]}", _C.RED)
    except Exception as e:
        _print("ERROR", f"Trigger failed: {e}", _C.RED)


def _start_trigger_thread(port: int) -> None:
    """Start a background thread that waits for the server then triggers the workflow."""
    yaml_file = os.environ.get("DEVALL_TRIGGER_WORKFLOW")
    if not yaml_file:
        return

    import threading
    import urllib.request
    import urllib.error

    def _wait_and_trigger():
        # Wait for server to be ready
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://localhost:{port}/api/workflows", timeout=2)
                break
            except (urllib.error.URLError, ConnectionRefusedError, OSError):
                time.sleep(1)
        else:
            _print("WARN", "Server did not become ready in 30s, skipping auto-trigger", _C.YELLOW)
            return
        _trigger_workflow_after_startup(port)

    t = threading.Thread(target=_wait_and_trigger, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    args = build_parser().parse_args()

    # Pre-flight checks
    if not args.no_preflight:
        preflight()

    _setup_signals()

    # ------------------------------------------------------------------
    # Start frontend (subprocess)
    # ------------------------------------------------------------------
    global _frontend_proc

    if not args.no_frontend:
        _print("START", f"Launching frontend dev server on port {FRONTEND_PORT_DEFAULT} ...", _C.CYAN)
        _frontend_proc = _start_frontend(args.port)
        time.sleep(1)

    # ------------------------------------------------------------------
    # Start backend IN-PROCESS (debuggable)
    # ------------------------------------------------------------------
    _print("START", f"Launching backend server on {args.host}:{args.port} (debug mode) ...", _C.CYAN)
    print()

    # Set env so server_main picks them up
    os.environ.setdefault("LOG_LEVEL", args.log_level.upper())

    # Ensure log directory
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    import uvicorn
    from server_main import RELOAD_SOURCE_DIRS, RELOAD_EXCLUDES, _watchfiles_available

    reload_enabled = not args.no_reload
    reload_kwargs: dict = {}

    if reload_enabled:
        reload_kwargs = {
            "reload_dirs": list(RELOAD_SOURCE_DIRS),
            "reload_excludes": list(RELOAD_EXCLUDES),
        }
        if not _watchfiles_available():
            _print("WARN", "'watchfiles' not installed — reload-exclude patterns ignored. "
                          "Install with: pip install uvicorn[standard]", _C.YELLOW)

    print(f"  {_C.GREEN}{'=' * 40}{_C.END}")
    print(f"  {_C.GREEN}  Services started successfully!{_C.END}")
    print(f"  {_C.GREEN}{'-' * 40}{_C.END}")
    print(f"  Frontend:  http://localhost:{FRONTEND_PORT_DEFAULT}")
    print(f"  Backend:   http://localhost:{args.port}")
    print(f"  Log level: {args.log_level.upper()}")
    print(f"  Reload:    {'ON' if reload_enabled else 'OFF'}")
    print(f"  {_C.GREEN}{'-' * 40}{_C.END}")
    print(f"  {_C.GRAY}Press Ctrl+C to stop all services{_C.END}")
    print(f"  {_C.GREEN}{'=' * 40}{_C.END}")
    print()

    # Auto-trigger workflow if DEVALL_TRIGGER_* env vars are set
    _start_trigger_thread(args.port)

    # Use factory mode when reload is on so that the subprocess pre-imports
    # runtime.bootstrap.schema BEFORE server.app, breaking the circular import
    # between check.check and runtime.__init__.
    if reload_enabled:
        uvicorn.run(
            "start_debug:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=True,
            log_level=args.log_level,
            ws="wsproto",
            **reload_kwargs,
        )
    else:
        # Non-reload: import in-process so IDE breakpoints work directly.
        app = create_app()
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level=args.log_level,
            ws="wsproto",
        )


if __name__ == "__main__":
    main()
