"""Bounded process capture and Docker-call supervision for formal Tool runs."""

from __future__ import annotations

from .direct_network import direct_environment

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


PROCESS_CAPTURE_PROTOCOL = "sgar-process-capture-v1"
NETWORK_POLICY_PROTOCOL = "sgar-network-policy-v1"
DEFAULT_STREAM_LIMIT_BYTES = 256 * 1024 * 1024
MAX_NORMAL_TIMEOUT_SECONDS = 1800


class ProcessSupervisionError(RuntimeError):
    pass


class ProcessOutputLimitExceeded(ProcessSupervisionError):
    def __init__(self, stream_name: str, observed_bytes: int, limit_bytes: int):
        super().__init__("process_output_limit_exceeded")
        self.stream_name = stream_name
        self.observed_bytes = observed_bytes
        self.limit_bytes = limit_bytes


@dataclass(frozen=True)
class NetworkExecutionPolicy:
    mode: str = "disabled"
    allowed_proxy_names: tuple[str, ...] = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    )
    allowed_environment_names: tuple[str, ...] = (
        "LANG",
        "LC_ALL",
        "PYTHONIOENCODING",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "SGAR_EXTRA_PYTHONPATH",
        "HYPOTHESIS_API_TOKEN",
    )

    def __post_init__(self) -> None:
        if self.mode not in {"disabled", "declared"}:
            raise ValueError("network_policy_mode_invalid")
        for name in (*self.allowed_proxy_names, *self.allowed_environment_names):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                raise ValueError("network_policy_environment_name_invalid")

    def permits(self, *, network_required: bool) -> bool:
        return not network_required or self.mode == "declared"


def manifest_tool_environment_allowlist(declared_names: Sequence[str]) -> tuple[str, ...]:
    """Allow only framework defaults and exact variables declared by a Tool manifest."""

    defaults = NetworkExecutionPolicy().allowed_environment_names
    declared = tuple(str(name).strip() for name in declared_names if str(name).strip())
    names = tuple(dict.fromkeys((*defaults, *declared)))
    return NetworkExecutionPolicy(allowed_environment_names=names).allowed_environment_names


@dataclass(frozen=True)
class ProcessCapturePolicy:
    stdout_limit_bytes: int = DEFAULT_STREAM_LIMIT_BYTES
    stderr_limit_bytes: int = DEFAULT_STREAM_LIMIT_BYTES
    chunk_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        if self.stdout_limit_bytes <= 0 or self.stderr_limit_bytes <= 0:
            raise ValueError("process_capture_limit_invalid")
        if not 1024 <= self.chunk_bytes <= 1024 * 1024:
            raise ValueError("process_capture_chunk_invalid")


@dataclass(frozen=True)
class CapturedStream:
    name: str
    data: bytes
    byte_size: int
    sha256: str
    encoding_status: str

    @property
    def text(self) -> str | None:
        if self.encoding_status != "utf-8":
            return None
        return self.data.decode("utf-8", errors="strict")

    def audit(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "byte_size": self.byte_size,
            "sha256": self.sha256,
            "encoding_status": self.encoding_status,
        }


@dataclass(frozen=True)
class SupervisedProcessResult:
    returncode: int
    stdout: CapturedStream
    stderr: CapturedStream
    container_name: str
    container_identity_sha256: str
    cleanup_verified: bool


def _captured_stream(name: str, data: bytes) -> CapturedStream:
    try:
        data.decode("utf-8", errors="strict")
        encoding = "utf-8"
    except UnicodeDecodeError:
        encoding = "binary_or_invalid_utf8"
    return CapturedStream(
        name=name,
        data=data,
        byte_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        encoding_status=encoding,
    )


async def _read_bounded_stream(
    stream: asyncio.StreamReader,
    *,
    name: str,
    limit_bytes: int,
    chunk_bytes: int,
) -> CapturedStream:
    chunks: list[bytes] = []
    observed = 0
    while True:
        chunk = await stream.read(chunk_bytes)
        if not chunk:
            break
        observed += len(chunk)
        if observed > limit_bytes:
            raise ProcessOutputLimitExceeded(name, observed, limit_bytes)
        chunks.append(chunk)
    return _captured_stream(name, b"".join(chunks))


def _safe_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class DockerCallIdentity:
    run_token: str
    call_token: str
    step_token: str
    attempt: int
    container_name: str
    cidfile: str
    identity_sha256: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        call_id: str,
        step_id: str,
        attempt: int,
        control_root: Path,
    ) -> "DockerCallIdentity":
        run_token = _safe_token(run_id)
        call_token = _safe_token(call_id)
        step_token = _safe_token(step_id)
        identity = hashlib.sha256(
            f"{run_token}:{call_token}:{step_token}:{attempt}".encode("utf-8")
        ).hexdigest()
        control_root.mkdir(parents=True, exist_ok=True)
        cidfile = control_root / f"{identity}.cid"
        return cls(
            run_token=run_token,
            call_token=call_token,
            step_token=step_token,
            attempt=attempt,
            container_name=f"sgar-{run_token[:8]}-{call_token[:12]}-{attempt}",
            cidfile=str(cidfile),
            identity_sha256=identity,
        )

    def docker_options(self) -> list[str]:
        return [
            "--name",
            self.container_name,
            "--label",
            f"sgar.run={self.run_token}",
            "--label",
            f"sgar.call={self.call_token}",
            "--label",
            f"sgar.step={self.step_token}",
            "--label",
            f"sgar.attempt={self.attempt}",
            "--cidfile",
            self.cidfile,
        ]


class DockerProcessSupervisor:
    """Own one Docker CLI process and verify call-scoped container cleanup."""

    def __init__(
        self,
        *,
        capture_policy: ProcessCapturePolicy | None = None,
        verify_cleanup: bool = True,
    ) -> None:
        self.capture_policy = capture_policy or ProcessCapturePolicy()
        self.verify_cleanup = bool(verify_cleanup)

    @staticmethod
    async def _control(*argv: str, env: Mapping[str, str]) -> tuple[int, bytes]:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=direct_environment(env),
        )
        output = bytearray()
        if process.stdout is not None:
            while True:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                if len(output) + len(chunk) > 1024 * 1024:
                    process.kill()
                    await process.wait()
                    raise ProcessSupervisionError("docker_control_output_limit")
                output.extend(chunk)
        await asyncio.wait_for(process.wait(), timeout=15)
        return int(process.returncode or 0), bytes(output)

    async def cleanup(
        self,
        identity: DockerCallIdentity,
        *,
        env: Mapping[str, str],
    ) -> bool:
        try:
            await self._control(
                "docker", "rm", "-f", identity.container_name, env=env
            )
        except Exception:
            pass
        if not self.verify_cleanup:
            return True
        try:
            code, output = await self._control(
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"label=sgar.run={identity.run_token}",
                "--filter",
                f"label=sgar.call={identity.call_token}",
                env=env,
            )
            return code == 0 and not output.strip()
        except Exception:
            return False
        finally:
            try:
                Path(identity.cidfile).unlink(missing_ok=True)
            except OSError:
                pass

    async def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        timeout_seconds: int,
        identity: DockerCallIdentity,
    ) -> SupervisedProcessResult:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # The executor already removed inherited proxies and supplied its
            # explicit route. Keep that environment: Docker -e NAME reads it.
            # Re-cleaning here silently strips authorized Tool proxy values.
            env=dict(env),
        )
        if process.stdout is None or process.stderr is None:
            process.kill()
            await process.wait()
            raise ProcessSupervisionError("process_capture_pipe_missing")
        stdout_task = asyncio.create_task(
            _read_bounded_stream(
                process.stdout,
                name="stdout",
                limit_bytes=self.capture_policy.stdout_limit_bytes,
                chunk_bytes=self.capture_policy.chunk_bytes,
            )
        )
        stderr_task = asyncio.create_task(
            _read_bounded_stream(
                process.stderr,
                name="stderr",
                limit_bytes=self.capture_policy.stderr_limit_bytes,
                chunk_bytes=self.capture_policy.chunk_bytes,
            )
        )
        wait_task = asyncio.create_task(process.wait())
        cleanup_verified = True
        try:
            stdout, stderr, _ = await asyncio.wait_for(
                asyncio.gather(stdout_task, stderr_task, wait_task),
                timeout=max(1, min(MAX_NORMAL_TIMEOUT_SECONDS, int(timeout_seconds))),
            )
        except BaseException:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except Exception:
                pass
            cleanup_verified = await self.cleanup(identity, env=env)
            for task in (stdout_task, stderr_task, wait_task):
                if not task.done():
                    task.cancel()
            raise
        if self.verify_cleanup:
            cleanup_verified = await self.cleanup(identity, env=env)
        else:
            try:
                Path(identity.cidfile).unlink(missing_ok=True)
            except OSError:
                pass
        return SupervisedProcessResult(
            returncode=int(process.returncode or 0),
            stdout=stdout,
            stderr=stderr,
            container_name=identity.container_name,
            container_identity_sha256=identity.identity_sha256,
            cleanup_verified=cleanup_verified,
        )


def sanitize_diagnostic(
    text: str,
    *,
    forbidden_values: Sequence[str] = (),
) -> tuple[str, dict[str, Any]]:
    sanitized = text
    replacements = 0
    for value in sorted(
        {str(item) for item in forbidden_values if str(item)},
        key=len,
        reverse=True,
    ):
        if value in sanitized:
            sanitized = sanitized.replace(value, "<redacted>")
            replacements += 1
        alternate = value.replace("\\", "/")
        if alternate != value and alternate in sanitized:
            sanitized = sanitized.replace(alternate, "<redacted>")
            replacements += 1
    encoded = sanitized.encode("utf-8")[:8192]
    safe = encoded.decode("utf-8", errors="ignore")
    return safe, {
        "message_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "sanitized_sha256": hashlib.sha256(safe.encode("utf-8")).hexdigest(),
        "sanitized_bytes": len(safe.encode("utf-8")),
        "redaction_count": replacements,
    }


__all__ = [
    "DEFAULT_STREAM_LIMIT_BYTES",
    "DockerCallIdentity",
    "DockerProcessSupervisor",
    "MAX_NORMAL_TIMEOUT_SECONDS",
    "NETWORK_POLICY_PROTOCOL",
    "NetworkExecutionPolicy",
    "PROCESS_CAPTURE_PROTOCOL",
    "ProcessCapturePolicy",
    "ProcessOutputLimitExceeded",
    "ProcessSupervisionError",
    "sanitize_diagnostic",
]
