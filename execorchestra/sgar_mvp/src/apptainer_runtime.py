"""Opt-in Apptainer transport for the existing external execution boundary.

The default Docker executors are unchanged. Only the task's app/tmp directories
are writable mounts; resource source staging and artifact contracts are reused
from JsonLinesExecutionSubstrate. This backend requires an allocated Linux job.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

from .external_worker_runtime import JsonLinesExecutionSubstrate
from .runtime_abstraction import RuntimeInjectionError


class ApptainerRuntimeError(RuntimeInjectionError):
    pass


_VERIFIED_IMAGE_HASHES: dict[tuple, str] = {}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# This helper runs INSIDE the container. Never follow task-created symlinks in
# host Python: a target that is harmless in /app could address a host secret.
_FILE_RPC = r'''
import base64, hashlib, json, pathlib, sys
q = json.load(sys.stdin)
p = pathlib.Path(q['path'])
op = q['operation']
result = {'ok': True, 'return_code': 0, 'stdout': '', 'stderr': ''}
try:
    if op == 'write_text':
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(q['text'], encoding='utf-8')
    elif op == 'exists':
        result.update(ok=p.exists(), exists=p.exists(), return_code=0 if p.exists() else 1)
    elif op == 'artifact_metadata':
        digest = hashlib.sha256(); size = 0
        with p.open('rb') as f:
            for chunk in iter(lambda: f.read(1048576), b''):
                digest.update(chunk); size += len(chunk)
        result.update(content_sha256=digest.hexdigest(), byte_size=size)
    else:
        with p.open('rb') as f:
            data = f.read(q['max_bytes'] + 1)
        if len(data) > q['max_bytes']:
            raise ValueError('file_size_limit')
        if op == 'read_text':
            result['stdout'] = data.decode('utf-8')
        elif op == 'read_bytes':
            result.update(data_base64=base64.b64encode(data).decode('ascii'),
                          byte_size=len(data), content_sha256=hashlib.sha256(data).hexdigest())
        else:
            raise ValueError('unknown_file_operation')
except (OSError, ValueError) as exc:
    result.update(ok=False, return_code=1, error_type=type(exc).__name__, stderr=str(exc))
print(json.dumps(result, ensure_ascii=True))
'''


class ApptainerExecutionSubstrate(JsonLinesExecutionSubstrate):
    """Persistent task files, short-lived contained processes, explicit network.

    `network_env` contains only tool/service settings selected by the operator.
    Control-model keys and ambient APPTAINER_* variables are never inherited.
    Network-enabled calls share the allocated node's network; offline calls get
    a separate network namespace. This is not Docker bridge equivalence.
    """

    def __init__(self, *, image: Path, image_sha256: str, state_dir: Path,
                 run_id: str, trial_id: str, apptainer: Path,
                 tools_prefix: Path, network_allowed: bool = False,
                 network_env: dict[str, str] | None = None,
                 max_output_bytes: int = 2 * 1024 * 1024,
                 max_file_bytes: int = 8 * 1024 * 1024):
        super().__init__(input_stream=io.StringIO(), output_stream=io.StringIO(),
                         run_id=run_id, trial_id=trial_id,
                         network_allowed=network_allowed)
        if sys.platform != "linux" or not os.environ.get("SLURM_JOB_ID"):
            raise ApptainerRuntimeError("allocated_linux_job_required")
        if not re.fullmatch(r"[a-f0-9]{64}", image_sha256):
            raise ApptainerRuntimeError("image_sha256_required")
        self.image = Path(image).resolve(strict=True)
        self.apptainer = Path(apptainer).resolve(strict=True)
        self.tools_prefix = Path(tools_prefix).resolve(strict=True)
        if not self.image.is_file() or not self.apptainer.is_file():
            raise ApptainerRuntimeError("runtime_file_missing")
        before = self.image.stat()
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        identity = (str(self.image), *(getattr(before, field) for field in fields))
        observed_hash = _VERIFIED_IMAGE_HASHES.get(identity)
        if observed_hash is None:
            observed_hash = file_sha256(self.image)
            after = self.image.stat()
            if any(getattr(before, field) != getattr(after, field) for field in fields):
                raise ApptainerRuntimeError("image_changed_during_verification")
            _VERIFIED_IMAGE_HASHES[identity] = observed_hash
        if observed_hash != image_sha256:
            raise ApptainerRuntimeError("image_sha256_mismatch")
        self.image_sha256 = image_sha256
        self._image_stat = self.image.stat()
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.parent.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(mode=0o700, exist_ok=False)
        self.app_dir = self.state_dir / "app"
        self.tmp_dir = self.state_dir / "task-tmp"
        self.private_dir = self.state_dir / "private"
        for directory in (self.app_dir, self.tmp_dir, self.private_dir):
            directory.mkdir(mode=0o700)
        (self.tmp_dir / "home").mkdir(mode=0o700)
        self._mount_stats = {p: p.stat() for p in (self.app_dir, self.tmp_dir)}
        self.network_env = dict(network_env or {})
        self.max_output_bytes = int(max_output_bytes)
        self.max_file_bytes = int(max_file_bytes)
        if self.max_output_bytes < 1024 or self.max_file_bytes < 1024:
            raise ApptainerRuntimeError("invalid_output_limit")
        self._validate_env(self.network_env, operator=True)
        self._ready = False

    @staticmethod
    def _validate_env(values: dict[str, str], *, operator: bool = False) -> None:
        for key, value in values.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", key):
                raise ApptainerRuntimeError("invalid_environment_name")
            if not isinstance(value, str) or "\x00" in value:
                raise ApptainerRuntimeError("invalid_environment_value")
            if key.upper().startswith(("APPTAINER", "SINGULARITY", "LD_")):
                raise ApptainerRuntimeError("runtime_environment_override_forbidden")
            if key.upper() in {"HOME", "PATH", "BASH_ENV", "ENV", "SHELLOPTS"}:
                raise ApptainerRuntimeError("runtime_environment_override_forbidden")
            if not operator and key.lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}:
                raise ApptainerRuntimeError("task_proxy_override_forbidden")

    def _check_identity(self) -> None:
        observed = self.image.stat()
        if any(getattr(observed, field) != getattr(self._image_stat, field)
               for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
            raise ApptainerRuntimeError("image_changed_since_verification")
        for path, expected in self._mount_stats.items():
            current = path.lstat()
            if path.is_symlink() or (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
                raise ApptainerRuntimeError("task_mount_changed")

    def _command(self, argv: list[str], *, network: bool, cwd: str,
                 extra_env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        self._check_identity()
        if not argv or any(not isinstance(a, str) or "\x00" in a for a in argv):
            raise ApptainerRuntimeError("invalid_runtime_argv")
        if network and not self.network_allowed:
            raise ApptainerRuntimeError("TASK_NETWORK_POLICY_DENIED")
        self._validate_env(extra_env)
        task_cwd = self.task_path(cwd)
        # A fresh host environment avoids inherited binds, overlays, Docker
        # credentials and model keys, including prefixed environment injections.
        env = {
            "PATH": ":".join((str(self.tools_prefix / "bin"),
                              str(self.tools_prefix / "sbin"), "/usr/bin", "/bin")),
            "HOME": str(self.private_dir), "LANG": "C.UTF-8",
            "APPTAINER_TMPDIR": str(self.private_dir),
            "APPTAINER_CACHEDIR": str(self.private_dir / "cache"),
        }
        container_env = {"PYTHONDONTWRITEBYTECODE": "1", **extra_env}
        if network:
            container_env.update(self.network_env)
        for key, value in container_env.items():
            env["APPTAINERENV_" + key] = value
        command = [str(self.apptainer), "exec", "--userns", "--containall",
                   "--cleanenv", "--no-eval", "--no-mount", "home,cwd,hostfs,bind-paths",
                   "--drop-caps", "all", "--security", "no-new-privs"]
        if not network:
            command.extend(("--net", "--network", "none"))
        for source, target in ((self.app_dir, "/app"), (self.tmp_dir, "/tmp")):
            if any(char in str(source) for char in (":", ",", "\n")):
                raise ApptainerRuntimeError("unrepresentable_bind_path")
            command.extend(("--bind", f"{source}:{target}:rw"))
        # Apptainer preserves the passwd HOME even with --cleanenv/--no-home.
        # Assign a task-owned home after entering the container so compilers
        # and libraries can cache without seeing or writing the login home.
        command.extend(("--pwd", task_cwd, str(self.image), "/usr/bin/env",
                        "HOME=/tmp/home", "XDG_CACHE_HOME=/tmp/home/.cache", *argv))
        return command, env

    @staticmethod
    def _stop_group(process: subprocess.Popen) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        # A child can outlive the group leader, so do not gate this on poll().
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)

    def _run(self, argv: list[str], *, timeout_sec: float, network: bool = False,
             cwd: str = "/app", extra_env: dict[str, str] | None = None,
             payload: bytes = b"", output_limit: int | None = None) -> dict[str, Any]:
        if not math.isfinite(timeout_sec) or timeout_sec <= 0:
            raise ApptainerRuntimeError("invalid_execution_timeout")
        command, env = self._command(argv, network=network, cwd=cwd, extra_env=extra_env or {})
        limit = output_limit or self.max_output_bytes
        start = time.monotonic()
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        truncated = {"stdout": False, "stderr": False}
        error = None
        with tempfile.TemporaryFile(dir=self.private_dir) as incoming:
            incoming.write(payload); incoming.seek(0)
            process = subprocess.Popen(command, stdin=incoming, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=env, cwd=self.private_dir,
                                       start_new_session=True)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                    while selector.get_map():
                        remaining = timeout_sec - (time.monotonic() - start)
                        if remaining <= 0:
                            error = "RESOURCE_EXECUTION_TIMEOUT"
                            break
                        for key, _ in selector.select(min(remaining, 0.1)):
                            chunk = os.read(key.fileobj.fileno(), 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            name = key.data
                            available = limit - len(buffers[name])
                            buffers[name].extend(chunk[:available])
                            if len(chunk) > available:
                                truncated[name] = True
                                error = "RESOURCE_OUTPUT_LIMIT"
                                break
                        if error:
                            break
                if not error:
                    try:
                        process.wait(timeout=max(0.001, timeout_sec - (time.monotonic() - start)))
                    except subprocess.TimeoutExpired:
                        error = "RESOURCE_EXECUTION_TIMEOUT"
            finally:
                self._stop_group(process)
                process.stdout.close(); process.stderr.close()
        result = {"ok": process.returncode == 0 and error is None,
                  "return_code": process.returncode,
                  "stdout": buffers["stdout"].decode("utf-8", errors="replace"),
                  "stderr": buffers["stderr"].decode("utf-8", errors="replace"),
                  "duration_ms": round((time.monotonic() - start) * 1000),
                  "execution_phase": "resource_execution",
                  "stdout_truncated": truncated["stdout"],
                  "stderr_truncated": truncated["stderr"],
                  "process_cleanup": {"launcher_reaped": process.poll() is not None,
                                      "process_group_signalled": True,
                                      "pid_namespace": True}}
        if error:
            result["error_type"] = error
        # A failed FUSE unmount is an infrastructure problem, not tool success.
        if "ERROR" in result["stderr"] and "cleanup" in result["stderr"].lower():
            result.update(ok=False, error_type="APPTAINER_CLEANUP_FAILED")
        return result

    def call(self, operation: str, *, timeout_sec: int = 30, **arguments: Any) -> dict:
        with self._lock:
            self.sequence += 1
            if operation == "exec_argv":
                result = self._run(list(arguments.get("argv") or []), timeout_sec=float(timeout_sec),
                                   network=bool(arguments.get("network_required", False)),
                                   cwd=arguments.get("cwd", "/app"),
                                   extra_env=dict(arguments.get("extra_env") or {}))
            elif operation in {"write_text", "read_text", "read_bytes", "exists", "artifact_metadata"}:
                query = {"operation": operation, "path": self.task_path(arguments.get("path", "")),
                         "max_bytes": self.max_file_bytes}
                if operation == "write_text":
                    content = arguments.get("text")
                    if not isinstance(content, str) or len(content.encode("utf-8")) > self.max_file_bytes:
                        raise ApptainerRuntimeError("invalid_file_payload")
                    query["text"] = content
                transport = self._run(["python3", "-c", _FILE_RPC], timeout_sec=float(timeout_sec),
                                      payload=json.dumps(query).encode("utf-8"),
                                      output_limit=self.max_file_bytes * 6 + 4096)
                result = transport
                if transport["ok"]:
                    try:
                        response = json.loads(transport["stdout"])
                    except ValueError as exc:
                        raise ApptainerRuntimeError("invalid_file_rpc_response") from exc
                    if not isinstance(response, dict) or type(response.get("ok")) is not bool:
                        raise ApptainerRuntimeError("invalid_file_rpc_response")
                    result = {**transport, **response}
            else:
                raise ApptainerRuntimeError("unsupported_runtime_operation")
            # Audit metadata is useful; credential env, generated content and raw
            # stdout do not belong in a second persistent transport log.
            request = {"operation": operation, "action_id": f"{self.runtime_id}:{self.sequence}",
                       "timeout_sec": timeout_sec}
            for key in ("logical_step_id", "depends_on", "bindings", "path", "network_required"):
                if key in arguments:
                    request[key] = arguments[key]
            recorded_result = {k: v for k, v in result.items()
                               if k not in {"stdout", "stderr", "data_base64"}}
            self.records.append({"request": request, "result": recorded_result})
            return result

    def require_pipeline_ready(self) -> None:
        if self._ready:
            self._check_identity()
            return
        probe = self.call("exec_argv", argv=["python3", "-c",
            "import json,os,pathlib; "
            "print(json.dumps({'cwd':os.getcwd(),'app':pathlib.Path('/app').is_dir(),"
            "'task_tmp':pathlib.Path('/tmp').is_dir()}))"])
        if not probe["ok"]:
            raise ApptainerRuntimeError("apptainer_preflight_failed:" + str(probe.get("error_type", probe["return_code"])))
        observed = json.loads(probe["stdout"])
        if observed != {"cwd": "/app", "app": True, "task_tmp": True}:
            raise ApptainerRuntimeError("apptainer_preflight_invalid")
        self._ready = True

    async def execute(self, *, prepared: Any, request: Any):
        result = await super().execute(prepared=prepared, request=request)
        result.cost_metric.update(runtime_backend="apptainer", runtime_image_sha256=self.image_sha256)
        return result
