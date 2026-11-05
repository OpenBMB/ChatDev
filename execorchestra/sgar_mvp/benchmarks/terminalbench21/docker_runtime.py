"""Persistent official Terminal-Bench task container and verifier runtime."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import posixpath
import re
import shlex
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

from .task_loader import TerminalBenchTask
from ...src.runtime_abstraction import RuntimeInjectionError, normalize_task_runtime_path


class TaskRuntimeError(RuntimeError):
    pass


def _declared_ctrf_path(test_script: Path) -> str | None:
    """Observe the official script's report declaration; never edit its tests."""
    match = re.search(r"--ctrf(?:\s+|=)(/[A-Za-z0-9_./-]+)", test_script.read_text())
    return match.group(1) if match else None


def _test_report_completed(report: Any) -> bool:
    """A reward file alone cannot prove that the declared pytest run happened."""
    if not isinstance(report, dict):
        return False
    results = report.get("results")
    if not isinstance(results, dict):
        return False
    summary = results.get("summary")
    if not isinstance(summary, dict):
        return False
    count = summary.get("tests")
    return isinstance(count, int) and not isinstance(count, bool) and count > 0


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def experiment_proxy() -> dict[str, str]:
    """Resolve container proxy values without exposing credentials in records."""
    values = _parse_env_file(Path("/etc/sgar/experiment-network.env"))
    host_proxy = os.environ.get("SGAR_DOCKER_PROXY") or values.get("SGAR_DOCKER_PROXY")
    if not host_proxy:
        relay_port = values.get("SGAR_DOCKER_RELAY_PORT", "7894")
        try:
            gateway = subprocess.run(
                ["docker", "network", "inspect", "bridge", "-f", "{{(index .IPAM.Config 0).Gateway}}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise TaskRuntimeError("docker_bridge_gateway_unavailable") from exc
        host_proxy = f"http://{gateway}:{relay_port}"
    no_proxy = os.environ.get("SGAR_NO_PROXY") or values.get(
        "SGAR_NO_PROXY", "localhost,127.0.0.1,::1"
    )
    return {
        "HTTP_PROXY": host_proxy,
        "HTTPS_PROXY": host_proxy,
        "http_proxy": host_proxy,
        "https_proxy": host_proxy,
        "NO_PROXY": no_proxy,
        "no_proxy": no_proxy,
    }


LOGICAL_TASK_ROOT = "/app"


def _task_command_script(argv: list[str]) -> str:
    """Transport large Python argv without an OS-sized argument atom.

    Restore the same script, argv and import path in a fresh interpreter. The
    payload is data in a private temporary file, never interpolated Python.
    Non-Python commands retain their ordinary process interface.
    """
    command = shlex.join(argv)
    if (len(command.encode("utf-8")) < 65536 or len(argv) < 2
            or not Path(argv[0]).name.startswith("python") or not argv[1].endswith(".py")):
        return command
    token = uuid.uuid4().hex
    path = "/tmp/sgar-resource-runtime/argv-" + token + ".json"
    delimiter = "SGAR_ARGV_" + token
    bootstrap = (
        "import json,os,runpy,sys; "
        "a=json.load(open(sys.argv[1],encoding='utf-8')); "
        "sys.argv=a[1:]; sys.path.insert(0,os.path.dirname(os.path.abspath(a[1]))); "
        "runpy.run_path(a[1],run_name='__main__')"
    )
    return (f"(umask 077; cat > {shlex.quote(path)} <<'{delimiter}'\n"
            + json.dumps(argv, ensure_ascii=False) + f"\n{delimiter}\n"
            + shlex.join([argv[0], "-c", bootstrap, path]) + " </dev/null\n"
            + f"sgar_exit=$?; rm -f {shlex.quote(path)}; exit $sgar_exit)")


def _valid_task_path(path: str) -> str:
    """Validate a canonical path in the isolated task filesystem."""
    try:
        normalized = normalize_task_runtime_path(path)
    except RuntimeInjectionError as exc:
        raise TaskRuntimeError("task_container_path_invalid") from exc
    if not path.startswith("/") or normalized != path:
        raise TaskRuntimeError("task_container_path_invalid")
    return normalized


def _valid_image_working_dir(path: str | None) -> str:
    """Return a safe absolute WorkingDir from image metadata.

    A task image may use ``/workspace`` (as prove-plus-comm does) or another
    image-local absolute directory.  Host paths, traversal and filesystem
    roots refer to the task container, including its valid root WorkingDir.
    """

    text = str(path or "").strip() or LOGICAL_TASK_ROOT
    normalized = posixpath.normpath(text)
    if (
        "\x00" in text
        or "\\" in text
        or not text.startswith("/")
        or normalized != text
    ):
        raise TaskRuntimeError("task_image_working_dir_invalid")
    return normalized


_COMMAND_CLEANUP = r"""
sgar_record_file=$1
sgar_proc_info() {
    IFS= read -r sgar_proc_stat < "/proc/$1/stat" 2>/dev/null || return 1
    sgar_proc_tail=${sgar_proc_stat##*) }
    set -- $sgar_proc_tail
    sgar_parent_pid=$2
    shift 19
    printf '%s %s' "$sgar_parent_pid" "$1"
}
read -r sgar_root_pid sgar_root_start < "$sgar_record_file" 2>/dev/null || exit 2
sgar_root_info=$(sgar_proc_info "$sgar_root_pid") || exit 0
[ "${sgar_root_info##* }" = "$sgar_root_start" ] || exit 2
sgar_process_rows=''
for sgar_stat_path in /proc/[0-9]*/stat; do
    sgar_row_pid=${sgar_stat_path#/proc/}; sgar_row_pid=${sgar_row_pid%/stat}
    sgar_row_info=$(sgar_proc_info "$sgar_row_pid") || continue
    sgar_process_rows="${sgar_process_rows}${sgar_row_pid} ${sgar_row_info}
"
done
sgar_descendants() (
    sgar_parent=$1
    printf '%s' "$sgar_process_rows" | while read -r sgar_pid sgar_ppid sgar_start; do
        if [ "$sgar_ppid" = "$sgar_parent" ] && [ "$sgar_pid" != "$$" ]; then
            sgar_descendants "$sgar_pid"
            printf '%s %s\n' "$sgar_pid" "$sgar_start"
        fi
    done
)
sgar_targets="$(sgar_descendants "$sgar_root_pid")
$sgar_root_pid $sgar_root_start"
for sgar_signal in TERM KILL; do
    printf '%s\n' "$sgar_targets" | while read -r sgar_pid sgar_start; do
        sgar_current=$(sgar_proc_info "$sgar_pid") || continue
        if [ "${sgar_current##* }" = "$sgar_start" ] && [ "$sgar_pid" != "$$" ]; then
            kill -"$sgar_signal" "$sgar_pid" 2>/dev/null || :
        fi
    done
    [ "$sgar_signal" != TERM ] || sleep 1
done
rm -f "$sgar_record_file"
"""


class DockerTaskRuntime:
    """One persistent task-facing Docker container per TB trial."""

    def __init__(self, task: TerminalBenchTask, *, trial_id: str, output_dir: Path):
        self.task = task
        self.trial_id = trial_id
        self.output_dir = output_dir
        self.container_id: str | None = None
        self.container_name = "sgar-tb21-" + hashlib.sha256(
            f"{task.task_id}:{trial_id}".encode()
        ).hexdigest()[:20]
        self.proxy = experiment_proxy() if task.allow_internet else {}
        # /app is the stable logical namespace used by compiler/resource
        # contracts; working_dir is the image-specific physical namespace.
        self.logical_working_dir = LOGICAL_TASK_ROOT
        self.working_dir: str | None = None
        self.rpc_records: list[dict[str, Any]] = []

    def _run(self, args: list[str], *, timeout: float, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def _terminate_owned_command(self, record_path: str) -> dict[str, Any]:
        """Cancel only this invocation's recorded process tree inside its container."""
        try:
            cleanup = subprocess.run(
                ["docker", "exec", self._require_started(), "sh", "-c",
                 _COMMAND_CLEANUP, "sgar-command-cleanup", record_path],
                capture_output=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return {"status": "unavailable", "scope": "invocation_process_tree"}
        return {"status": "terminated" if cleanup.returncode == 0 else "unconfirmed",
                "scope": "invocation_process_tree"}

    def image_digest(self) -> str:
        result = self._run(
            ["docker", "image", "inspect", self.task.image, "--format", "{{.Id}}"],
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            from ...src.image_preparation import prepare_image, ImagePreparationError
            try:
                self.image_preparation_receipt = prepare_image(self.task.image)
            except ImagePreparationError as exc:
                raise TaskRuntimeError(f"task_image_preparation_failed:{exc}") from exc
            return self.image_preparation_receipt["image_id"]
        return result.stdout.strip()

    def start(self) -> dict[str, Any]:
        image_digest = self.image_digest()
        args = [
            "docker", "run", "--detach", "--rm", "--name", self.container_name,
            "--label", "sgar.tb21=true",
            "--label", f"sgar.tb21.trial_id={self.trial_id}",
        ]
        if self.task.cpus is not None:
            args.extend(["--cpus", str(self.task.cpus)])
        if self.task.memory_mb is not None:
            args.extend(["--memory", f"{self.task.memory_mb}m"])
        if self.task.gpus:
            args.extend(["--gpus", str(self.task.gpus)])
        if not self.task.allow_internet:
            args.extend(["--network", "none"])
        # Pass names, not values, on argv; values come from the subprocess env.
        for name in self.proxy:
            args.extend(["--env", name])
        args.extend([image_digest, "sh", "-c", "sleep infinity"])
        env = os.environ.copy()
        env.update(self.proxy)
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=60, check=False)
        if result.returncode != 0 or not result.stdout.strip():
            raise TaskRuntimeError(f"task_container_start_failed:{result.stderr[-1000:]}")
        self.container_id = result.stdout.strip()
        inspect = self._run(
            ["docker", "inspect", self.container_id, "--format", "{{json .Config}}"],
            timeout=30,
        )
        if inspect.returncode != 0:
            raise TaskRuntimeError(f"task_container_inspect_failed:{inspect.stderr[-1000:]}")
        try:
            image_config = json.loads(inspect.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise TaskRuntimeError("task_container_inspect_invalid_json") from exc
        self.working_dir = _valid_image_working_dir(image_config.get("WorkingDir"))
        self.exec_argv(
            ["mkdir", "-p", LOGICAL_TASK_ROOT, "/tmp/sgar-resource-runtime", "/logs/verifier"],
            timeout=30,
            cwd="/tmp",
        )
        return {
            "container_id_sha256": hashlib.sha256(self.container_id.encode()).hexdigest(),
            "container_name": self.container_name,
            "image": self.task.image,
            "image_digest": image_digest,
            "image_preparation": getattr(self, "image_preparation_receipt", {"status": "cached", "downloaded": False}),
            "working_dir": self.working_dir,
            "logical_working_dir": self.logical_working_dir,
            "path_mapping": {
                "logical_root": self.logical_working_dir,
                "physical_root": self.working_dir,
            },
            "network_enabled": self.task.allow_internet,
        }

    def _require_started(self) -> str:
        if not self.container_id:
            raise TaskRuntimeError("task_container_not_started")
        return self.container_id

    def _proxy_exports(self) -> str:
        return "; ".join(
            f"export {key}={shlex.quote(value)}" for key, value in self.proxy.items()
        )

    def _physical_path(self, path: str) -> str:
        """Map a validated logical task path into the image namespace."""

        logical = _valid_task_path(path)
        physical_root = self.working_dir or LOGICAL_TASK_ROOT
        if logical == LOGICAL_TASK_ROOT:
            return physical_root
        if logical.startswith(LOGICAL_TASK_ROOT + "/"):
            return posixpath.join(physical_root, logical[len(LOGICAL_TASK_ROOT) + 1:])
        return logical

    def _map_exec_arg(self, value: str) -> str:
        """Map logical POSIX paths while preserving task data arguments.

        Backslashes are valid task data (for example a Windows path that a
        benchmark asks the agent to parse).  They are rejected only by the
        typed task-path validators, never by this generic argv transport.
        """

        text = str(value)
        if "\x00" in text:
            raise TaskRuntimeError("task_exec_argument_invalid")
        if text == LOGICAL_TASK_ROOT or text.startswith(LOGICAL_TASK_ROOT + "/"):
            return self._physical_path(text)
        return text

    def _map_runtime_environment_value(self, name: str, value: str) -> str:
        """Map framework-owned path variables to the same task namespace."""
        if name in {"PYTHONPATH", "SGAR_EXTRA_PYTHONPATH"}:
            return ":".join(self._map_exec_arg(part) for part in str(value).split(":"))
        if name == "SGAR_WORKSPACE_ROOT":
            return self._map_exec_arg(str(value))
        return str(value)

    def exec_argv(
        self,
        argv: list[str],
        *,
        timeout: float = 120,
        extra_env: Mapping[str, str] | None = None,
        cwd: str = "/app",
    ) -> dict[str, Any]:
        container = self._require_started()
        logical_cwd = _valid_task_path(cwd)
        cwd = self._physical_path(logical_cwd)
        if not argv or any("\x00" in str(item) for item in argv):
            raise TaskRuntimeError("task_exec_argv_invalid")
        mapped_argv = [self._map_exec_arg(str(item)) for item in argv]
        extra_env = dict(extra_env or {})
        if any(str(key).lower() in {"http_proxy", "https_proxy", "no_proxy", "all_proxy"} for key in extra_env):
            raise TaskRuntimeError("task_proxy_override_forbidden")
        proxy_exports = self._proxy_exports()
        environment_statements = [proxy_exports] if proxy_exports else []
        for key, value in extra_env.items():
            if not str(key).replace("_", "a").isalnum() or "=" in str(key):
                raise TaskRuntimeError("task_extra_env_name_invalid")
            environment_statements.append(
                f"export {key}={shlex.quote(self._map_runtime_environment_value(str(key), str(value)))}"
            )
        # A command may itself exit with Docker's reserved exit codes. Record
        # that the task shell was reached instead of guessing from stderr or
        # the numeric code. Remove this private transport marker before any
        # observation is returned to the method.
        start_marker = "__sgar_task_exec_" + uuid.uuid4().hex
        record_path = "/tmp/sgar-resource-runtime/command-" + uuid.uuid4().hex + ".pid"
        record_quote = shlex.quote(record_path)
        shell = "; ".join([
            *environment_statements,
            "mkdir -p /tmp/sgar-resource-runtime",
            "IFS= read -r sgar_command_stat < /proc/$$/stat",
            "sgar_command_tail=${sgar_command_stat##*) }",
            "set -- $sgar_command_tail; shift 19",
            f"printf '%s %s\\n' \"$$\" \"$1\" > {record_quote}",
            f"trap {shlex.quote('rm -f ' + record_quote)} EXIT",
            f"printf '%s\\n' {shlex.quote(start_marker)} >&2",
            _task_command_script(mapped_argv),
        ])
        started = time.monotonic()
        # The shell program can be large even when every individual argument
        # is short. Send it through stdin rather than Docker's single -c atom.
        streamed = len(shell.encode("utf-8")) >= 65536
        try:
            process = subprocess.run(
                (["docker", "exec", "-i", "-w", cwd, container, "sh", "-s"]
                 if streamed else ["docker", "exec", "-w", cwd, container, "sh", "-c", shell]),
                **({"input": shell.encode("utf-8")} if streamed else {}),
                capture_output=True,
                text=False,
                timeout=timeout,
                check=False,
            )
        except OSError as exc:
            return {"ok": False, "return_code": None, "stdout": "",
                    "stderr": f"task runtime launch failed: {type(exc).__name__} errno={exc.errno}",
                    "execution_phase": "runtime_launch",
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "stdout_truncated": False, "stderr_truncated": False,
                    "error_type": "RUNTIME_LAUNCH_FAILED"}
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            stderr_bytes = exc.stderr if isinstance(exc.stderr, bytes) else b""
            marker_line = (start_marker + "\n").encode("utf-8")
            task_command_started = stderr_bytes.startswith(marker_line)
            cleanup = self._terminate_owned_command(record_path)
            # Preserve phase evidence already captured by subprocess, without
            # altering timeout status or permitting continuation of unknown effects.
            def safe_partial(value):
                raw = value if isinstance(value, bytes) else str(value or "").encode("utf-8")
                text = raw.decode("utf-8", errors="replace").replace(start_marker, "")
                for secret in self.proxy.values():
                    if secret:
                        text = text.replace(str(secret), "[proxy redacted]")
                raw = text.encode("utf-8")
                return raw[-8192:].decode("utf-8", errors="replace"), len(raw) > 8192
            partial_stdout, stdout_truncated = safe_partial(exc.output)
            partial_stderr, stderr_truncated = safe_partial(
                stderr_bytes[len(marker_line):] if task_command_started else stderr_bytes)
            return {
                "ok": False,
                "return_code": 124,
                "stdout": partial_stdout,
                "stderr": "task command timed out" + ("\n" + partial_stderr if partial_stderr else ""),
                "process_cleanup": cleanup,
                "execution_phase": (
                    "resource_execution" if task_command_started else "runtime_launch"
                ),
                "duration_ms": duration_ms,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
                "error_type": (
                    "RESOURCE_EXECUTION_TIMEOUT"
                    if task_command_started else "RUNTIME_LAUNCH_TIMEOUT"
                ),
            }
        duration_ms = int((time.monotonic() - started) * 1000)
        marker_line = (start_marker + "\n").encode("utf-8")
        task_command_started = process.stderr.startswith(marker_line)
        stderr_bytes = process.stderr[len(marker_line):] if task_command_started else process.stderr
        encoding_error = False
        try:
            stdout = process.stdout.decode("utf-8", errors="strict")
            stderr = stderr_bytes.decode("utf-8", errors="strict")
        except UnicodeError:
            # The RPC carries text. Never silently replace binary bytes or
            # turn a completed command's decoding failure into a pipe crash.
            stdout = ""
            stderr = "resource_text_encoding_unsupported: expected UTF-8 text output"
            encoding_error = True
        return {
            "ok": process.returncode == 0 and not encoding_error,
            "return_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "execution_phase": "resource_execution" if task_command_started else "runtime_launch",
            "duration_ms": duration_ms,
            "stdout_truncated": False,
            "stderr_truncated": False,
            **({"error_type": "RESOURCE_TEXT_ENCODING_UNSUPPORTED"} if encoding_error else {}),
        }

    def write_text(self, path: str, text: str) -> dict[str, Any]:
        logical_path = _valid_task_path(path)
        path = self._physical_path(logical_path)
        container = self._require_started()
        logical_parent = posixpath.dirname(logical_path) or LOGICAL_TASK_ROOT
        # The destination parent may not exist yet.  Use the stable task root
        # as cwd while creating it; using logical_parent here makes docker
        # exec fail before mkdir can run (exit 127 for a missing cwd).
        mkdir = self.exec_argv(
            ["mkdir", "-p", logical_parent],
            timeout=30,
            cwd=LOGICAL_TASK_ROOT,
        )
        if not mkdir.get("ok"):
            return {"ok": False, "return_code": mkdir.get("return_code"),
                    "stderr": mkdir.get("stderr") or "task_parent_create_failed"}
        process = subprocess.run(
            ["docker", "exec", "-i", "-w", self.working_dir or LOGICAL_TASK_ROOT, container, "sh", "-c", f"cat > {shlex.quote(path)}"],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return {"ok": process.returncode == 0, "return_code": process.returncode, "stderr": process.stderr}

    def write_file(self, path: str, source: Path) -> dict[str, Any]:
        """Stage a task file without loading its contents into host memory."""
        logical_path = _valid_task_path(path)
        physical_path = self._physical_path(logical_path)
        container = self._require_started()
        if not source.is_file():
            raise TaskRuntimeError("task_stage_source_missing")
        parent = posixpath.dirname(logical_path) or LOGICAL_TASK_ROOT
        mkdir = self.exec_argv(["mkdir", "-p", parent], timeout=30, cwd=LOGICAL_TASK_ROOT)
        if not mkdir.get("ok"):
            return {"ok": False, "return_code": mkdir.get("return_code"),
                    "stderr": mkdir.get("stderr") or "task_parent_create_failed"}
        copied = self._run(
            ["docker", "cp", str(source), f"{container}:{physical_path}"],
            timeout=120,
        )
        return {"ok": copied.returncode == 0, "return_code": copied.returncode,
                "stderr": copied.stderr}

    def read_text(self, path: str) -> dict[str, Any]:
        logical_path = _valid_task_path(path)
        result = self.exec_argv(["cat", logical_path], timeout=30)
        return result

    def read_bytes(self, path: str) -> dict[str, Any]:
        """Return exact task-workspace bytes through the private RPC channel."""

        logical_path = _valid_task_path(path)
        container = self._require_started()
        process = subprocess.run(
            ["docker", "exec", "-w", self.working_dir or LOGICAL_TASK_ROOT,
             container, "cat", self._physical_path(logical_path)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        payload = bytes(process.stdout or b"")
        stderr = bytes(process.stderr or b"").decode("utf-8", errors="replace")
        return {
            "ok": process.returncode == 0,
            "return_code": process.returncode,
            "stderr": stderr,
            "data_base64": base64.b64encode(payload).decode("ascii"),
            "byte_size": len(payload),
            "content_sha256": hashlib.sha256(payload).hexdigest(),
        }

    def snapshot_task_file(self, path: str, destination: Path, *, max_bytes: int | None = None,
                           authorized_paths: Iterable[str] = ()) -> bool:
        """Copy a regular task-workspace file for public input ingress.

        The benchmark adapter calls this before the worker starts.  The source
        must be in the task workspace or an exact task-declared file verified
        by the adapter before execution; unrelated image files stay excluded.
        """
        logical = _valid_task_path(path)
        if not logical.startswith(LOGICAL_TASK_ROOT + "/") and logical not in authorized_paths:
            raise TaskRuntimeError("task_snapshot_path_outside_workspace")
        expected_dir = self.output_dir.parent / (self.output_dir.name + ".task-state-source")
        if destination.parent.resolve() != expected_dir.resolve():
            raise TaskRuntimeError("task_snapshot_destination_invalid")
        size = self.exec_argv(["wc", "-c", logical], timeout=15, cwd="/app")
        if not size.get("ok"):
            return False
        try:
            byte_count = int(str(size.get("stdout") or "").split()[0])
        except (IndexError, ValueError):
            return False
        if max_bytes is not None and byte_count > max_bytes:
            return False
        copied = self._run(
            ["docker", "cp", f"{self._require_started()}:{self._physical_path(logical)}",
             str(destination)],
            timeout=30,
        )
        if copied.returncode != 0 or not destination.is_file():
            return False
        if destination.stat().st_size != byte_count or (max_bytes is not None and byte_count > max_bytes):
            destination.unlink(missing_ok=True)
            return False
        return True

    def exists(self, path: str) -> dict[str, Any]:
        logical_path = _valid_task_path(path)
        result = self.exec_argv(["test", "-e", logical_path], timeout=30)
        # `test -e` uses exit code 1 for a normal, negative answer.  Do not
        # turn that expected state into an infrastructure exception.
        if result.get("return_code") == 1:
            return {**result, "ok": False, "exists": False}
        if result.get("ok"):
            result["exists"] = True
        return result

    def artifact_metadata(self, path: str) -> dict[str, Any]:
        logical_path = _valid_task_path(path)
        path = self._physical_path(logical_path)
        result = self.exec_argv(
            ["sh", "-c", f"test -f {shlex.quote(path)} && sha256sum {shlex.quote(path)} && wc -c < {shlex.quote(path)}"],
            timeout=30,
        )
        if not result["ok"]:
            return result
        lines = [line.strip() for line in (result.get("stdout") or "").splitlines() if line.strip()]
        if len(lines) < 2:
            return {"ok": False, "error_type": "artifact_metadata_malformed"}
        digest = lines[-2].split()[0]
        try:
            size = int(lines[-1])
        except ValueError:
            return {"ok": False, "error_type": "artifact_metadata_size_invalid"}
        return {"ok": True, "content_sha256": digest, "byte_size": size, "stdout": result.get("stdout", "")}

    def verify(self) -> dict[str, Any]:
        container = self._require_started()
        tests_dir = self.task.tests_dir
        mkdir = self.exec_argv(["mkdir", "-p", "/tests"], timeout=30)
        if not mkdir.get("ok"):
            return {"status": "verifier_failure", "detail": "cannot_create_tests_dir"}
        cp1 = subprocess.run(["docker", "cp", f"{tests_dir}/.", f"{container}:/tests/"], capture_output=True, text=True, timeout=60, check=False)
        cp2 = subprocess.run(["docker", "cp", str(self.task.test_script), f"{container}:/tmp/test.sh"], capture_output=True, text=True, timeout=30, check=False)
        if cp1.returncode != 0 or cp2.returncode != 0:
            return {"status": "verifier_failure", "detail": (cp1.stderr or cp2.stderr)[-1000:]}
        started = time.monotonic()
        env_prefix = self._proxy_exports()
        report_path = _declared_ctrf_path(self.task.test_script)
        # This phase runs after method execution. Network retries affect only
        # verifier preparation; the official script and total timeout stay fixed.
        # Remove stale receipts before invocation so a future verifier-only retry
        # cannot accidentally reuse an earlier result.
        receipts = ["/logs/verifier/reward.txt"] + ([report_path] if report_path else [])
        receipt_cleanup = self.exec_argv(["rm", "-f", *receipts], timeout=15)
        if not receipt_cleanup.get("ok"):
            return {"status": "verifier_failure", "detail": "cannot_clear_previous_verifier_receipts"}
        shell = (
            f"{env_prefix}; "
            "export UV_HTTP_TIMEOUT=120 UV_HTTP_RETRIES=3 PIP_DEFAULT_TIMEOUT=60 PIP_RETRIES=3; "
            "if [ -d /etc/apt/apt.conf.d ]; then "
            "printf '%s\\n' 'Acquire::Retries \"3\";' > /etc/apt/apt.conf.d/80sgar-verifier-network; fi; "
            "exec bash /tmp/test.sh"
        )
        try:
            process = subprocess.run(
                ["docker", "exec", "-w", self.working_dir or LOGICAL_TASK_ROOT, container, "sh", "-c", shell],
                capture_output=True,
                text=True,
                timeout=self.task.verifier_timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "verifier_timeout",
                "duration_seconds": time.monotonic() - started,
                "stdout": str(exc.stdout or ""),
                "stderr": str(exc.stderr or ""),
            }
        reward = self.exec_argv(["cat", "/logs/verifier/reward.txt"], timeout=15)
        reward_value: float | None = None
        if reward["ok"]:
            try:
                reward_value = float((reward.get("stdout") or "").strip())
            except ValueError:
                pass
        report = None
        if report_path:
            report_result = self.exec_argv(["cat", report_path], timeout=15)
            if report_result.get("ok"):
                try:
                    report = json.loads(report_result.get("stdout") or "")
                except (ValueError, TypeError):
                    pass
            if isinstance(report, dict):
                (self.output_dir / "verifier_test_report.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
        report_completed = _test_report_completed(report) if report_path else None
        status = "ok" if process.returncode == 0 and reward_value is not None else "verifier_failure"
        if report_completed is False:
            status = "verifier_failure"
        return {
            "status": status,
            "detail": "declared_test_report_missing_or_empty" if report_completed is False else None,
            "reward": reward_value,
            "test_report_declared": report_path is not None,
            "test_report_completed": report_completed,
            "network_preparation": {"uv_http_timeout_sec": 120, "uv_http_retries": 3,
                                    "pip_default_timeout_sec": 60, "pip_retries": 3,
                                    "apt_download_retries": 3},
            "exit_code": process.returncode,
            "duration_seconds": time.monotonic() - started,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }

    def cleanup(self) -> dict[str, Any]:
        if not self.container_id:
            return {"cleaned": True, "container_id": None}
        result = subprocess.run(["docker", "rm", "-f", self.container_id], capture_output=True, text=True, timeout=30, check=False)
        cleaned = result.returncode == 0 or "No such container" in (result.stderr or "")
        return {"cleaned": cleaned, "container_id_sha256": hashlib.sha256(self.container_id.encode()).hexdigest()}

    def handle_rpc(self, request: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation") or "")
        timeout = float(request.get("timeout_sec") or 60)
        if operation == "exec_argv":
            result = self.exec_argv(
                list(request.get("argv") or []), timeout=timeout,
                extra_env=request.get("extra_env") or {},
                cwd=str(request.get("cwd") or "/app"),
            )
        elif operation == "write_text":
            result = self.write_text(str(request.get("path") or ""), str(request.get("text") or ""))
        elif operation == "read_text":
            result = self.read_text(str(request.get("path") or ""))
        elif operation == "read_bytes":
            result = self.read_bytes(str(request.get("path") or ""))
        elif operation == "exists":
            result = self.exists(str(request.get("path") or ""))
        elif operation == "artifact_metadata":
            result = self.artifact_metadata(str(request.get("path") or ""))
        else:
            result = {"ok": False, "error_type": "task_runtime_operation_unknown"}
        recorded_result = dict(result)
        if operation == "read_bytes" and "data_base64" in recorded_result:
            recorded_result["data_base64"] = "<redacted>"
        self.rpc_records.append({"request": dict(request), "result": recorded_result})
        return result
