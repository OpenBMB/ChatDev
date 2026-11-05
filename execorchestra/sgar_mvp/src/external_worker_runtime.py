"""Private pipe RPC usable from SGAR's synchronous and asynchronous code."""
from __future__ import annotations

import ast
import base64
import binascii
import json
import hashlib
import os
import posixpath
import select
import threading
from pathlib import Path
from typing import Any, TextIO

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .capability_operations import (
    CAPABILITY_TO_EXECUTION_OPERATION,
    manifest_capability_operations,
)
from .executors import ExecutionResult
from .execution_contracts import infer_artifact_type_from_path
from .runtime_abstraction import RuntimeInjectionError, normalize_task_runtime_path


class WorkerProtocolError(RuntimeInjectionError):
    pass


def _external_write_receipt(request: Any) -> dict[str, Any]:
    """Project a verified file write into its declared native receipt shape."""

    contract = getattr(request, "resource_native_output_contract", None) or {}
    schema = contract.get("schema") or contract.get("schema_hint") or {}
    required = set(schema.get("required") or []) if isinstance(schema, dict) else set()
    if {"status", "written"} <= required:
        return {"status": "success", "written": True}
    if {"status", "tool", "mcp_server", "mcp_tool", "result"} <= required:
        return {
            "status": "success",
            "tool": request.resource_definition.resource_id,
            "mcp_server": "external_task_substrate",
            "mcp_tool": "write_file",
            "result": {"is_error": False, "content": []},
        }
    raise WorkerProtocolError("external_write_file_receipt_contract_unsupported")


class JsonLinesExecutionSubstrate:
    def __init__(self, *, input_stream: TextIO, output_stream: TextIO,
                 run_id: str, trial_id: str, rpc_timeout: float = 60,
                 network_allowed: bool = False):
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.runtime_id = run_id
        self.trial_id = trial_id
        self.rpc_timeout = rpc_timeout
        self.network_allowed = bool(network_allowed)
        self.sequence = 0
        self._lock = threading.RLock()
        self.records: list[dict[str, Any]] = []
        self._requirement_probe_cache: dict[str, str | None] = {}
        self._python_dependency_paths: dict[str, str] = {}
        self._python_bundle_cache: dict[str, str] = {}
        self._resource_stage_cache: dict[str, tuple[Path, Path, tuple[tuple[str, str, int], ...]]] = {}

    def resource_incompatibility(self, raw_manifest: Any) -> str | None:
        """Check declared Tool dependencies in the actual external task image.

        The control host may have the sealed SGAR image, while a benchmark
        executes Tools in its own image.  Never substitute host readiness for
        task-container readiness when admitting a Tool to a frozen pool.
        """
        if not isinstance(raw_manifest, dict) or raw_manifest.get("resource_type") != "Tool":
            return None
        requirements = raw_manifest.get("runtime_requirements") or {}
        if not isinstance(requirements, dict):
            return "external_runtime_requirements_invalid"
        if self.native_file_rpc(raw_manifest):
            # Native file RPCs never run manifest Python wrappers in the task image.
            return None
        # The exact Python in a reference image is not necessarily the
        # adapter's execution requirement in an externally owned task image.
        # Only an explicit compatibility declaration may replace that pin.
        python_spec = str(requirements.get("python_compatibility")
                          or requirements.get("python") or "")
        try:
            python_versions = SpecifierSet(python_spec)
        except InvalidSpecifier:
            return "external_python_requirement_invalid"
        packages = [
            str(item.get("name") or item.get("package") or "")
            for item in requirements.get("python_packages") or []
            if isinstance(item, dict) and item.get("required", True)
        ]
        commands = [str(item) for item in requirements.get("commands") or []]
        if not python_spec and not packages and not commands:
            return None
        probe = {"python": python_spec, "packages": sorted(packages),
                 "commands": sorted(commands), "package_versions": {
                     str(p.get('name') or p.get('package') or ''): str(p.get('version') or '')
                     for p in requirements.get('python_packages') or []
                     if isinstance(p, dict) and p.get('required', True)}}
        key = json.dumps(probe, sort_keys=True, separators=(",", ":"))
        if key not in self._requirement_probe_cache:
            if not python_spec and not packages:
                # A shell Tool must not require Python merely so SGAR can
                # check its declared task-image commands. Probe each command
                # through the task's POSIX shell, without interpolating the
                # command name into shell source.
                reason = None
                for command in sorted(commands):
                    result = self.call(
                        "exec_argv",
                        argv=["sh", "-c", 'command -v "$1" >/dev/null 2>&1', "sh", command],
                        timeout_sec=30,
                    )
                    if not result.get("ok"):
                        reason = "external_command_unavailable"
                        break
                self._requirement_probe_cache[key] = reason
                return reason
            script = """import importlib.metadata, json, shutil, sys
q = json.loads(sys.argv[1])
bad = []
missing = []
version = '.'.join(map(str, sys.version_info[:3]))
if any(not shutil.which(command) for command in q['commands']):
    bad.append('external_command_unavailable')
for package in q['packages']:
    try:
        importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        bad.append('external_python_package_unavailable')
        missing.append(package)
print(json.dumps({'python_version': version, 'failures': sorted(set(bad)), 'missing_packages': missing}))
"""
            try:
                result = self.call("exec_argv", argv=["python3", "-c", script, key],
                                   timeout_sec=30)
                if not result.get("ok"):
                    reason = "external_python_runtime_unavailable"
                else:
                    observation = json.loads(str(result.get("stdout") or ""))
                    if (observation.get('missing_packages') and (
                        not python_spec or Version(observation['python_version']) in python_versions
                    )):
                        from .external_python_bundle import stage_dependency_bundle
                        path = stage_dependency_bundle(self, requirements=requirements,
                            missing_packages=observation['missing_packages'],
                            python_version=observation['python_version'])
                        if path:
                            result = self.call('exec_argv', argv=['python3','-c',script,key],
                                extra_env={'PYTHONPATH':path}, timeout_sec=30)
                            if result.get('ok'):
                                observation = json.loads(str(result.get('stdout') or ''))
                                if not observation['failures']:
                                    # Per-resource declaration, not a process-global environment.
                                    self._python_dependency_paths[key] = path
                    failures = observation["failures"]
                    if python_spec and Version(observation["python_version"]) not in python_versions:
                        failures.append("external_python_version_mismatch")
                    reason = str(sorted(set(failures))[0]) if failures else None
            except (ValueError, TypeError, KeyError, InvalidVersion):
                reason = "external_runtime_probe_invalid"
            self._requirement_probe_cache[key] = reason
        return self._requirement_probe_cache[key]

    @staticmethod
    def native_file_rpc(raw_manifest: Any) -> bool:
        if not isinstance(raw_manifest, dict) or raw_manifest.get("resource_type") != "Tool":
            return False
        operations = manifest_capability_operations(raw_manifest)
        return bool(operations) and all(
            CAPABILITY_TO_EXECUTION_OPERATION.get(operation) in {"read_file", "write_file"}
            for operation in operations
        )

    def require_pipeline_ready(self) -> None:
        # The Harbor adapter supplies a persistent task root and artifact
        # metadata RPCs.  Native scope details never cross this boundary.
        return None

    def step_scope(
        self, *, step_id: str, depends_on: tuple[str, ...], attempt: int
    ) -> dict[str, Any]:
        del step_id, depends_on, attempt
        # The external task container owns the real filesystem namespace.  The
        # framework still needs a RuntimePathMap while preparing formal
        # bindings, whose internal representation requires host/runtime route
        # pairs.  Use a deterministic, non-existent virtual host root for that
        # private translation only; it is never mounted, read, or serialized
        # into the task container.  All actual I/O continues through this RPC
        # substrate in the container filesystem. /app is only the stable cwd
        # alias; system configuration paths are also task-container paths.
        virtual_host_root = (
            "/tmp/sgar-external-runtime/"
            + hashlib.sha256(self.runtime_id.encode("utf-8")).hexdigest()[:32]
        )
        runtime_path = "/app"
        return {
            "protocol": "sgar-external-task-scope/v1",
            "runtime_roots": [{
                "host_path": virtual_host_root,
                "runtime_path": "/app",
                "path_kind": "directory",
            }],
            "public_inputs": [],
            "masked_roots": [],
            "hidden_roots": [],
            "writable_root": {
                "host_path": virtual_host_root,
                "runtime_path": runtime_path,
                "path_kind": "directory",
            },
            "working_directory": runtime_path,
            "allow_legacy_shell": False,
        }

    def validate_dispatch(self, prepared: Any) -> None:
        scope = prepared.sandbox_scope or {}
        external_scope = str(scope.get("protocol") or "") == "sgar-external-task-scope/v1"
        if (prepared.sandbox_scope and not external_scope) or (
            prepared.artifact_adapter is not None and not external_scope
        ):
            raise RuntimeInjectionError("UNBOUND_RUNTIME_PATH:host_scope_or_artifact_callback")
        if prepared.network_required and not self.network_allowed:
            raise RuntimeInjectionError("TASK_NETWORK_POLICY_DENIED")
        if any(
            str(key).lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
            for key in (prepared.extra_env or {})
        ):
            raise RuntimeInjectionError("TASK_PROXY_OVERRIDE_FORBIDDEN")
        if prepared.execution_substrate_mode != "external":
            raise RuntimeInjectionError("runtime_mode_mismatch")
        command = str(prepared.command or "")
        # This dispatch executes solely through the task-container RPC. The
        # manifest-selected executable needs no second hard-coded allowlist.
        # Host scope and manifest source staging remain separate boundaries.
        if not command or "\x00" in command:
            raise RuntimeInjectionError("invalid_runtime_executable")
        if any(not isinstance(item, str) or "\x00" in item for item in prepared.args):
            raise RuntimeInjectionError("invalid_runtime_argv")

    @staticmethod
    def task_path(path: str) -> str:
        return normalize_task_runtime_path(path)

    @staticmethod
    def _project_root(configured_root: str = "") -> Path:
        explicit = str(configured_root or "").strip()
        if explicit:
            root = Path(explicit).resolve()
            if not root.is_dir():
                raise WorkerProtocolError("external_project_root_missing")
            return root
        configured = str(os.environ.get("SGAR_PROJECT_ROOT") or "").strip()
        if configured:
            root = Path(configured).resolve()
            if root.is_dir():
                return root
        return Path.cwd().resolve()

    def _dispatch_source_path(self, request: Any, *, project_root: str = "") -> Path:
        definition = request.resource_definition
        entrypoint = definition.entrypoint(request.entrypoint_id)
        dispatch = str(entrypoint.dispatch or "")
        if dispatch.startswith("file://"):
            dispatch = dispatch[len("file://") :]
        root = self._project_root(project_root)
        source = Path(dispatch)
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise WorkerProtocolError("external_resource_source_outside_project") from exc
        if not source.is_file() or source.suffix not in {".py", ".sh"}:
            raise WorkerProtocolError("external_resource_source_missing")
        return source

    @staticmethod
    def _local_resource_dependencies(source: Path) -> tuple[Path, ...]:
        """Return the selected wrapper plus its transitive same-directory imports."""

        pending = [source]
        found: dict[Path, None] = {}
        while pending:
            item = pending.pop()
            item = item.resolve()
            if item in found:
                continue
            found[item] = None
            if item.suffix != ".py":
                continue
            try:
                tree = ast.parse(item.read_text(encoding="utf-8"), filename=str(item))
            except (OSError, UnicodeError, SyntaxError) as exc:
                raise WorkerProtocolError("external_resource_source_parse_failed") from exc
            module_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    module_names.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    module_names.add(node.module.split(".", 1)[0])
            for module_name in sorted(module_names):
                candidate = (item.parent / f"{module_name}.py").resolve()
                if candidate.parent == item.parent and candidate.is_file() and candidate not in found:
                    pending.append(candidate)
        return tuple(sorted(found))

    def _stage_resource_source(
        self, request: Any, *, project_root: str = ""
    ) -> tuple[Path, Path]:
        """Stage only one wrapper's dependency closure and safely reuse it."""

        root = self._project_root(project_root)
        source = self._dispatch_source_path(request, project_root=str(root))
        files = self._local_resource_dependencies(source)
        bundle = []
        identity = hashlib.sha256()
        for item in files:
            data = item.read_bytes()
            relative = item.relative_to(root).as_posix()
            digest = hashlib.sha256(data).hexdigest()
            identity.update(relative.encode("utf-8"))
            identity.update(b"\0")
            identity.update(digest.encode("ascii"))
            identity.update(b"\0")
            bundle.append((item, data.decode("utf-8"), digest, len(data)))
        stage_key = identity.hexdigest()[:20]
        stage_dir = f"/tmp/sgar-resource-runtime/{stage_key}"
        staged_source = Path(stage_dir) / source.name
        cached = self._resource_stage_cache.get(stage_key)
        if cached is not None:
            cache_valid = True
            for target, expected_digest, expected_size in cached[2]:
                metadata = self.call("artifact_metadata", path=target, timeout_sec=30)
                if (
                    not metadata.get("ok")
                    or metadata.get("content_sha256") != expected_digest
                    or metadata.get("byte_size") != expected_size
                ):
                    cache_valid = False
                    break
            if cache_valid:
                return cached[0], cached[1]

        mkdir = self.call("exec_argv", argv=["mkdir", "-p", stage_dir], timeout_sec=30)
        if not mkdir.get("ok"):
            raise WorkerProtocolError("external_resource_stage_directory_failed")
        staged_files = []
        for item, text, digest, byte_size in bundle:
            target = f"{stage_dir}/{item.name}"
            result = self.call(
                "write_text",
                path=target,
                text=text,
                timeout_sec=30,
            )
            if not result.get("ok"):
                raise WorkerProtocolError("external_resource_stage_write_failed")
            staged_files.append((target, digest, byte_size))
        cached_value = (source, staged_source, tuple(staged_files))
        self._resource_stage_cache[stage_key] = cached_value
        return source, staged_source

    def _stage_host_file(
        self, path: Path, stage_dir: Path, *, project_root: str = ""
    ) -> str:
        root = self._project_root(project_root)
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise WorkerProtocolError("external_host_path_in_resource_argv") from exc
        if not path.is_file():
            raise WorkerProtocolError("external_resource_argument_missing")
        target = f"{stage_dir.as_posix()}/{path.name}"
        result = self.call(
            "write_text",
            path=target,
            text=path.read_text(encoding="utf-8"),
            timeout_sec=30,
        )
        if not result.get("ok"):
            raise WorkerProtocolError("external_resource_argument_stage_failed")
        return target

    def _container_exec_request(self, prepared: Any, request: Any) -> tuple[list[str], dict[str, Any]]:
        """Build an exec_argv request with no host executable or script path."""

        project_root = str(getattr(prepared, "project_root", "") or "")
        declared_command = str(prepared.command)
        command_name = Path(declared_command).name
        command = "python3" if command_name in {"python", "python3"} else declared_command
        raw_args = [str(item) for item in prepared.args]
        extra_env = dict(prepared.extra_env or {})
        requirements = getattr(getattr(request, 'resource_definition', None), 'runtime_requirements', {})
        dependency_key = json.dumps({
            'python': str(requirements.get('python_compatibility') or requirements.get('python') or ''),
            'packages': sorted(str(p.get('name') or p.get('package') or '')
                for p in requirements.get('python_packages') or [] if isinstance(p, dict) and p.get('required', True)),
            'commands': sorted(str(c) for c in requirements.get('commands') or []),
            'package_versions': {str(p.get('name') or p.get('package') or ''): str(p.get('version') or '')
                for p in requirements.get('python_packages') or [] if isinstance(p, dict) and p.get('required', True)},
        }, sort_keys=True, separators=(',', ':'))
        dependency_path = self._python_dependency_paths.get(dependency_key)
        if dependency_path and command == 'python3':
            extra_env['PYTHONPATH'] = ':'.join(filter(None, (dependency_path, extra_env.get('PYTHONPATH'))))
        private_root = str(Path(project_root).resolve()) if project_root else ""

        def private_source_path(value: str) -> bool:
            return bool(private_root) and (
                value == private_root or value.startswith(private_root + os.sep)
            )

        for key, value in extra_env.items():
            text = str(value)
            if key in {"PYTHONPATH", "SGAR_EXTRA_PYTHONPATH"}:
                # The formal scope can legitimately expose the exact /app
                # root, and Python paths may contain several task-local roots.
                # Validate each component instead of treating the entire
                # colon-separated value as one host path.
                parts = text.split(":")
                if any(not part or not part.startswith("/") for part in parts):
                    raise WorkerProtocolError("external_host_path_in_resource_env")
                try:
                    for part in parts:
                        if private_source_path(part):
                            raise WorkerProtocolError("external_host_path_in_resource_env")
                        self.task_path(part)
                except RuntimeInjectionError as exc:
                    raise WorkerProtocolError("external_host_path_in_resource_env") from exc
            elif os.path.isabs(text):
                if private_source_path(text):
                    raise WorkerProtocolError("external_host_path_in_resource_env")
                try:
                    self.task_path(text)
                except RuntimeInjectionError as exc:
                    raise WorkerProtocolError("external_host_path_in_resource_env") from exc
        if private_source_path(command):
            raise WorkerProtocolError("external_host_path_in_resource_argv")
        # Port-aware lowering has already validated typed paths. Other argv
        # values are opaque task data: slash-prefixed patterns or text are not
        # paths and must never be normalized based on their spelling.
        if raw_args and raw_args[0].startswith(("/app", "/tmp")):
            for raw in raw_args:
                if private_source_path(raw):
                    raise WorkerProtocolError("external_host_path_in_resource_argv")
            return [command, *raw_args], {
                "request_call_id": request.call_id,
                "logical_step_id": getattr(request, "logical_step_id", None),
                "depends_on": list(getattr(request, "depends_on", ()) or ()),
                "bindings": dict(getattr(request, "resolved_bindings", {}) or {}),
                "network_required": bool(prepared.network_required),
                "extra_env": extra_env,
                "cwd": "/app",
            }

        source, staged_source = self._stage_resource_source(
            request, project_root=project_root
        )
        args: list[str] = []
        for raw in raw_args:
            if raw == str(source) or raw == str(source.resolve()):
                args.append(str(staged_source))
            elif os.path.isabs(raw) and raw.startswith(str(source.parent) + os.sep):
                # Sibling helper/source paths are all staged under one route.
                args.append(
                    self._stage_host_file(
                        Path(raw), staged_source.parent, project_root=project_root
                    )
                )
            elif os.path.isabs(raw):
                if private_source_path(raw):
                    raise WorkerProtocolError("external_host_path_in_resource_argv")
                args.append(raw)
            else:
                args.append(raw)
        if not args or args[0] != str(staged_source):
            # Formal resource adapters put the wrapper as argv[0].  Refuse
            # ambiguous calls rather than executing an unstaged host path.
            raise WorkerProtocolError("external_resource_entrypoint_not_staged")
        return [command, *args], {
            "request_call_id": request.call_id,
            "logical_step_id": getattr(request, "logical_step_id", None),
            "depends_on": list(getattr(request, "depends_on", ()) or ()),
            "bindings": dict(getattr(request, "resolved_bindings", {}) or {}),
            "network_required": bool(prepared.network_required),
            "extra_env": extra_env,
            "cwd": "/app",
        }

    def call(self, operation: str, *, timeout_sec: int = 30, **arguments: Any) -> dict:
        with self._lock:
            self.sequence += 1
            action_id = f"{self.runtime_id}:action:{self.sequence:04d}"
            request = {
                "protocol": "sgar-external-substrate-action-v1", "run_id": self.runtime_id,
                "trial_id": self.trial_id, "action_id": action_id,
                "operation": operation, "timeout_sec": timeout_sec, **arguments,
            }
            wire = json.dumps(request, ensure_ascii=True) + "\n"
            self.output_stream.write(wire)
            self.output_stream.flush()
            readable, _, _ = select.select(
                [self.input_stream], [], [], timeout_sec + self.rpc_timeout
            )
            if not readable:
                raise WorkerProtocolError("worker_response_timeout")
            line = self.input_stream.readline()
            if not line or not line.endswith("\n"):
                raise WorkerProtocolError("worker_response_missing")
            response = json.loads(line)
            for key in ("run_id", "trial_id", "action_id"):
                if response.get(key) != request[key]:
                    raise WorkerProtocolError("worker_response_identity_mismatch")
            if response.get("protocol") != "sgar-external-substrate-result-v1":
                raise WorkerProtocolError("worker_response_protocol_invalid")
            result = response.get("result")
            if not isinstance(result, dict) or type(result.get("ok")) is not bool:
                raise WorkerProtocolError("worker_result_invalid")
            self.records.append({"request": request, "result": result})
            return result

    async def execute(self, *, prepared: Any, request: Any) -> ExecutionResult:
        self.validate_dispatch(prepared)
        card = request.resource_definition.capability_card
        selected_operation = next(
            (
                item
                for item in (card.capability_operations if card is not None else ())
                if item.capability_operation_id == request.capability_operation_id
            ),
            None,
        )
        bindings = dict(getattr(request, "resolved_bindings", {}) or {})
        operation_kind = str(
            getattr(selected_operation, "execution_operation_kind", "") or ""
        )
        if operation_kind == "read_file":
            path = next(
                (bindings[name] for name in ("path", "file_path", "source_path") if name in bindings),
                None,
            )
            if not isinstance(path, str):
                raise WorkerProtocolError("external_read_file_binding_invalid")
            result = self.call(
                "read_text", path=self.task_path(path), timeout_sec=prepared.timeout_sec
            )
            if result.get("stdout_truncated"):
                raise WorkerProtocolError("external_read_file_truncated")
        elif operation_kind == "write_file":
            receipt = _external_write_receipt(request)
            path = next(
                (
                    bindings[name]
                    for name in (
                        "path", "file_path", "destination_path", "destination", "target_path"
                    )
                    if name in bindings
                ),
                None,
            )
            content = next(
                (
                    bindings[name]
                    for name in ("content", "text", "payload", "data")
                    if name in bindings
                ),
                None,
            )
            if not isinstance(path, str) or not isinstance(content, str):
                raise WorkerProtocolError("external_write_file_binding_invalid")
            task_path = self.task_path(path)
            native_type = str(
                (getattr(request, "resource_native_output_contract", None) or {}).get("artifact_type") or ""
            ).strip().lower()
            target_type = str(
                (getattr(request, "target_output_contract", None) or {}).get("artifact_type") or ""
            ).strip().lower()
            materialized_types = set(
                getattr(selected_operation, "materialized_artifact_types", ()) or ()
            )
            file_type = (
                target_type
                if target_type and target_type != native_type
                else infer_artifact_type_from_path(task_path, default="plaintext")
            )
            # A generic text writer can persist registered textual formats.
            # Keep the semantic type (e.g. source language) on the resulting
            # handle; matching the storage capability must not relabel output
            # or mistake the JSON write receipt for the materialized file.
            from .artifact_v2 import is_text_format

            text_compatible = "plaintext" in materialized_types and is_text_format(file_type)
            if materialized_types and file_type not in materialized_types and not text_compatible:
                raise WorkerProtocolError("external_write_file_artifact_type_unsupported")
            written = self.call(
                "write_text",
                path=task_path,
                text=content,
                timeout_sec=prepared.timeout_sec,
            )
            if written.get("ok"):
                metadata = self.call("artifact_metadata", path=task_path)
                if not metadata.get("ok"):
                    result = {
                        "ok": False,
                        "return_code": metadata.get("return_code"),
                        "stdout": "",
                        "stderr": str(
                            metadata.get("stderr")
                            or "external_artifact_metadata_unavailable"
                        ),
                        "error_type": "EXTERNAL_ARTIFACT_METADATA_UNAVAILABLE",
                    }
                else:
                    expected_bytes = content.encode("utf-8")
                    if (
                        metadata.get("content_sha256") != hashlib.sha256(expected_bytes).hexdigest()
                        or metadata.get("byte_size") != len(expected_bytes)
                    ):
                        raise WorkerProtocolError("external_written_text_identity_mismatch")
                    result = {
                        "ok": True,
                        "return_code": 0,
                        "stdout": json.dumps(receipt, ensure_ascii=False),
                        "stderr": "",
                        "duration_ms": written.get("duration_ms"),
                        "stdout_truncated": False,
                        "stderr_truncated": False,
                        "direct_artifacts": [
                            {
                                "path": task_path,
                                # The process result is a JSON receipt; the side
                                # effect is a task-state file whose content type is
                                # governed by the produced-file contract, not by
                                # the receipt's target output representation.
                                "artifact_type": file_type,
                                "content_sha256": metadata.get("content_sha256"),
                                "byte_size": metadata.get("byte_size"),
                            }
                        ],
                    }
            else:
                result = written
        else:
            argv, metadata = self._container_exec_request(prepared, request)
            result = self.call(
                "exec_argv", argv=argv,
                timeout_sec=prepared.timeout_sec, **metadata,
            )
        artifact_handles: list[dict[str, Any]] = []
        try:
            payload = json.loads(result.get("stdout") or "{}")
        except (TypeError, ValueError):
            payload = {}
        produced = payload.get("produced_files") if isinstance(payload, dict) else []
        # Failed process output is diagnostic evidence, not an artifact handoff.
        # Leave partial files in the task workspace for recovery, but return the
        # failure without a metadata RPC for every temporary file it left behind.
        if result["ok"] and isinstance(produced, list):
            for index, path in enumerate(produced):
                if not isinstance(path, str):
                    continue
                task_path = self.task_path(path)
                metadata = self.call("artifact_metadata", path=task_path)
                if not metadata.get("ok"):
                    continue
                content_sha256 = metadata.get("content_sha256")
                byte_size = metadata.get("byte_size")
                # ``artifact_metadata`` returns identity fields directly in
                # the current RPC protocol.  Retain compatibility with older
                # workers that serialized the same fields into JSON stdout.
                if content_sha256 is None or byte_size is None:
                    try:
                        legacy_metadata = json.loads(metadata.get("stdout") or "{}")
                    except (TypeError, ValueError):
                        legacy_metadata = {}
                    if isinstance(legacy_metadata, dict):
                        content_sha256 = legacy_metadata.get("content_sha256")
                        byte_size = legacy_metadata.get("byte_size")
                if not isinstance(content_sha256, str) or type(byte_size) is not int:
                    continue
                artifact_handles.append({
                    "handle_id": f"{self.runtime_id}:{request.call_id}:artifact:{index}",
                    "kind": "tool_output",
                    "producer_task": self.trial_id,
                    "producer_step": getattr(request, "logical_step_id", None),
                    "logical_path": task_path,
                    "tool_path": task_path,
                    "artifact_type": infer_artifact_type_from_path(
                        task_path,
                        default="file",
                    ),
                    "content_sha256": content_sha256,
                    "byte_size": byte_size,
                    "current_run": True,
                })
        for index, item in enumerate(result.get("direct_artifacts") or []):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                continue
            path = self.task_path(item["path"])
            artifact_handles.append({
                "handle_id": f"{self.runtime_id}:{request.call_id}:artifact:direct:{index}",
                "kind": "tool_output",
                "producer_task": self.trial_id,
                "producer_step": request.execution_context.step_id,
                "logical_path": path,
                "tool_path": path,
                "artifact_type": str(item.get("artifact_type") or "file"),
                "content_sha256": item.get("content_sha256"),
                "byte_size": item.get("byte_size"),
                "current_run": True,
            })
        failure = None
        if not result["ok"]:
            text_encoding_failed = (
                result.get("execution_phase") == "resource_execution"
                and result.get("error_type") == "RESOURCE_TEXT_ENCODING_UNSUPPORTED"
            )
            command_timed_out = (
                result.get("execution_phase") == "resource_execution"
                and result.get("error_type") == "RESOURCE_EXECUTION_TIMEOUT"
            )
            command_failed = (
                result.get("execution_phase") == "resource_execution"
                and type(result.get("return_code")) is int
                and result["return_code"] != 0
                and not result.get("error_type")
            )
            failure = {
                "responsibility": (
                    "research"
                    if command_failed or command_timed_out or text_encoding_failed
                    else "infrastructure"
                ),
                "failure_stage": (
                    "resource_execution"
                    if command_failed or command_timed_out or text_encoding_failed
                    else "execution"
                ),
                "failure_code": (
                    "resource_process_timeout" if command_timed_out
                    else "resource_process_failed" if command_failed
                    else result.get("error_type") or "EXTERNAL_SUBSTRATE_ERROR"
                ),
                "retryable": False, "response_received": True,
            }
        return ExecutionResult(
            is_success=result["ok"], output_data=result.get("stdout") or "",
            error_log=None if result["ok"] else result.get("stderr") or str(failure),
            cost_metric={"runtime_protocol": "sgar-external-substrate-action-v1",
                         "resource_execution_location": "task_container",
                         "host_resource_source_executed": False,
                         "return_code": result.get("return_code"),
                         "execution_phase": result.get("execution_phase"),
                         **({"task_process_cleanup": result["process_cleanup"]}
                            if "process_cleanup" in result else {}),
                         "latency_ms": result.get("duration_ms"),
                         "stderr": result.get("stderr"),
                         "stdout_truncated": result.get("stdout_truncated"),
                         "stderr_truncated": result.get("stderr_truncated"),
                         "external_artifact_handles": artifact_handles,
                         "execution_audit": {
                             "protocol": "sgar-external-task-scope/v1",
                             "task_namespace_validated": True,
                             "task_container_rpc": True,
                             "host_paths_exposed": False,
                             "project_root_mounted": False,
                             "runtime_argv_host_path_detected": False,
                             "host_resource_source_executed": False,
                         },
                         **({"failure": failure} if failure else {})},
        )

    async def write_text(self, path: str, text: str) -> None:
        result = self.call("write_text", path=self.task_path(path), text=text)
        if not result["ok"]:
            raise WorkerProtocolError(result.get("error_type"))

    async def read_text(self, path: str) -> str:
        result = self.call("read_text", path=self.task_path(path))
        if not result["ok"] or result.get("stdout_truncated"):
            raise WorkerProtocolError(result.get("error_type") or "truncated_file")
        return result.get("stdout") or ""

    async def read_bytes(self, path: str) -> bytes:
        result = self.call("read_bytes", path=self.task_path(path))
        if not result.get("ok"):
            raise WorkerProtocolError(result.get("error_type") or "file_read_failed")
        encoded = result.get("data_base64")
        if not isinstance(encoded, str):
            raise WorkerProtocolError("file_read_payload_missing")
        try:
            payload = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise WorkerProtocolError("file_read_payload_invalid") from exc
        if result.get("byte_size") != len(payload):
            raise WorkerProtocolError("file_read_size_mismatch")
        if result.get("content_sha256") != hashlib.sha256(payload).hexdigest():
            raise WorkerProtocolError("file_read_hash_mismatch")
        return payload

    async def exists(self, path: str) -> bool:
        result = self.call("exists", path=self.task_path(path))
        if result["ok"]:
            return True
        if result.get("return_code") == 1 and (
            result.get("error_type") == "TASK_COMMAND_NONZERO_EXIT"
            or (result.get("exists") is False and not result.get("error_type"))
        ):
            return False
        raise WorkerProtocolError(result.get("error_type"))
