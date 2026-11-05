"""Runtime dependency declarations and environment checks for S-GAR.

This module keeps dependency handling in the system layer. Resource manifests can
opt into ``runtime_requirements`` over time, while an overlay file lets the
orchestrator consume dependency metadata without rewriting imported resources.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .direct_network import load_project_tool_environment
from .pipeline_control import canonical_sha256


DEFAULT_OVERLAY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "config", "resource_runtime_requirements.json")
)

SUCCESS_TOOL_STATUSES = {"ok", "passed", "valid", "success", "succeeded"}
FAILURE_TOOL_STATUSES = {
    "failed",
    "error",
    "errors",
    "simulated",
    "mock",
    "placeholder",
    "no_tests",
    "invalid",
    "missing",
    "timeout",
    "blocked",
}

_MODULE_PACKAGE_ALIAS = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "fitz": "pymupdf",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
}

_BUILTIN_REQUIREMENTS: Dict[str, Dict[str, Any]] = {}


@dataclass
class EnvironmentProfile:
    """Snapshot of the control environment and available isolated runtimes."""

    python_executable: str
    python_version: str
    docker_available: bool
    docker_probe_deferred: bool = False
    docker_cli_available: bool = False
    docker_daemon_available: bool = False
    docker_error: str = ""
    docker_check_warnings: List[str] = field(default_factory=list)
    docker_warmup: Dict[str, Any] = field(default_factory=dict)
    commands: Dict[str, bool] = field(default_factory=dict)
    python_packages: Dict[str, bool] = field(default_factory=dict)
    env_vars: Dict[str, bool] = field(default_factory=dict)
    docker_images: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    network_available: Optional[bool] = None

    def model_dump(self) -> Dict[str, Any]:
        return {
            "python_executable": self.python_executable,
            "python_version": self.python_version,
            "docker_available": self.docker_available,
            "docker_probe_deferred": self.docker_probe_deferred,
            "docker_cli_available": self.docker_cli_available,
            "docker_daemon_available": self.docker_daemon_available,
            "docker_error": self.docker_error,
            "docker_check_warnings": list(self.docker_check_warnings),
            "docker_warmup": dict(self.docker_warmup),
            "commands": dict(self.commands),
            "python_packages": dict(self.python_packages),
            "env_vars": dict(self.env_vars),
            "docker_images": dict(self.docker_images),
            "network_available": self.network_available,
        }

    def public_projection(self) -> Dict[str, Any]:
        """Return the host-free production identity for traces and reports."""

        executable_name = os.path.basename(str(self.python_executable or ""))
        runtime_identity = {
            "executable_name": executable_name,
            "python_version": self.python_version,
        }
        warmup = dict(self.docker_warmup or {})
        warmup_public = {
            "status": str(warmup.get("status") or ""),
            "image": str(warmup.get("image") or ""),
            "output_sha256": canonical_sha256(str(warmup.get("output") or "")),
        }
        return {
            "python_runtime": runtime_identity,
            "python_runtime_sha256": canonical_sha256(runtime_identity),
            "docker_available": self.docker_available,
            "docker_probe_deferred": self.docker_probe_deferred,
            "docker_cli_available": self.docker_cli_available,
            "docker_daemon_available": self.docker_daemon_available,
            "docker_error_sha256": canonical_sha256(self.docker_error or ""),
            "docker_check_warning_count": len(self.docker_check_warnings),
            "docker_check_warnings_sha256": canonical_sha256(
                list(self.docker_check_warnings)
            ),
            "docker_warmup": warmup_public,
            "commands": dict(self.commands),
            "python_packages": dict(self.python_packages),
            "env_vars": dict(self.env_vars),
            "docker_image_ids": sorted(str(key) for key in self.docker_images),
            "network_available": self.network_available,
        }


@dataclass
class DependencyCheckResult:
    """Result of checking one resource against the current runtime profile."""

    resource_id: str
    runtime_profile: str = "unknown"
    dependency_status: str = "satisfied"
    install_policy: str = "repair_first"
    missing_python_packages: List[str] = field(default_factory=list)
    missing_node_packages: List[str] = field(default_factory=list)
    missing_system_packages: List[str] = field(default_factory=list)
    missing_commands: List[str] = field(default_factory=list)
    missing_env_vars: List[str] = field(default_factory=list)
    install_packages: List[str] = field(default_factory=list)
    docker_image: str = ""
    docker_image_id: str = ""
    reason: str = ""
    failure_type: str = ""
    responsibility: str = ""
    retryable: bool = False
    failure_stage: str = ""

    @property
    def is_blocked(self) -> bool:
        return self.dependency_status == "blocked"

    def model_dump(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "runtime_profile": self.runtime_profile,
            "dependency_status": self.dependency_status,
            "install_policy": self.install_policy,
            "missing_python_packages": list(self.missing_python_packages),
            "missing_node_packages": list(self.missing_node_packages),
            "missing_system_packages": list(self.missing_system_packages),
            "missing_commands": list(self.missing_commands),
            "missing_env_vars": list(self.missing_env_vars),
            "install_packages": list(self.install_packages),
            "docker_image": self.docker_image,
            "docker_image_id": self.docker_image_id,
            "reason": self.reason,
            "failure_type": self.failure_type,
            "responsibility": self.responsibility,
            "retryable": bool(self.retryable),
            "failure_stage": self.failure_stage,
        }


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_overlay(path: str = DEFAULT_OVERLAY_PATH) -> Dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            payload = json.load(f)
    except Exception:
        return {}
    if isinstance(payload, dict) and isinstance(payload.get("resources"), dict):
        return payload["resources"]
    return payload if isinstance(payload, dict) else {}


def _normalize_package_name(item: Any) -> Optional[str]:
    if isinstance(item, str):
        text = item.strip()
    elif isinstance(item, dict):
        text = str(item.get("name") or item.get("package") or "").strip()
    else:
        text = ""
    if not text:
        return None
    return _MODULE_PACKAGE_ALIAS.get(text, text)


def _package_to_import_name(package: str) -> str:
    reverse = {value: key for key, value in _MODULE_PACKAGE_ALIAS.items()}
    return reverse.get(package, package).replace("-", "_")


def get_runtime_requirements(
    resource_id: str,
    raw_manifest: Optional[Dict[str, Any]] = None,
    overlay_path: str = DEFAULT_OVERLAY_PATH,
) -> Dict[str, Any]:
    """Resolve runtime requirements, with the manifest as the authority."""

    raw_manifest = raw_manifest or {}
    merged: Dict[str, Any] = dict(_BUILTIN_REQUIREMENTS.get(resource_id, {}))
    manifest_req = raw_manifest.get("runtime_requirements")
    if isinstance(manifest_req, dict):
        merged = _deep_merge(merged, manifest_req)
    overlay = _load_overlay(overlay_path).get(resource_id, {})
    if isinstance(overlay, dict):
        merged = _deep_merge(merged, overlay)
    if not merged:
        resource_type = raw_manifest.get("resource_type") or raw_manifest.get("type", {}).get("resource_type")
        runtime = str(raw_manifest.get("execution", {}).get("runtime") or "").lower()
        if resource_type == "Model":
            merged = {"runtime_profile": "model-api", "install_policy": "never"}
        elif "script" in runtime:
            merged = {
                "runtime_profile": "python-stdlib",
                "python": ">=3.10",
                "python_packages": [],
                "commands": [],
                "network_required": False,
                "install_policy": "repair_first",
            }
        else:
            merged = {"runtime_profile": "unknown", "install_policy": "repair_first"}
    return merged


def _check_docker_daemon(
    docker_executable: Optional[str],
    *,
    timeout_sec: int = 20,
    attempts: int = 3,
    retry_delays: Sequence[int] = (2, 5),
) -> tuple[bool, str, List[str]]:
    if not docker_executable:
        return False, "docker CLI not found", []
    warnings: List[str] = []
    attempts = max(1, int(attempts or 1))
    timeout_sec = max(1, int(timeout_sec or 1))
    last_message = ""
    for attempt in range(1, attempts + 1):
        try:
            proc = subprocess.run(
                [docker_executable, "info", "--format", "{{json .ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            last_message = f"docker daemon check timed out after {timeout_sec}s"
        except Exception as exc:
            last_message = f"docker daemon check failed: {exc}"
        else:
            if proc.returncode == 0:
                return True, "", warnings
            message = (proc.stderr or proc.stdout or "").strip()
            if not message:
                message = f"docker info returned exit code {proc.returncode}"
            last_message = message.splitlines()[0][:240]

        if attempt < attempts:
            warnings.append(f"docker daemon check attempt {attempt}/{attempts} failed: {last_message}")
            delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)] if retry_delays else 0
            if delay > 0:
                time.sleep(delay)
    return False, f"{last_message} after {attempts} attempt(s)", warnings


def scan_environment(
    extra_packages: Optional[Sequence[str]] = None,
    *,
    extra_commands: Optional[Sequence[str]] = None,
    required_env_vars: Optional[Sequence[str]] = None,
    docker_images: Optional[Sequence[str]] = None,
    docker_check_timeout_sec: int = 20,
    docker_check_attempts: int = 3,
    probe_docker: bool = True,
) -> EnvironmentProfile:
    project_env: dict[str, str] = {}
    env_path = Path(os.environ.get("SGAR_PROJECT_ROOT") or os.getcwd()) / ".env"
    if env_path.is_file():
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                project_env[name.strip()] = value.strip().strip('"').strip("'")
        except OSError:
            project_env = {}
    packages = {
        "pytest",
        "pandas",
        "numpy",
        "openpyxl",
        "sklearn",
        "playwright",
        "PIL",
        "cv2",
        "yaml",
        "bs4",
    }
    if extra_packages:
        packages.update(_package_to_import_name(str(pkg)) for pkg in extra_packages if pkg)
    commands = {"docker", "node", "npm", "pytest", "git", "python3"}
    commands.update(str(command) for command in (extra_commands or []) if str(command).strip())
    docker_executable = shutil.which("docker")
    if probe_docker:
        docker_daemon_available, docker_error, docker_warnings = _check_docker_daemon(
            docker_executable,
            timeout_sec=docker_check_timeout_sec,
            attempts=docker_check_attempts,
        )
    else:
        docker_daemon_available, docker_error, docker_warnings = False, "", []
    docker_ready = bool(docker_executable and docker_daemon_available)
    image_profiles: Dict[str, Dict[str, Any]] = {}
    if docker_ready:
        for image in sorted(set(docker_images or ["sgar-runtime:rc1"])):
            try:
                proc = subprocess.run(
                    [docker_executable or "docker", "image", "inspect", image],
                    capture_output=True,
                    text=True,
                    timeout=max(1, docker_check_timeout_sec),
                    check=False,
                )
                if proc.returncode != 0:
                    image_profiles[image] = {
                        "available": False,
                        "error": (proc.stderr or proc.stdout or "image not found").strip()[:500],
                    }
                    continue
                inspected = json.loads(proc.stdout)[0]
                image_profiles[image] = {
                    "available": True,
                    "id": str(inspected.get("Id") or ""),
                    "repo_digests": list(inspected.get("RepoDigests") or []),
                }
            except Exception as exc:
                image_profiles[image] = {"available": False, "error": str(exc)[:500]}
    elif probe_docker:
        for image in sorted(set(docker_images or ["sgar-runtime:rc1"])):
            image_profiles[image] = {"available": False, "error": docker_error or "docker unavailable"}

    return EnvironmentProfile(
        python_executable=sys.executable,
        python_version=".".join(str(part) for part in sys.version_info[:3]),
        docker_available=docker_ready,
        docker_probe_deferred=not probe_docker,
        docker_cli_available=bool(docker_executable),
        docker_daemon_available=docker_daemon_available,
        docker_error=docker_error,
        docker_check_warnings=docker_warnings,
        commands={cmd: bool(shutil.which(cmd)) for cmd in sorted(commands)},
        python_packages={
            pkg: importlib.util.find_spec(_package_to_import_name(pkg)) is not None
            for pkg in sorted(packages)
        },
        env_vars={
            str(name): bool(os.environ.get(str(name)) or project_env.get(str(name)))
            for name in sorted(set(required_env_vars or []))
            if str(name).strip()
        },
        docker_images=image_profiles,
    )


def warmup_docker_runtime(
    env_profile: EnvironmentProfile,
    *,
    image: str = "sgar-runtime:rc1",
    timeout_sec: int = 300,
    workspace_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Warm the default Docker Python runtime without mutating the repo."""

    if not env_profile.docker_cli_available:
        return {
            "status": "skipped",
            "reason": "docker CLI unavailable",
            "image": image,
            "failure_type": "runtime_provisioning_unavailable",
            "responsibility": "infrastructure",
            "retryable": False,
            "failure_stage": "runtime_warmup",
        }
    if not env_profile.docker_daemon_available:
        return {
            "status": "skipped",
            "reason": env_profile.docker_error or "docker daemon unavailable",
            "image": image,
            "failure_type": "runtime_daemon_unavailable",
            "responsibility": "infrastructure",
            "retryable": False,
            "failure_stage": "runtime_warmup",
        }
    docker_executable = shutil.which("docker") or "docker"
    env = os.environ.copy()
    env["MSYS_NO_PATHCONV"] = "1"
    env["SGAR_WORKSPACE_ROOT"] = "/app"
    if workspace_root:
        env["SGAR_HOST_WORKSPACE_ROOT"] = os.path.abspath(workspace_root)
    try:
        proc = subprocess.run(
            [docker_executable, "run", "--rm", image, "python", "-V"],
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_sec or 1)),
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "failure_type": "runtime_warmup_timeout",
            "responsibility": "infrastructure",
            "retryable": False,
            "failure_stage": "runtime_warmup",
            "reason": f"Docker runtime warmup exceeded {timeout_sec}s",
            "image": image,
        }
    except OSError as exc:
        return {
            "status": "failed",
            "failure_type": "runtime_provisioning_unavailable",
            "responsibility": "infrastructure",
            "retryable": False,
            "failure_stage": "runtime_warmup",
            "reason": str(exc),
            "image": image,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "failure_type": "runtime_warmup_framework_error",
            "responsibility": "framework",
            "retryable": False,
            "failure_stage": "runtime_warmup",
            "reason": str(exc),
            "image": image,
        }
    output = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode == 0:
        return {"status": "ok", "image": image, "output": output}
    return {
        "status": "failed",
        # Warmup occurs before a resource is invoked.  A non-zero Docker result
        # therefore describes the system runtime, not task executability.  The
        # diagnostic output is deliberately not used to infer ownership.
        "failure_type": "runtime_image_pull_failed",
        "responsibility": "infrastructure",
        "retryable": False,
        "failure_stage": "runtime_warmup",
        "reason": output.splitlines()[0][:240] if output else f"docker run exited {proc.returncode}",
        "image": image,
        "return_code": proc.returncode,
    }


class DependencyGate:
    """Evaluate whether a resource can run in the current system runtime policy."""

    def __init__(
        self,
        env_profile: Optional[EnvironmentProfile] = None,
        overlay_path: str = DEFAULT_OVERLAY_PATH,
        project_root: str | os.PathLike[str] | None = None,
    ) -> None:
        self.env_profile = env_profile or scan_environment()
        self.overlay_path = overlay_path
        self.project_root = project_root
        self._cache: Dict[str, DependencyCheckResult] = {}

    def assess(self, resource_id: str, raw_manifest: Optional[Dict[str, Any]] = None) -> DependencyCheckResult:
        cache_key = f"{resource_id}:{id(raw_manifest)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        requirements = get_runtime_requirements(resource_id, raw_manifest, self.overlay_path)
        raw_manifest = raw_manifest or {}
        resource_type = raw_manifest.get("resource_type") or raw_manifest.get("type", {}).get("resource_type")
        runtime_profile = str(requirements.get("runtime_profile") or "unknown")
        install_policy = str(requirements.get("install_policy") or "repair_first")
        package_items = requirements.get("python_packages") or []
        node_package_items = requirements.get("node_packages") or []
        system_package_items = requirements.get("system_packages") or []
        command_items = requirements.get("commands") or []
        env_var_items = requirements.get("env_vars") or []
        packages = [pkg for pkg in (_normalize_package_name(item) for item in package_items) if pkg]
        node_packages = [pkg for pkg in (_normalize_package_name(item) for item in node_package_items) if pkg]
        system_packages = [pkg for pkg in (_normalize_package_name(item) for item in system_package_items) if pkg]
        commands = [str(cmd).strip() for cmd in command_items if str(cmd).strip()]
        env_vars = [str(item).strip() for item in env_var_items if str(item).strip()]
        docker_image = str(requirements.get("docker_image") or "sgar-runtime:rc1")

        host_runtime = runtime_profile in {"host-control", "host-python-stdlib"}
        missing_packages = (
            [
                pkg for pkg in packages
                if not self.env_profile.python_packages.get(_package_to_import_name(pkg), False)
            ]
            if host_runtime
            else []
        )
        missing_commands = (
            [
                cmd for cmd in commands
                if not self.env_profile.commands.get(cmd, False)
                and not (cmd == "pytest" and "pytest" in packages)
            ]
            if host_runtime
            else []
        )
        # Readiness must resolve declared Tool variables from the same project
        # environment source used by Tool dispatch. Only presence is retained.
        project_tool_env = (
            load_project_tool_environment(self.project_root, tuple(env_vars))
            if self.project_root is not None and resource_type == "Tool"
            else {}
        )
        missing_env_vars = [
            name for name in env_vars
            if not (
                project_tool_env.get(name)
                if self.project_root is not None and resource_type == "Tool"
                else self.env_profile.env_vars.get(name, False)
            )
        ]

        requires_docker = resource_type == "Tool" and runtime_profile not in {
            "model-api",
            "unknown",
            "host-control",
            "host-python-stdlib",
        }
        image_profile = self.env_profile.docker_images.get(docker_image, {})
        if runtime_profile == "unknown":
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="blocked",
                install_policy=install_policy,
                missing_env_vars=missing_env_vars,
                reason="runtime_profile_unknown",
                failure_type="resource_manifest_incomplete",
                responsibility="framework",
                retryable=False,
                failure_stage="runtime_dependency_gate",
            )
        elif missing_env_vars:
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="blocked",
                install_policy=install_policy,
                missing_env_vars=missing_env_vars,
                docker_image=docker_image if requires_docker else "",
                reason="missing environment variables: " + ", ".join(missing_env_vars),
                failure_type="runtime_environment_drift",
                responsibility="infrastructure",
                retryable=False,
                failure_stage="runtime_dependency_gate",
            )
        elif requirements.get("network_required") and self.env_profile.network_available is False:
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="blocked",
                install_policy=install_policy,
                docker_image=docker_image if requires_docker else "",
                reason="network_unavailable",
                failure_type="runtime_provisioning_infrastructure_failure",
                responsibility="infrastructure",
                retryable=False,
                failure_stage="runtime_dependency_gate",
            )
        elif (
            requires_docker
            and not self.env_profile.docker_probe_deferred
            and not self.env_profile.docker_available
        ):
            if not self.env_profile.docker_cli_available:
                docker_reason = "docker CLI unavailable"
            elif not self.env_profile.docker_daemon_available:
                docker_reason = "docker CLI available but daemon unavailable"
                if self.env_profile.docker_error:
                    docker_reason += f": {self.env_profile.docker_error}"
            else:
                docker_reason = "docker unavailable"
            failure_type = (
                "runtime_provisioning_unavailable"
                if not self.env_profile.docker_cli_available
                else "runtime_daemon_unavailable"
            )
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="blocked",
                install_policy=install_policy,
                missing_python_packages=missing_packages,
                missing_commands=missing_commands,
                missing_env_vars=missing_env_vars,
                docker_image=docker_image,
                reason=docker_reason,
                failure_type=failure_type,
                responsibility="infrastructure",
                retryable=False,
                failure_stage="runtime_dependency_gate",
            )
        elif (
            requires_docker
            and not self.env_profile.docker_probe_deferred
            and not image_profile.get("available")
        ):
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="blocked",
                install_policy=install_policy,
                missing_python_packages=packages,
                missing_node_packages=node_packages,
                missing_system_packages=system_packages,
                missing_commands=commands,
                docker_image=docker_image,
                reason=f"runtime_image_missing: {docker_image}",
                failure_type="runtime_image_pull_failed",
                responsibility="infrastructure",
                retryable=False,
                failure_stage="runtime_dependency_gate",
            )
        elif (
            requires_docker
            and not self.env_profile.docker_probe_deferred
            and isinstance(self.env_profile.docker_warmup, dict)
            and self.env_profile.docker_warmup.get("status") == "failed"
        ):
            failure_type = str(self.env_profile.docker_warmup.get("failure_type") or "runtime_profile_unavailable")
            reason = str(self.env_profile.docker_warmup.get("reason") or "Docker runtime warmup failed")
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="blocked",
                install_policy=install_policy,
                missing_python_packages=missing_packages,
                missing_commands=missing_commands,
                missing_env_vars=missing_env_vars,
                docker_image=docker_image,
                docker_image_id=str(image_profile.get("id") or ""),
                reason=f"{failure_type}: {reason}",
                failure_type=failure_type,
                responsibility=str(
                    self.env_profile.docker_warmup.get("responsibility") or "framework"
                ),
                retryable=bool(self.env_profile.docker_warmup.get("retryable", False)),
                failure_stage=str(
                    self.env_profile.docker_warmup.get("failure_stage")
                    or "runtime_warmup"
                ),
            )
        elif install_policy == "sandbox_auto" and packages:
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="installable",
                install_policy=install_policy,
                missing_python_packages=missing_packages,
                missing_commands=missing_commands,
                install_packages=packages,
                reason="Required Python packages will be installed in the isolated Docker runtime.",
            )
        elif runtime_profile == "model-api" or (not missing_packages and not missing_commands):
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="satisfied",
                install_policy=install_policy,
                docker_image=docker_image if requires_docker else "",
                docker_image_id=str(image_profile.get("id") or "") if requires_docker else "",
            )
        elif install_policy == "sandbox_auto" and self.env_profile.docker_available and not missing_commands:
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="installable",
                install_policy=install_policy,
                missing_python_packages=missing_packages,
                missing_commands=missing_commands,
                install_packages=missing_packages,
                reason="Required Python packages can be installed in the isolated Docker runtime.",
            )
        else:
            reason_parts = []
            if missing_packages:
                reason_parts.append("missing packages: " + ", ".join(missing_packages))
            if missing_commands:
                reason_parts.append("missing commands: " + ", ".join(missing_commands))
            if install_policy != "sandbox_auto":
                reason_parts.append(f"install_policy={install_policy}")
            if not self.env_profile.docker_available and install_policy == "sandbox_auto":
                if self.env_profile.docker_cli_available and not self.env_profile.docker_daemon_available:
                    reason_parts.append("docker daemon unavailable")
                else:
                    reason_parts.append("docker unavailable")
            result = DependencyCheckResult(
                resource_id=resource_id,
                runtime_profile=runtime_profile,
                dependency_status="blocked",
                install_policy=install_policy,
                missing_python_packages=missing_packages,
                missing_commands=missing_commands,
                reason="; ".join(reason_parts),
                failure_type="resource_dependency_missing",
                responsibility="research",
                retryable=False,
                failure_stage="runtime_dependency_gate",
            )
        self._cache[cache_key] = result
        return result


@lru_cache(maxsize=1)
def _stdlib_modules() -> Set[str]:
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    stdlib.update(sys.builtin_module_names)
    stdlib.update({"__future__", "typing_extensions"})
    return stdlib


def scan_python_imports_from_text(code: str) -> List[str]:
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    imports: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
    return sorted(imports)


def scan_python_imports_from_file(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return scan_python_imports_from_text(f.read())
    except OSError:
        return []


def _is_local_module(module_name: str, local_dirs: Iterable[str]) -> bool:
    for directory in local_dirs:
        if not directory:
            continue
        root = os.path.abspath(directory)
        if os.path.isfile(os.path.join(root, f"{module_name}.py")):
            return True
        module_dir = os.path.join(root, module_name)
        if os.path.isfile(os.path.join(module_dir, "__init__.py")):
            return True
        if os.path.isdir(module_dir):
            for current, dirnames, filenames in os.walk(module_dir):
                dirnames[:] = [
                    name
                    for name in dirnames
                    if name not in {"__pycache__", ".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache"}
                ]
                if any(name.endswith(".py") for name in filenames):
                    return True
    return False


def missing_external_python_imports(
    imports: Sequence[str],
    *,
    allowed_packages: Optional[Sequence[str]] = None,
    local_dirs: Optional[Sequence[str]] = None,
) -> List[str]:
    allowed_modules = {
        _package_to_import_name(pkg)
        for pkg in (allowed_packages or [])
        if str(pkg).strip()
    }
    local_dirs = list(local_dirs or [])
    missing: List[str] = []
    for module in imports:
        if not module or module in _stdlib_modules() or module in allowed_modules:
            continue
        if _is_local_module(module, local_dirs):
            continue
        missing.append(_MODULE_PACKAGE_ALIAS.get(module, module))
    return sorted(set(missing))


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    stripped = (text or "").strip()
    if not stripped:
        return None
    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def interpret_tool_status(output_data: str) -> Optional[Dict[str, Any]]:
    payload = extract_json_object(output_data)
    if not payload:
        return None
    raw_status = str(payload.get("status") or payload.get("result") or "").strip().lower()
    if not raw_status:
        return None
    if raw_status in SUCCESS_TOOL_STATUSES:
        semantic_ok = True
    elif raw_status in FAILURE_TOOL_STATUSES:
        semantic_ok = False
    else:
        return None
    reason = (
        payload.get("error")
        or payload.get("message")
        or payload.get("stderr")
        or payload.get("stdout")
        or raw_status
    )
    return {
        "semantic_ok": semantic_ok,
        "status": raw_status,
        "reason": str(reason or raw_status)[:2000],
        "payload": payload,
    }
