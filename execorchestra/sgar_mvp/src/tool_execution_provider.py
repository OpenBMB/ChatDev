"""Generic Tool dispatch provider for :mod:`sgar_mvp.src.resource_runtime`.

This module owns the final executor boundary only.  It receives a prepared,
typed argv invocation and never inspects resource IDs, query text, parameter
names, or capability prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .executors import DumbExecutor, ExecutionResult, HostPythonExecutor
from .runtime_abstraction import require_execution_substrate
from .pipeline_control import canonical_sha256
from .process_supervisor import NetworkExecutionPolicy
from .path_namespace import RuntimePathMap
from .direct_network import load_tool_proxy_config, tool_proxy_audit
from .resource_runtime import (
    ExecutionWorldDescriptor,
    ResourceCallRequest,
    ResourceCallResult,
    execution_result_to_resource_result,
)
from .schema import ArtifactHandle


TOOL_EXECUTION_PROVIDER_PROTOCOL = "sgar-tool-execution-provider-v1"


def uses_unscoped_host_python(runtime_profile: str, sandbox_scope: Mapping[str, Any] | None) -> bool:
    """Shared preparation/dispatch choice: scoped execution needs an image."""
    return runtime_profile == "host-python-stdlib" and not sandbox_scope


def _workspace_inventory(root: Path) -> dict[str, dict[str, Any]]:
    if not root.is_dir():
        raise RuntimeError("tool_writable_root_missing")
    inventory: dict[str, dict[str, Any]] = {}
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            item for item in directories if item != ".sgar-control"
        )
        for name in list(directories):
            path = current_path / name
            if path.is_symlink():
                raise RuntimeError("tool_side_effect_symlink_forbidden")
            relative = path.relative_to(root).as_posix()
            inventory[relative] = {"path_kind": "directory"}
        for name in sorted(files):
            path = current_path / name
            if path.is_symlink():
                raise RuntimeError("tool_side_effect_symlink_forbidden")
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
            inventory[path.relative_to(root).as_posix()] = {
                "path_kind": "file",
                "sha256": digest.hexdigest(),
                "byte_size": size,
            }
    return inventory


def _inventory_delta(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    before_keys = set(before)
    after_keys = set(after)
    modified = sorted(
        key for key in before_keys & after_keys if before[key] != after[key]
    )
    return {
        "created": [
            {"locator": key, **dict(after[key])}
            for key in sorted(after_keys - before_keys)
        ],
        "modified": [
            {"locator": key, **dict(after[key])}
            for key in modified
        ],
        "deleted": [
            {"locator": key, **dict(before[key])}
            for key in sorted(before_keys - after_keys)
        ],
    }


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _plain_sha256(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text[len("sha256:") :]
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return canonical_sha256(value)


def _public_scope_projection(
    scope: Mapping[str, Any] | None,
    *,
    project_root: str = "",
) -> dict[str, Any]:
    source = dict(scope or {})

    def runtime_locator(host_path: Any) -> str:
        if not project_root:
            raise ValueError("sandbox_scope_project_root_required")
        project = Path(project_root).resolve()
        path = Path(str(host_path)).resolve()
        try:
            relative = path.relative_to(project)
        except ValueError as exc:
            raise ValueError("sandbox_scope_path_outside_project") from exc
        return "/app/" + relative.as_posix()

    def project_entries(name: str) -> list[dict[str, Any]]:
        projected: list[dict[str, Any]] = []
        for raw in source.get(name) or []:
            if isinstance(raw, Mapping):
                item = {
                    key: raw[key]
                    for key in (
                        "runtime_path",
                        "path_kind",
                        "sha256",
                        "descriptor_hash",
                        "access",
                    )
                    if raw.get(key) is not None
                }
                if "runtime_path" not in item and raw.get("host_path"):
                    item["runtime_path"] = runtime_locator(raw["host_path"])
            else:
                item = {"runtime_path": runtime_locator(raw)}
            projected.append(item)
        return projected

    writable_raw = source.get("writable_root") or {}
    writable = (
        {"runtime_path": writable_raw.get("runtime_path")}
        if isinstance(writable_raw, Mapping) and writable_raw.get("runtime_path")
        else {}
    )
    return {
        "protocol": str(source.get("protocol") or "legacy-unscoped"),
        "runtime_roots": project_entries("runtime_roots"),
        "public_inputs": project_entries("public_inputs"),
        "masked_roots": project_entries("masked_roots"),
        "hidden_roots": project_entries("hidden_roots"),
        "writable_root": writable,
        "working_directory": str(source.get("working_directory") or ""),
        "allow_legacy_shell": bool(source.get("allow_legacy_shell", False)),
    }


def sandbox_scope_sha256(
    scope: Mapping[str, Any] | None,
    *,
    project_root: str = "",
) -> str:
    """Hash the only host-free sandbox projection exposed to runtime records."""

    return canonical_sha256(
        _public_scope_projection(scope, project_root=project_root)
    )


@dataclass(frozen=True)
class PreparedToolDispatch:
    """Private dispatch material; host paths never enter its public descriptor."""

    subtask_description: str
    context_data: str
    dispatch_locator: str
    command: str
    args: tuple[Any, ...]
    extra_env: Mapping[str, Any] = field(default_factory=dict)
    runtime_environment: Any = None
    network_required: bool = False
    sandbox_scope: Mapping[str, Any] | None = None
    runtime_profile: str = "unknown"
    runtime_kind: str = "unknown"
    project_root: str = ""
    timeout_sec: int = 180
    network_policy_mode: str = "disabled"
    stdout_limit_bytes: int = 256 * 1024 * 1024
    stderr_limit_bytes: int = 256 * 1024 * 1024
    allowed_runtime_environment_names: tuple[str, ...] = field(
        default_factory=lambda: NetworkExecutionPolicy().allowed_environment_names
    )
    artifact_adapter: Callable[[ExecutionResult], Sequence[ArtifactHandle]] | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    execution_substrate_mode: str = "default"

    def execution_world(self) -> ExecutionWorldDescriptor:
        scope_projection = _public_scope_projection(
            self.sandbox_scope,
            project_root=self.project_root,
        )
        runtime_environment = self.runtime_environment
        runtime_image_id = str(
            _field(runtime_environment, "image_id", "")
            or ("host-python-stdlib" if self.runtime_profile == "host-python-stdlib" else "")
        )
        environment_hash = _plain_sha256(
            _field(
                runtime_environment,
                "environment_hash",
                {"runtime_profile": self.runtime_profile},
            )
        )
        dependency_lock_hash = _plain_sha256(
            _field(
                runtime_environment,
                "lock_hash",
                {"runtime_profile": self.runtime_profile, "lock": "none"},
            )
        )
        request_hash = _plain_sha256(
            _field(
                runtime_environment,
                "request_hash",
                {
                    "command_sha256": canonical_sha256(self.command),
                    "args_sha256": canonical_sha256(list(self.args)),
                    "extra_env_names": sorted(str(key) for key in self.extra_env),
                    "network_required": self.network_required,
                    "network_policy_mode": self.network_policy_mode,
                    "tool_proxy_config_fingerprint": (
                        tool_proxy_audit(load_tool_proxy_config(self.project_root))[
                            "proxy_config_fingerprint"
                        ]
                        if self.network_required and self.network_policy_mode == "declared"
                        else ""
                    ),
                    "scope": scope_projection,
                },
            )
        )
        writable = scope_projection.get("writable_root") or {}
        return ExecutionWorldDescriptor(
            runtime_image_id=runtime_image_id,
            runtime_kind=self.runtime_kind,
            runtime_roots=tuple(scope_projection.get("runtime_roots") or []),
            writable_root_runtime_path=str(writable.get("runtime_path") or ""),
            working_directory=str(
                scope_projection.get("working_directory")
                or writable.get("runtime_path")
                or "/app"
            ),
            public_input_descriptors=tuple(
                scope_projection.get("public_inputs") or []
            ),
            environment_sha256=environment_hash,
            dependency_lock_sha256=dependency_lock_hash,
            runtime_request_sha256=request_hash,
            sandbox_scope_sha256=sandbox_scope_sha256(
                self.sandbox_scope,
                project_root=self.project_root,
            ),
            network_required=bool(self.network_required),
            direct_argv=True,
        )


class ToolExecutionProvider:
    """Execute one already prepared Tool call through a direct-argv executor."""

    def __init__(self, prepared: PreparedToolDispatch, *, execution_substrate: Any = None) -> None:
        self.prepared = prepared
        self.execution_substrate = require_execution_substrate(
            execution_substrate, mode=prepared.execution_substrate_mode
        )
        if self.execution_substrate is not None:
            self.execution_substrate.validate_dispatch(prepared)
        self.execution_world = prepared.execution_world()
        self.dispatch_count = 0

    async def __call__(self, request: ResourceCallRequest) -> ResourceCallResult:
        declared = request.resource_definition.entrypoint(request.entrypoint_id)
        if declared.dispatch != self.prepared.dispatch_locator:
            raise RuntimeError("prepared_entrypoint_dispatch_mismatch")
        if request.execution_world.execution_world_sha256 != self.execution_world.execution_world_sha256:
            raise RuntimeError("prepared_execution_world_mismatch")
        self.dispatch_count += 1
        writable_root = None
        before_inventory: dict[str, dict[str, Any]] = {}
        if self.execution_substrate is None and self.prepared.sandbox_scope:
            writable = self.prepared.sandbox_scope.get("writable_root") or {}
            if isinstance(writable, Mapping) and writable.get("host_path"):
                writable_root = Path(str(writable["host_path"]))
                before_inventory = _workspace_inventory(writable_root)
        if self.execution_substrate is not None:
            result = await self.execution_substrate.execute(prepared=self.prepared, request=request)
        elif (
            self.prepared.execution_substrate_mode == "external"
        ):
            raise RuntimeError("UNBOUND_RUNTIME_PATH: external provider has no substrate")
        else:
            if uses_unscoped_host_python(self.prepared.runtime_profile, self.prepared.sandbox_scope):
                executor = HostPythonExecutor(
                    project_root=self.prepared.project_root,
                    timeout_sec=self.prepared.timeout_sec,
                )
            else:
                executor = DumbExecutor(timeout_sec=self.prepared.timeout_sec)
            result = await executor.execute(
                self.prepared.subtask_description,
                self.prepared.context_data,
                command=self.prepared.command,
                args=list(self.prepared.args),
                extra_env=dict(self.prepared.extra_env),
                runtime_environment=self.prepared.runtime_environment,
                network_required=self.prepared.network_required,
                network_policy_mode=self.prepared.network_policy_mode,
                allowed_runtime_environment_names=(
                    self.prepared.allowed_runtime_environment_names
                ),
                stdout_limit_bytes=self.prepared.stdout_limit_bytes,
                stderr_limit_bytes=self.prepared.stderr_limit_bytes,
                formal_supervision=True,
                run_id=request.execution_context.run_id,
                resource_call_id=request.call_id,
                step_id=request.execution_context.step_id,
                attempt=request.execution_context.attempt,
                **(
                    {"sandbox_scope": dict(self.prepared.sandbox_scope)}
                    if self.prepared.sandbox_scope
                    else {}
                ),
            )
        result.cost_metric.update(
            {
                "resource_runtime_protocol": "sgar-resource-runtime-v1",
                "tool_execution_provider_protocol": TOOL_EXECUTION_PROVIDER_PROTOCOL,
                "entrypoint_id": request.entrypoint_id,
                "execution_world_sha256": self.execution_world.execution_world_sha256,
            }
        )
        if writable_root is not None:
            after_inventory = _workspace_inventory(writable_root)
            result.cost_metric["side_effect_inventory"] = _inventory_delta(
                before_inventory,
                after_inventory,
            )
        artifacts: tuple[ArtifactHandle, ...] = ()
        if self.execution_substrate is not None and result.is_success:
            artifacts = tuple(
                ArtifactHandle(
                    handle_id=str(item["handle_id"]),
                    kind=str(item.get("kind") or "tool_output"),
                    producer_task=item.get("producer_task"),
                    producer_step=item.get("producer_step"),
                    logical_path=str(item.get("logical_path") or item.get("tool_path") or ""),
                    host_path=None,
                    tool_path=str(item.get("tool_path") or item.get("logical_path") or ""),
                    artifact_type=str(item.get("artifact_type") or "file"),
                    validation_status="not_run",
                    current_run=True,
                    provenance={
                        "content_sha256": item.get("content_sha256"),
                        "byte_size": item.get("byte_size"),
                        "runtime": "external_task_state",
                    },
                )
                for item in (result.cost_metric.get("external_artifact_handles") or [])
                if isinstance(item, Mapping) and item.get("handle_id")
            )
        if self.execution_substrate is None and result.is_success and self.prepared.artifact_adapter is not None:
            artifacts = tuple(self.prepared.artifact_adapter(result))
        if writable_root is not None and result.is_success:
            # The runtime already inventories actual writes. A Tool's native
            # receipt need not contain paths for its file effects to be usable
            # by a subsequent declared step.
            path_map = RuntimePathMap.from_scope(self.prepared.sandbox_scope)
            known_hosts = {item.host_path for item in artifacts}
            captured = []
            delta = result.cost_metric["side_effect_inventory"]
            for item in (*delta["created"], *delta["modified"]):
                if item["path_kind"] != "file":
                    continue
                host = str(writable_root / item["locator"])
                if host in known_hosts:
                    continue
                captured.append(ArtifactHandle(
                    handle_id="artifact:tool_file:" + canonical_sha256({
                        "call_id": request.call_id, "locator": item["locator"], "sha256": item["sha256"]}),
                    kind="tool_output", producer_task=request.execution_context.subtask_id,
                    producer_step=request.execution_context.step_id, logical_path=item["locator"],
                    host_path=host, tool_path=path_map.host_to_runtime(host), artifact_type="file",
                    validation_status="not_run", current_run=True,
                    provenance={"content_sha256": item["sha256"], "byte_size": item["byte_size"],
                                "runtime": "isolated_task_state"},
                ))
                known_hosts.add(host)
            artifacts += tuple(captured)
        canonical = execution_result_to_resource_result(
            result,
            call_id=request.call_id,
            resource_id=request.resource_definition.resource_id,
            entrypoint_id=request.entrypoint_id,
            output_contract=request.output_contract,
            provider_result_source="formal_tool_provider",
            require_structured_failure=True,
        )
        return canonical.model_copy(update={"artifacts": artifacts})


__all__ = [
    "PreparedToolDispatch",
    "TOOL_EXECUTION_PROVIDER_PROTOCOL",
    "ToolExecutionProvider",
    "sandbox_scope_sha256",
    "uses_unscoped_host_python",
]
