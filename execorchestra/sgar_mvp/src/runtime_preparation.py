"""Explicit, content-addressed Python dependency preparation for SGAR.

The module deliberately separates environment preparation from resource
execution.  It never mutates the active Python environment and never performs
failure-driven installation.  Extra packages are resolved in a disposable
container and installed into an immutable Docker image derived from the locked
RC1 runtime.
"""

from __future__ import annotations

from .direct_network import (direct_environment, direct_container_environment_args,
                             load_tool_proxy_config, tool_proxy_environment)

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import sysconfig
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlsplit

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import InvalidVersion, Version

from .atomic_io import temporary_sibling_path
from .pipeline_control import canonical_sha256


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "runtime_provisioning.json"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMPORT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_HASH_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")

CONTROLLED_IMPORT_PACKAGE_MAP: dict[str, str] = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python-headless",
    "dateutil": "python-dateutil",
    "docx": "python-docx",
    "dotenv": "python-dotenv",
    "fitz": "pymupdf",
    "jwt": "pyjwt",
    "pil": "pillow",
    "pptx": "python-pptx",
    "reportlab": "reportlab",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
}
CONTROLLED_PACKAGE_IMPORT_MAP: dict[str, str] = {
    canonicalize_name(distribution): import_name
    for import_name, distribution in CONTROLLED_IMPORT_PACKAGE_MAP.items()
}


def _is_stdlib_import(name: str) -> bool:
    if name in set(getattr(sys, "stdlib_module_names", set())) or name in set(sys.builtin_module_names):
        return True
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError):
        return False
    if spec is None or spec.origin is None:
        return False
    if spec.origin in {"built-in", "frozen"}:
        return True
    try:
        origin = Path(spec.origin).resolve()
        stdlib = Path(sysconfig.get_paths()["stdlib"]).resolve()
        purelib = Path(sysconfig.get_paths().get("purelib") or "").resolve()
        platlib = Path(sysconfig.get_paths().get("platlib") or "").resolve()
        return origin.is_relative_to(stdlib) and not (
            (purelib and origin.is_relative_to(purelib)) or (platlib and origin.is_relative_to(platlib))
        )
    except (KeyError, OSError, ValueError):
        return False


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = temporary_sibling_path(path)
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _normalized_index_identity(url: str) -> str:
    """Return a credential-free identity that still distinguishes index paths."""

    parsed = urlsplit(str(url or "").strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimePreparationError(
            "Package index must be a credential-free HTTPS URL without query or fragment.",
            failure_type="runtime_dependency_spec_unsafe",
            failure_layer="framework_implementation",
        )
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise RuntimePreparationError(
            "Package index URL contains an invalid port.",
            failure_type="runtime_dependency_spec_unsafe",
            failure_layer="framework_implementation",
        ) from exc
    if port:
        host = f"{host}:{port}"
    path = "/" + "/".join(segment for segment in parsed.path.split("/") if segment)
    if path == "/":
        path = ""
    return f"{parsed.scheme.lower()}://{host}{path}"


class RuntimePreparationError(RuntimeError):
    """Structured failure raised before an executable resource is invoked."""

    def __init__(
        self,
        message: str,
        *,
        failure_type: str,
        failure_layer: str = "runtime_preparation",
        transient: bool = False,
        source_kind: str = "system",
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.failure_type = failure_type
        self.failure_layer = failure_layer
        self.transient = bool(transient)
        self.source_kind = source_kind
        self.details = dict(details or {})

    def model_dump(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "failure_type": self.failure_type,
            "failure_layer": self.failure_layer,
            "transient": self.transient,
            "source_kind": self.source_kind,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class PythonDependency:
    name: str
    specifier: str = ""
    hashes: tuple[str, ...] = ()
    import_names: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    install_policies: tuple[str, ...] = ("prepare_isolated",)
    required: bool = True

    @property
    def requirement(self) -> str:
        return f"{self.name}{self.specifier}"

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "specifier": self.specifier,
            "requirement": self.requirement,
            "hashes": list(self.hashes),
            "import_names": list(self.import_names),
            "sources": list(self.sources),
            "install_policies": list(self.install_policies),
            "required": self.required,
        }


@dataclass(frozen=True)
class RuntimePreparationRequest:
    python_requirements: tuple[PythonDependency, ...] = ()
    execution_network_required: bool = False
    run_id: str = ""
    step_id: str = ""
    allow_build: bool = True

    def model_dump(self) -> dict[str, Any]:
        return {
            "python_requirements": [item.model_dump() for item in self.python_requirements],
            "execution_network_required": self.execution_network_required,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "allow_build": self.allow_build,
        }


@dataclass(frozen=True)
class ResolvedPackage:
    name: str
    version: str
    filename: str
    hashes: tuple[str, ...]
    import_names: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "filename": self.filename,
            "hashes": list(self.hashes),
            "import_names": list(self.import_names),
            "sources": list(self.sources),
        }


@dataclass(frozen=True)
class RuntimeEnvironmentHandle:
    status: str
    image_id: str
    image_ref: str
    base_image_id: str
    base_image_ref: str
    environment_hash: str
    request_hash: str
    lock_hash: str
    lock_path: str
    cache_hit: bool
    execution_network_required: bool
    preparation_event_id: str
    preparation_event_ids: tuple[str, ...]
    packages: tuple[ResolvedPackage, ...] = ()
    preparation_ms: float = 0.0
    verification: Mapping[str, Any] = field(default_factory=dict)

    @property
    def execution_image(self) -> str:
        return self.image_id

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "image_id": self.image_id,
            "image_ref": self.image_ref,
            "base_image_id": self.base_image_id,
            "base_image_ref": self.base_image_ref,
            "environment_hash": self.environment_hash,
            "request_hash": self.request_hash,
            "lock_hash": self.lock_hash,
            "lock_path": self.lock_path,
            "cache_hit": self.cache_hit,
            "execution_network_required": self.execution_network_required,
            "network_required": self.execution_network_required,
            "preparation_event_id": self.preparation_event_id,
            "preparation_event_ids": list(self.preparation_event_ids),
            "packages": [item.model_dump() for item in self.packages],
            "preparation_ms": self.preparation_ms,
            "verification": dict(self.verification),
        }

    def public_projection(self) -> dict[str, Any]:
        """Return the host-free immutable execution identity."""

        return {
            "status": self.status,
            "image_id": self.image_id,
            "image_ref": self.image_ref,
            "base_image_id": self.base_image_id,
            "base_image_ref": self.base_image_ref,
            "environment_hash": self.environment_hash,
            "request_hash": self.request_hash,
            "lock_hash": self.lock_hash,
            "lock_locator": Path(self.lock_path).name if self.lock_path else "",
            "cache_hit": self.cache_hit,
            "execution_network_required": self.execution_network_required,
            "network_required": self.execution_network_required,
            "preparation_event_id": self.preparation_event_id,
            "preparation_event_ids": list(self.preparation_event_ids),
            "packages": [item.model_dump() for item in self.packages],
            "verification_sha256": canonical_sha256(dict(self.verification)),
        }


PreparedRuntimeHandle = RuntimeEnvironmentHandle


def _dependency_from_value(
    value: Any,
    source: str = "",
    *,
    install_policy: str = "prepare_isolated",
) -> PythonDependency:
    hashes: list[str] = []
    import_names: list[str] = []
    required = True
    if isinstance(value, Mapping):
        name = str(value.get("name") or value.get("package") or "").strip()
        specifier = str(value.get("version") or value.get("specifier") or "").strip()
        if specifier.lower() == "image-locked":
            specifier = ""
        if specifier and not specifier.startswith(("=", "<", ">", "!", "~")):
            specifier = "==" + specifier
        raw_hashes = value.get("hashes") or ([value.get("hash")] if value.get("hash") else [])
        hashes = [str(item).lower() for item in raw_hashes if item]
        raw_imports = value.get("import_names") or ([value.get("import_name")] if value.get("import_name") else [])
        import_names = [str(item).strip() for item in raw_imports if item]
        required = bool(value.get("required", True))
        requirement_text = f"{name}{specifier}"
    else:
        requirement_text = str(value or "").strip()
        parts = re.split(r"\s+--hash=", requirement_text)
        requirement_text = parts[0].strip()
        hashes = [item.strip().lower() for item in parts[1:] if item.strip()]
    try:
        parsed = Requirement(requirement_text)
    except InvalidRequirement as exc:
        raise RuntimePreparationError(
            f"Invalid Python requirement: {requirement_text}",
            failure_type="runtime_dependency_spec_invalid",
            source_kind="manifest" if source.startswith("manifest:") else "generated-artifact",
            details={"requirement": requirement_text},
        ) from exc
    if parsed.url or parsed.extras or parsed.marker:
        raise RuntimePreparationError(
            f"Only index-hosted, marker-free Python requirements are allowed: {requirement_text}",
            failure_type="runtime_dependency_spec_unsafe",
            source_kind="manifest" if source.startswith("manifest:") else "generated-artifact",
        )
    normalized_hashes = []
    for item in hashes:
        normalized = item if item.startswith("sha256:") else f"sha256:{item}"
        if not _HASH_RE.fullmatch(normalized):
            raise RuntimePreparationError(
                f"Invalid dependency hash for {parsed.name}: {item}",
                failure_type="runtime_dependency_spec_invalid",
                source_kind="manifest" if source.startswith("manifest:") else "generated-artifact",
            )
        normalized_hashes.append(normalized)
    return PythonDependency(
        name=canonicalize_name(parsed.name),
        specifier=str(parsed.specifier),
        hashes=tuple(sorted(set(normalized_hashes))),
        import_names=tuple(sorted(set(import_names))),
        sources=(source,) if source else (),
        install_policies=(install_policy,),
        required=required,
    )


def collect_manifest_python_dependencies(
    manifests: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> tuple[PythonDependency, ...]:
    """Collect Python requirements from one manifest or an iterable of manifests."""

    items = [manifests] if isinstance(manifests, Mapping) else list(manifests)
    groups: list[tuple[PythonDependency, ...]] = []
    for manifest in items:
        resource_id = str(manifest.get("resource_id") or "unknown")
        requirements = manifest.get("runtime_requirements") or {}
        install_policy = str(requirements.get("install_policy") or "never").strip().lower()
        if install_policy == "sandbox_auto":
            install_policy = "prepare_isolated"
        if install_policy == "repair_first":
            raise RuntimePreparationError(
                f"Legacy repair-first installation is forbidden for {resource_id}.",
                failure_type="runtime_dependency_policy_denied",
                failure_layer="framework_implementation",
                source_kind="manifest",
            )
        if install_policy not in {"never", "prepare_isolated"}:
            raise RuntimePreparationError(
                f"Unsupported install policy for {resource_id}: {install_policy}",
                failure_type="runtime_dependency_policy_denied",
                failure_layer="framework_implementation",
                source_kind="manifest",
            )
        if install_policy == "prepare_isolated" and (
            requirements.get("node_packages") or requirements.get("system_packages")
        ):
            raise RuntimePreparationError(
                f"Runtime preparation v1 only supports Python dependencies: {resource_id}",
                failure_type="unsupported_dependency_ecosystem",
                source_kind="manifest",
            )
        values = requirements.get("python_packages") or []
        groups.append(
            tuple(
                _dependency_from_value(
                    value,
                    f"manifest:{resource_id}",
                    install_policy=install_policy,
                )
                for value in values
            )
        )
    return merge_python_dependencies(*groups)


def dependencies_from_imports(
    import_names: Iterable[str],
    *,
    source: str = "generated-artifact",
    import_package_map: Optional[Mapping[str, str]] = None,
    allow_same_name_fallback: bool = True,
) -> tuple[PythonDependency, ...]:
    """Convert top-level imports (or already-mapped package names) to requirements."""

    mapping = {key.lower(): value for key, value in CONTROLLED_IMPORT_PACKAGE_MAP.items()}
    mapping.update({str(key).lower(): str(value) for key, value in (import_package_map or {}).items()})
    dependencies: list[PythonDependency] = []
    for raw_name in import_names:
        original = str(raw_name or "").strip().split(".", 1)[0]
        if not original or _is_stdlib_import(original):
            continue
        lowered = original.lower()
        package = mapping.get(lowered)
        import_name = original
        if package is None:
            mapped_import = CONTROLLED_PACKAGE_IMPORT_MAP.get(canonicalize_name(original))
            if mapped_import:
                package = original
                import_name = mapped_import
        if package is None:
            if not allow_same_name_fallback or not _IMPORT_RE.fullmatch(original):
                raise RuntimePreparationError(
                    f"No controlled package mapping for import: {original}",
                    failure_type="artifact_dependency_unresolvable",
                    source_kind="generated-artifact",
                    details={"import_name": original},
                )
            package = original
        dependency = _dependency_from_value(
            package,
            source,
            install_policy="prepare_isolated",
        )
        dependencies.append(replace(dependency, import_names=(import_name,)))
    return merge_python_dependencies(dependencies)


def merge_python_dependencies(*groups: Iterable[PythonDependency]) -> tuple[PythonDependency, ...]:
    merged: dict[str, PythonDependency] = {}
    for group in groups:
        for item in group:
            normalized = item if isinstance(item, PythonDependency) else _dependency_from_value(item)
            key = normalized.name
            previous = merged.get(key)
            if previous is None:
                merged[key] = normalized
                continue
            specifiers = {value for value in (previous.specifier, normalized.specifier) if value}
            if len(specifiers) > 1:
                # Let pip resolve compatible ranges, but reject contradictory exact pins early.
                exact = {value for value in specifiers if value.startswith("==") and "," not in value}
                if len(exact) > 1:
                    raise RuntimePreparationError(
                        f"Conflicting exact versions for {key}: {sorted(exact)}",
                        failure_type="runtime_dependency_conflict",
                        source_kind="plan",
                    )
                specifier = ",".join(sorted(specifiers))
            else:
                specifier = next(iter(specifiers), "")
            merged[key] = PythonDependency(
                name=key,
                specifier=specifier,
                hashes=tuple(sorted(set(previous.hashes) | set(normalized.hashes))),
                import_names=tuple(sorted(set(previous.import_names) | set(normalized.import_names))),
                sources=tuple(sorted(set(previous.sources) | set(normalized.sources))),
                install_policies=tuple(
                    sorted(set(previous.install_policies) | set(normalized.install_policies))
                ),
                required=previous.required or normalized.required,
            )
    return tuple(merged[key] for key in sorted(merged))


class _DirectoryLock:
    def __init__(self, path: Path, timeout_sec: int, stale_sec: int) -> None:
        self.path = path
        self.timeout_sec = timeout_sec
        self.stale_sec = stale_sec
        self.owner_token = uuid.uuid4().hex

    def __enter__(self) -> "_DirectoryLock":
        deadline = time.monotonic() + self.timeout_sec
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self.path.mkdir()
                (self.path / "owner.json").write_text(
                    _canonical_json(
                        {
                            "pid": os.getpid(),
                            "created_at": time.time(),
                            "owner_token": self.owner_token,
                        }
                    ),
                    encoding="utf-8",
                )
                return self
            except FileExistsError:
                try:
                    stale = time.time() - self.path.stat().st_mtime > self.stale_sec
                except OSError:
                    stale = False
                if stale:
                    stale_path = self.path.with_name(f"{self.path.name}.stale.{uuid.uuid4().hex}")
                    try:
                        os.replace(self.path, stale_path)
                        shutil.rmtree(stale_path, ignore_errors=True)
                        continue
                    except OSError:
                        pass
                if time.monotonic() >= deadline:
                    raise RuntimePreparationError(
                        f"Timed out waiting for runtime preparation lock: {self.path.name}",
                        failure_type="runtime_preparation_lock_timeout",
                        transient=True,
                    )
                time.sleep(0.2)

    def __exit__(self, *_: Any) -> None:
        try:
            owner = json.loads((self.path / "owner.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return
        if str(owner.get("owner_token") or "") == self.owner_token:
            shutil.rmtree(self.path, ignore_errors=True)


class RuntimePreparer:
    """Prepare immutable Docker runtime handles for one explicit dependency set."""

    def __init__(
        self,
        project_root: str | os.PathLike[str] | None = None,
        config_path: str | os.PathLike[str] | None = None,
        *,
        enabled_override: Optional[bool] = None,
        runner: Optional[Callable[..., subprocess.CompletedProcess[str]]] = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
        self.config_path = Path(config_path or DEFAULT_CONFIG_PATH).resolve()
        try:
            self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimePreparationError(
                f"Unable to load runtime provisioning config: {self.config_path}",
                failure_type="runtime_provisioning_config_invalid",
            ) from exc
        if enabled_override is not None:
            self.config["enabled"] = bool(enabled_override)
        index_override = str(os.environ.get("SGAR_PYPI_INDEX_URL") or "").strip()
        index_url = index_override or str(
            self.config.get("index_url") or "https://pypi.org/simple"
        ).strip()
        self.config["index_url"] = index_url
        # Never trust a separately configured short identity: the normalized,
        # credential-free URL is the cache identity, including mirror path.
        self.config["index_identity"] = _normalized_index_identity(index_url)
        self._runner = runner or subprocess.run
        cache_value = str(self.config.get("cache_root") or "sgar_mvp/execution_outputs/runtime_cache")
        self.cache_root = (self.project_root / cache_value).resolve() if not Path(cache_value).is_absolute() else Path(cache_value)
        self.base_lock_path = self.project_root / str(
            self.config.get("base_runtime_lock") or "sgar_mvp/config/rc1_runtime_lock.json"
        )
        self._base_inventory_cache: Optional[dict[str, str]] = None

    def _docker_platform_args(self) -> list[str]:
        platform_name = str(self.config.get("platform") or "linux/amd64").strip().lower()
        if not re.fullmatch(r"linux/(amd64|arm64)", platform_name):
            raise RuntimePreparationError(
                f"Unsupported runtime preparation platform: {platform_name}",
                failure_type="runtime_provisioning_config_invalid",
                failure_layer="framework_implementation",
            )
        return ["--platform", platform_name]

    def _run(self, args: Sequence[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        env = direct_environment(os.environ)
        env["MSYS_NO_PATHCONV"] = "1"
        args = list(args)
        # Dependency resolution/download containers use the same declared
        # egress as network Tools. Offline build/run network flags stay intact.
        if args[:2] in (["docker", "run"], ["docker", "build"]):
            env.update(tool_proxy_environment(
                load_tool_proxy_config(self.project_root),
                network_required=True, network_policy_mode="declared",
            ))
        if args[:2] == ["docker", "run"]:
            args[2:2] = direct_container_environment_args()
        elif args[:2] == ["docker", "build"]:
            overrides = direct_container_environment_args()
            overrides[::2] = ["--build-arg"] * (len(overrides) // 2)
            args[2:2] = overrides
        try:
            result = self._runner(
                list(args), capture_output=True, text=True, timeout=timeout, check=False, env=env
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimePreparationError(
                f"Runtime preparation command timed out after {timeout}s",
                failure_type="runtime_provisioning_timeout",
                transient=True,
            ) from exc
        except OSError as exc:
            raise RuntimePreparationError(
                f"Runtime preparation command failed to start: {exc}",
                failure_type="runtime_provisioning_unavailable",
                transient=True,
            ) from exc
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            daemon_available = True
            if list(args[:2]) != ["docker", "info"]:
                try:
                    daemon_probe = self._runner(
                        ["docker", "info", "--format", "{{json .ServerVersion}}"],
                        capture_output=True,
                        text=True,
                        timeout=min(max(1, timeout), 20),
                        check=False,
                        env=env,
                    )
                    daemon_available = daemon_probe.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    daemon_available = False
            transient = not daemon_available
            failure_type = (
                "runtime_daemon_unavailable"
                if transient
                else "runtime_provisioning_failed"
            )
            raise RuntimePreparationError(
                stderr[:2000] or f"Runtime preparation command exited {result.returncode}",
                failure_type=failure_type,
                transient=transient,
                details={"return_code": result.returncode},
            )
        return result

    def _run_registry_command(
        self,
        args: Sequence[str],
        *,
        timeout: int,
        dependencies: Sequence[PythonDependency],
    ) -> subprocess.CompletedProcess[str]:
        """Run a resolver/download command with bounded infrastructure retries."""

        retry_limit = max(0, int(self.config.get("infrastructure_retry_limit") or 0))
        for attempt in range(retry_limit + 1):
            try:
                return self._run(args, timeout=timeout)
            except RuntimePreparationError as exc:
                if exc.transient and attempt < retry_limit:
                    time.sleep(min(0.25 * (2**attempt), 1.0))
                    continue
                if not exc.transient:
                    manifest_source = any(
                        source.startswith("manifest:")
                        for dependency in dependencies
                        for source in dependency.sources
                    )
                    raise RuntimePreparationError(
                        str(exc),
                        failure_type=(
                            "runtime_dependency_unresolvable"
                            if manifest_source
                            else "artifact_dependency_unresolvable"
                        ),
                        source_kind="manifest" if manifest_source else "generated-artifact",
                    ) from exc
                raise
        raise AssertionError("unreachable")

    def _load_base_lock(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.base_lock_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimePreparationError(
                f"Invalid RC1 runtime lock: {self.base_lock_path}",
                failure_type="runtime_base_lock_invalid",
            ) from exc
        image_ref = str(payload.get("image") or "")
        image_id = str(payload.get("image_id") or "").lower()
        if not image_ref or not _SHA256_RE.fullmatch(image_id):
            raise RuntimePreparationError(
                "RC1 runtime lock does not contain a valid immutable image ID.",
                failure_type="runtime_base_lock_invalid",
            )
        return payload

    def _inspect_image(self, image: str) -> dict[str, Any]:
        result = self._run(
            ["docker", "image", "inspect", image],
            timeout=int(self.config.get("inspect_timeout_sec") or 30),
        )
        try:
            payload = json.loads(result.stdout)[0]
        except Exception as exc:
            raise RuntimePreparationError(
                f"Docker returned invalid image metadata for {image}",
                failure_type="runtime_image_inspect_invalid",
            ) from exc
        image_id = str(payload.get("Id") or "").lower()
        if not _SHA256_RE.fullmatch(image_id):
            raise RuntimePreparationError(
                f"Docker image {image} has no immutable sha256 image ID.",
                failure_type="runtime_image_inspect_invalid",
            )
        return payload

    def _validated_base(self) -> tuple[dict[str, Any], dict[str, Any]]:
        lock = self._load_base_lock()
        inspected = self._inspect_image(str(lock["image"]))
        actual = str(inspected.get("Id") or "").lower()
        expected = str(lock["image_id"]).lower()
        if actual != expected:
            raise RuntimePreparationError(
                f"RC1 base image digest mismatch: expected {expected}, got {actual}",
                failure_type="runtime_base_image_mismatch",
                details={"expected_image_id": expected, "actual_image_id": actual},
            )
        expected_os, expected_arch = str(
            self.config.get("platform") or "linux/amd64"
        ).lower().split("/", 1)
        actual_os = str(inspected.get("Os") or "").lower()
        actual_arch = str(inspected.get("Architecture") or "").lower()
        if actual_os != expected_os or actual_arch != expected_arch:
            raise RuntimePreparationError(
                (
                    "RC1 base image platform mismatch: "
                    f"expected {expected_os}/{expected_arch}, got {actual_os}/{actual_arch}"
                ),
                failure_type="runtime_base_image_mismatch",
                failure_layer="framework_implementation",
            )
        return lock, inspected

    def _immutable_base_ref(self, lock: Mapping[str, Any]) -> str:
        image_id = str(lock.get("image_id") or "").lower()
        if not _SHA256_RE.fullmatch(image_id):
            raise RuntimePreparationError(
                "RC1 runtime lock has no immutable image ID for Docker FROM.",
                failure_type="runtime_base_lock_invalid",
            )
        alias = f"sgar-runtime-base:{image_id.removeprefix('sha256:')}"
        try:
            inspected = self._inspect_image(alias)
        except RuntimePreparationError as exc:
            if exc.failure_type != "runtime_provisioning_failed":
                raise
            self._run(
                ["docker", "image", "tag", image_id, alias],
                timeout=int(self.config.get("inspect_timeout_sec") or 30),
            )
            inspected = self._inspect_image(alias)
        actual_id = str(inspected.get("Id") or "").lower()
        if actual_id != image_id:
            raise RuntimePreparationError(
                f"Content-addressed RC1 base alias points to {actual_id}, expected {image_id}.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        return alias

    def _base_environment_hash(self, lock: Mapping[str, Any]) -> str:
        return _sha256_json(
            {
                "base_image_id": str(lock["image_id"]).lower(),
                "platform": str(self.config.get("platform") or "linux/amd64"),
                "python_abi": str(self.config.get("python_abi") or "cp311"),
                "index_identity": str(self.config.get("index_identity") or "pypi"),
                "resolver_version": str(self.config.get("resolver_version") or "1"),
                "build_recipe_version": str(self.config.get("build_recipe_version") or "1"),
            }
        )

    def base_handle(
        self,
        execution_network_required: bool = False,
        run_id: str = "",
        step_id: str = "",
    ) -> RuntimeEnvironmentHandle:
        started = time.monotonic()
        lock, _ = self._validated_base()
        event_id = uuid.uuid4().hex
        environment_hash = self._base_environment_hash(lock)
        request_hash = _sha256_json({"environment_hash": environment_hash, "requirements": []})
        return RuntimeEnvironmentHandle(
            status="ready",
            image_id=str(lock["image_id"]).lower(),
            image_ref=str(lock["image"]),
            base_image_id=str(lock["image_id"]).lower(),
            base_image_ref=str(lock["image"]),
            environment_hash=environment_hash,
            request_hash=request_hash,
            lock_hash=str(lock.get("dockerfile_sha256") or environment_hash),
            lock_path=str(self.base_lock_path),
            cache_hit=True,
            execution_network_required=bool(execution_network_required),
            preparation_event_id=event_id,
            preparation_event_ids=(event_id,),
            preparation_ms=(time.monotonic() - started) * 1000,
            verification={"base_lock_valid": True, "run_id": run_id, "step_id": step_id},
        )

    def _request_hash(self, base_environment_hash: str, dependencies: Sequence[PythonDependency]) -> str:
        # Provenance (run/task/step IDs) is deliberately excluded.  It belongs
        # in the trace, not in the environment identity; otherwise identical
        # requirements in realistic/oracle runs would re-query the registry.
        normalized_requirements = [
            {
                "name": item.name,
                "specifier": item.specifier,
                "hashes": list(item.hashes),
                "import_names": list(item.import_names),
                "install_policies": list(item.install_policies),
                "required": item.required,
            }
            for item in dependencies
        ]
        return _sha256_json(
            {
                "base_environment_hash": base_environment_hash,
                "requirements": normalized_requirements,
            }
        )

    def _cached_handle(
        self,
        request_hash: str,
        request: RuntimePreparationRequest,
        started: float,
    ) -> Optional[RuntimeEnvironmentHandle]:
        mapping_path = self.cache_root / "requests" / f"{request_hash.removeprefix('sha256:')}.json"
        if not mapping_path.is_file():
            return None
        try:
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            lock_path = Path(str(mapping["lock_path"]))
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            package_payloads = mapping.get("packages") or lock.get("packages") or []
            packages = tuple(
                ResolvedPackage(
                    name=str(item["name"]),
                    version=str(item["version"]),
                    filename=str(item["filename"]),
                    hashes=tuple(item.get("hashes") or []),
                    import_names=tuple(item.get("import_names") or []),
                    sources=tuple(item.get("sources") or []),
                )
                for item in package_payloads
            )
            requested_by_name = {item.name: item for item in request.python_requirements}
            packages = tuple(
                replace(
                    item,
                    import_names=tuple(
                        sorted(
                            set(item.import_names)
                            | set(requested_by_name.get(item.name, PythonDependency(item.name)).import_names)
                        )
                    ),
                    sources=tuple(
                        sorted(
                            set(item.sources)
                            | set(requested_by_name.get(item.name, PythonDependency(item.name)).sources)
                        )
                    ),
                )
                for item in packages
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None
        if _sha256_json(lock) != str(mapping.get("lock_hash") or ""):
            raise RuntimePreparationError(
                "Cached runtime lock hash does not match its request mapping.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        if str(mapping.get("request_hash") or "") != request_hash:
            raise RuntimePreparationError(
                "Cached runtime request mapping belongs to a different request.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        expected_environment_hash = _sha256_json(
            {
                "base_environment_hash": str(lock.get("base_environment_hash") or ""),
                "lock_hash": str(mapping.get("lock_hash") or ""),
            }
        )
        if str(mapping.get("environment_hash") or "") != expected_environment_hash:
            raise RuntimePreparationError(
                "Cached runtime environment hash does not match its resolved lock.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        expected_base_id = str(self._load_base_lock().get("image_id") or "").lower()
        if str(lock.get("base_image_id") or "").lower() != expected_base_id:
            raise RuntimePreparationError(
                "Cached runtime lock was built from a different RC1 base image.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        try:
            inspected = self._inspect_image(str(mapping["image_ref"]))
        except RuntimePreparationError as exc:
            if exc.failure_type == "runtime_provisioning_failed":
                return None
            raise
        actual_id = str(inspected.get("Id") or "").lower()
        if actual_id != str(mapping["image_id"]).lower():
            raise RuntimePreparationError(
                "Cached runtime image ID does not match its request mapping.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        labels = ((inspected.get("Config") or {}).get("Labels") or {})
        if (
            labels.get("org.sgar.runtime-preparation") != "runtime-prep-v1"
            or labels.get("org.sgar.runtime.lock-hash") != str(mapping["lock_hash"])
            or str(labels.get("org.sgar.runtime.base-image-id") or "").lower()
            != expected_base_id
        ):
            raise RuntimePreparationError(
                "Cached runtime image labels do not match its resolved lock and base.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        try:
            verification = self._verify_prepared_image(actual_id, packages)
        except RuntimePreparationError as exc:
            if exc.transient:
                raise
            raise RuntimePreparationError(
                "Cached runtime failed import verification and cannot be reused.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
                details={"cached_failure_type": exc.failure_type, **exc.details},
            ) from exc
        event_id = uuid.uuid4().hex
        return RuntimeEnvironmentHandle(
            status="ready",
            image_id=actual_id,
            image_ref=str(mapping["image_ref"]),
            base_image_id=str(lock["base_image_id"]),
            base_image_ref=str(lock["base_image_ref"]),
            environment_hash=str(mapping["environment_hash"]),
            request_hash=request_hash,
            lock_hash=str(mapping["lock_hash"]),
            lock_path=str(lock_path),
            cache_hit=True,
            execution_network_required=request.execution_network_required,
            preparation_event_id=event_id,
            preparation_event_ids=(event_id,),
            packages=packages,
            preparation_ms=(time.monotonic() - started) * 1000,
            verification={
                **verification,
                "cache_verified": True,
                "network_used_for_resolution": False,
                "run_id": request.run_id,
                "step_id": request.step_id,
            },
        )

    def _base_inventory(self, image_id: str) -> dict[str, str]:
        if self._base_inventory_cache is not None:
            return dict(self._base_inventory_cache)
        code = (
            "import importlib.metadata,json;"
            "print(json.dumps({d.metadata['Name'].lower().replace('_','-'):d.version "
            "for d in importlib.metadata.distributions() if d.metadata.get('Name')}))"
        )
        result = self._run(
            [
                "docker", "run", "--rm", *self._docker_platform_args(),
                "--network", "none", image_id, "python", "-c", code,
            ],
            timeout=int(self.config.get("verify_timeout_sec") or 60),
        )
        try:
            self._base_inventory_cache = {
                canonicalize_name(key): str(value) for key, value in json.loads(result.stdout).items()
            }
        except Exception as exc:
            raise RuntimePreparationError(
                "Unable to inspect packages in the RC1 base image.",
                failure_type="runtime_base_inventory_invalid",
            ) from exc
        return dict(self._base_inventory_cache)

    def _index_args(self) -> list[str]:
        url = str(self.config.get("index_url") or "https://pypi.org/simple")
        _normalized_index_identity(url)
        return ["--index-url", url]

    @staticmethod
    def _dependency_satisfied(dependency: PythonDependency, inventory: Mapping[str, str]) -> bool:
        installed = inventory.get(dependency.name)
        if installed is None:
            return False
        if not dependency.specifier:
            return True
        try:
            return Version(installed) in SpecifierSet(dependency.specifier)
        except (InvalidSpecifier, InvalidVersion):
            return False

    def _partition_dependencies(
        self,
        dependencies: Sequence[PythonDependency],
        *,
        base_image_id: str,
    ) -> tuple[tuple[PythonDependency, ...], tuple[PythonDependency, ...]]:
        inventory = self._base_inventory(base_image_id)
        satisfied: list[PythonDependency] = []
        missing: list[PythonDependency] = []
        for dependency in dependencies:
            (satisfied if self._dependency_satisfied(dependency, inventory) else missing).append(dependency)
        for dependency in missing:
            policies = set(dependency.install_policies)
            if "never" not in policies:
                continue
            manifest_sources = [source for source in dependency.sources if source.startswith("manifest:")]
            if policies - {"never"}:
                raise RuntimePreparationError(
                    f"Dependency {dependency.requirement} conflicts with the locked RC1 runtime.",
                    failure_type="runtime_dependency_conflict",
                    source_kind="plan",
                    details={"sources": list(dependency.sources)},
                )
            raise RuntimePreparationError(
                f"RC1 base image is missing locked dependency {dependency.requirement}.",
                failure_type="resource_manifest_incomplete",
                failure_layer="framework_implementation",
                source_kind="manifest",
                details={"sources": manifest_sources, "dependency": dependency.model_dump()},
            )
        return tuple(satisfied), tuple(missing)

    def _resolve_and_download(
        self,
        dependencies: Sequence[PythonDependency],
        base_lock: Mapping[str, Any],
        work_dir: Path,
    ) -> tuple[ResolvedPackage, ...]:
        report_path = work_dir / "report.json"
        wheelhouse = work_dir / "wheelhouse"
        wheelhouse.mkdir(parents=True, exist_ok=True)
        mount = f"{work_dir.resolve()}:/out"
        requirements = [item.requirement for item in dependencies]
        base_image_id = str(base_lock["image_id"])
        self._run_registry_command(
            [
                "docker", "run", "--rm", *self._docker_platform_args(),
                "--network", "bridge", "-v", mount,
                base_image_id, "python", "-m", "pip", "install", "--dry-run",
                "--disable-pip-version-check", "--only-binary=:all:",
                "--report", "/out/report.json", *self._index_args(), *requirements,
            ],
            timeout=int(self.config.get("resolve_timeout_sec") or 300),
            dependencies=dependencies,
        )
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimePreparationError(
                "pip resolver did not produce a valid report.",
                failure_type="runtime_dependency_resolver_invalid",
            ) from exc
        additions: list[tuple[str, str]] = []
        base_inventory = self._base_inventory(base_image_id)
        for entry in report.get("install") or []:
            metadata = entry.get("metadata") or {}
            name = canonicalize_name(str(metadata.get("name") or ""))
            version = str(metadata.get("version") or "")
            if not name or not version:
                raise RuntimePreparationError(
                    "pip resolver report contains an unnamed distribution.",
                    failure_type="runtime_dependency_resolver_invalid",
                )
            if name in base_inventory:
                if base_inventory[name] != version and bool(self.config.get("additive_only", True)):
                    raise RuntimePreparationError(
                        f"Dependency {name} would replace RC1 version {base_inventory[name]} with {version}.",
                        failure_type="runtime_dependency_conflict",
                        source_kind="plan",
                    )
                continue
            additions.append((name, version))
        if not additions:
            return ()
        specs = [f"{name}=={version}" for name, version in sorted(set(additions))]
        self._run_registry_command(
            [
                "docker", "run", "--rm", *self._docker_platform_args(),
                "--network", "bridge", "-v", mount,
                base_image_id, "python", "-m", "pip", "download",
                "--disable-pip-version-check", "--only-binary=:all:", "--no-deps",
                "--dest", "/out/wheelhouse", *self._index_args(), *specs,
            ],
            timeout=int(self.config.get("download_timeout_sec") or 300),
            dependencies=dependencies,
        )
        dependency_by_name = {item.name: item for item in dependencies}
        resolved: list[ResolvedPackage] = []
        for path in sorted(wheelhouse.glob("*.whl")):
            try:
                wheel_name, wheel_version, _, _ = parse_wheel_filename(path.name)
            except Exception as exc:
                raise RuntimePreparationError(
                    f"Invalid wheel downloaded by resolver: {path.name}",
                    failure_type="runtime_dependency_resolver_invalid",
                ) from exc
            name = canonicalize_name(str(wheel_name))
            expected = next((version for pkg, version in additions if pkg == name), None)
            if expected is None or str(wheel_version) != expected:
                continue
            digest = _sha256_file(path)
            direct = dependency_by_name.get(name)
            if direct and direct.hashes and digest not in direct.hashes:
                raise RuntimePreparationError(
                    f"Downloaded wheel hash does not match the declared hash for {name}.",
                    failure_type="dependency_integrity_failure",
                    failure_layer="framework_implementation",
                    source_kind="manifest" if any(s.startswith("manifest:") for s in direct.sources) else "generated-artifact",
                )
            resolved.append(
                ResolvedPackage(
                    name=name,
                    version=expected,
                    filename=path.name,
                    hashes=(digest,),
                    import_names=direct.import_names if direct else (),
                    sources=direct.sources if direct else ("transitive",),
                )
            )
        missing = sorted(set(additions) - {(item.name, item.version) for item in resolved})
        if missing:
            raise RuntimePreparationError(
                f"Resolver did not download all required wheels: {missing}",
                failure_type="runtime_dependency_resolver_invalid",
            )
        return tuple(sorted(resolved, key=lambda item: item.name))

    def _write_build_context(
        self,
        work_dir: Path,
        packages: Sequence[ResolvedPackage],
        base_image_ref: str,
        lock_hash: str,
        base_image_id: str,
    ) -> None:
        lines = [
            f"{item.name}=={item.version} --hash={item.hashes[0]}" for item in packages
        ]
        (work_dir / "requirements.lock").write_text("\n".join(lines) + "\n", encoding="utf-8")
        dockerfile = (
            f"FROM {base_image_ref}\n"
            "COPY wheelhouse /opt/sgar-wheelhouse\n"
            "COPY requirements.lock /opt/sgar-requirements.lock\n"
            "RUN python -m pip install --no-index --only-binary=:all: "
            "--find-links=/opt/sgar-wheelhouse --require-hashes --no-deps "
            "-r /opt/sgar-requirements.lock\n"
            f"LABEL org.sgar.runtime-preparation=\"runtime-prep-v1\"\n"
            f"LABEL org.sgar.runtime.lock-hash=\"{lock_hash}\" "
            f"org.sgar.runtime.base-image-id=\"{base_image_id}\"\n"
        )
        (work_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")

    def _build_and_verify(
        self,
        work_dir: Path,
        image_ref: str,
        packages: Sequence[ResolvedPackage],
        lock_hash: str,
    ) -> tuple[str, dict[str, Any]]:
        try:
            self._run(
                [
                    "docker", "build", *self._docker_platform_args(),
                    "--pull=false", "--network", "none",
                    "--label", f"org.sgar.runtime.lock-hash={lock_hash}",
                    "-t", image_ref, str(work_dir),
                ],
                timeout=int(self.config.get("build_timeout_sec") or 600),
            )
        except RuntimePreparationError as exc:
            if exc.transient:
                raise
            manifest_source = any(
                source.startswith("manifest:")
                for package in packages
                for source in package.sources
            )
            raise RuntimePreparationError(
                str(exc),
                failure_type="runtime_build_failed",
                source_kind="manifest" if manifest_source else "generated-artifact",
                details={"phase": "offline_image_build", **exc.details},
            ) from exc
        inspected = self._inspect_image(image_ref)
        image_id = str(inspected.get("Id") or "").lower()
        return image_id, self._verify_prepared_image(image_id, packages)

    def _verify_prepared_image(
        self,
        image_id: str,
        packages: Sequence[ResolvedPackage],
    ) -> dict[str, Any]:
        imports = sorted({name for item in packages for name in item.import_names if _IMPORT_RE.fullmatch(name)})
        package_versions = {item.name: item.version for item in packages}
        code = (
            "import importlib,importlib.metadata,json;"
            f"imports={imports!r};versions={package_versions!r};"
            "[importlib.import_module(x) for x in imports];"
            "actual={k:importlib.metadata.version(k) for k in versions};"
            "assert actual==versions,(actual,versions);print(json.dumps(actual,sort_keys=True))"
        )
        try:
            result = self._run(
                [
                    "docker", "run", "--rm", *self._docker_platform_args(),
                    "--network", "none", image_id, "python", "-c", code,
                ],
                timeout=int(self.config.get("verify_timeout_sec") or 60),
            )
        except RuntimePreparationError as exc:
            manifest_source = any(
                source.startswith("manifest:")
                for package in packages
                for source in package.sources
            )
            raise RuntimePreparationError(
                str(exc),
                failure_type="runtime_import_verification_failed",
                source_kind="manifest" if manifest_source else "generated-artifact",
                transient=exc.transient,
                details=exc.details,
            ) from exc
        return {"imports": imports, "versions": json.loads(result.stdout or "{}")}

    def _existing_environment_image(
        self,
        image_ref: str,
        lock_hash: str,
        packages: Sequence[ResolvedPackage],
    ) -> Optional[tuple[str, dict[str, Any]]]:
        try:
            inspected = self._inspect_image(image_ref)
        except RuntimePreparationError as exc:
            if exc.failure_type == "runtime_provisioning_failed":
                return None
            raise
        labels = ((inspected.get("Config") or {}).get("Labels") or {})
        expected_base_id = str(self._load_base_lock().get("image_id") or "").lower()
        if (
            labels.get("org.sgar.runtime-preparation") != "runtime-prep-v1"
            or labels.get("org.sgar.runtime.lock-hash") != lock_hash
            or str(labels.get("org.sgar.runtime.base-image-id") or "").lower()
            != expected_base_id
        ):
            raise RuntimePreparationError(
                f"Prepared runtime tag {image_ref} has unexpected lock or base labels.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        image_id = str(inspected.get("Id") or "").lower()
        try:
            verification = self._verify_prepared_image(image_id, packages)
        except RuntimePreparationError as exc:
            if exc.transient:
                raise
            raise RuntimePreparationError(
                "Existing prepared runtime failed import verification.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
                details={"cached_failure_type": exc.failure_type, **exc.details},
            ) from exc
        return image_id, verification

    def prepare(self, request: RuntimePreparationRequest) -> RuntimeEnvironmentHandle:
        started = time.monotonic()
        dependencies = merge_python_dependencies(request.python_requirements)
        if not dependencies:
            return self.base_handle(
                execution_network_required=request.execution_network_required,
                run_id=request.run_id,
                step_id=request.step_id,
            )
        if not bool(self.config.get("enabled", True)):
            raise RuntimePreparationError(
                "Runtime dependency preparation is disabled.",
                failure_type="runtime_preparation_disabled",
            )
        if not request.allow_build:
            raise RuntimePreparationError(
                "This execution path does not allow building a derived runtime.",
                failure_type="runtime_build_disallowed",
            )
        base_lock, _ = self._validated_base()
        base_environment_hash = self._base_environment_hash(base_lock)
        request_hash = self._request_hash(base_environment_hash, dependencies)
        _, missing_dependencies = self._partition_dependencies(
            dependencies,
            base_image_id=str(base_lock["image_id"]),
        )
        if not missing_dependencies:
            handle = self.base_handle(
                execution_network_required=request.execution_network_required,
                run_id=request.run_id,
                step_id=request.step_id,
            )
            return replace(handle, request_hash=request_hash)
        cached = self._cached_handle(request_hash, request, started)
        if cached is not None:
            return cached
        lock_dir = self.cache_root / "locks" / f"{request_hash.removeprefix('sha256:')}.lock"
        with _DirectoryLock(
            lock_dir,
            timeout_sec=int(self.config.get("lock_timeout_sec") or 900),
            stale_sec=int(self.config.get("stale_lock_sec") or 1800),
        ):
            cached = self._cached_handle(request_hash, request, started)
            if cached is not None:
                return cached
            self.cache_root.mkdir(parents=True, exist_ok=True)
            temp_root = self.cache_root / "tmp"
            temp_root.mkdir(parents=True, exist_ok=True)
            work_dir = temp_root / f"sgar-runtime-{uuid.uuid4().hex}"
            work_dir.mkdir(parents=False, exist_ok=False)
            try:
                resolve_started = time.monotonic()
                packages = self._resolve_and_download(missing_dependencies, base_lock, work_dir)
                resolve_ms = (time.monotonic() - resolve_started) * 1000
                if not packages:
                    handle = self.base_handle(
                        execution_network_required=request.execution_network_required,
                        run_id=request.run_id,
                        step_id=request.step_id,
                    )
                    return replace(handle, request_hash=request_hash)
                environment_packages = [
                    {
                        "name": item.name,
                        "version": item.version,
                        "filename": item.filename,
                        "hashes": list(item.hashes),
                    }
                    for item in packages
                ]
                lock_payload = {
                    "schema_version": 1,
                    "base_image_ref": str(base_lock["image"]),
                    "base_image_id": str(base_lock["image_id"]).lower(),
                    "base_environment_hash": base_environment_hash,
                    "platform": str(self.config.get("platform") or "linux/amd64"),
                    "python_abi": str(self.config.get("python_abi") or "cp311"),
                    "packages": environment_packages,
                    "index_identity": str(self.config.get("index_identity") or "pypi"),
                    "resolver_version": str(self.config.get("resolver_version") or "1"),
                    "build_recipe_version": str(self.config.get("build_recipe_version") or "1"),
                }
                lock_hash = _sha256_json(lock_payload)
                image_repository = str(self.config.get("derived_image_repository") or "sgar-runtime-deps")
                image_ref = f"{image_repository}:{lock_hash.removeprefix('sha256:')}"
                environment_lock_dir = (
                    self.cache_root
                    / "locks"
                    / f"environment-{lock_hash.removeprefix('sha256:')}.lock"
                )
                with _DirectoryLock(
                    environment_lock_dir,
                    timeout_sec=int(self.config.get("lock_timeout_sec") or 900),
                    stale_sec=int(self.config.get("stale_lock_sec") or 1800),
                ):
                    build_started = time.monotonic()
                    existing = self._existing_environment_image(image_ref, lock_hash, packages)
                    environment_cache_hit = existing is not None
                    if existing is not None:
                        image_id, verification = existing
                    else:
                        self._write_build_context(
                            work_dir,
                            packages,
                            self._immutable_base_ref(base_lock),
                            lock_hash,
                            str(base_lock["image_id"]),
                        )
                        image_id, verification = self._build_and_verify(
                            work_dir,
                            image_ref,
                            packages,
                            lock_hash,
                        )
                    build_ms = (time.monotonic() - build_started) * 1000
            finally:
                try:
                    resolved_work = work_dir.resolve()
                    resolved_temp_root = temp_root.resolve()
                    if resolved_work.is_relative_to(resolved_temp_root):
                        shutil.rmtree(resolved_work, ignore_errors=True)
                except (OSError, ValueError):
                    pass
            lock_path = self.cache_root / "resolved" / lock_hash.removeprefix("sha256:") / "runtime.lock.json"
            _atomic_json(lock_path, lock_payload)
            environment_hash = _sha256_json(
                {"base_environment_hash": base_environment_hash, "lock_hash": lock_hash}
            )
            mapping = {
                "request_hash": request_hash,
                "lock_hash": lock_hash,
                "environment_hash": environment_hash,
                "lock_path": str(lock_path),
                "image_ref": image_ref,
                "image_id": image_id,
                "requested_requirements": [item.model_dump() for item in dependencies],
                "packages": [item.model_dump() for item in packages],
            }
            mapping_path = self.cache_root / "requests" / f"{request_hash.removeprefix('sha256:')}.json"
            _atomic_json(mapping_path, mapping)
        event_id = uuid.uuid4().hex
        return RuntimeEnvironmentHandle(
            status="ready",
            image_id=image_id,
            image_ref=image_ref,
            base_image_id=str(base_lock["image_id"]).lower(),
            base_image_ref=str(base_lock["image"]),
            environment_hash=environment_hash,
            request_hash=request_hash,
            lock_hash=lock_hash,
            lock_path=str(lock_path),
            cache_hit=environment_cache_hit,
            execution_network_required=request.execution_network_required,
            preparation_event_id=event_id,
            preparation_event_ids=(event_id,),
            packages=packages,
            preparation_ms=(time.monotonic() - started) * 1000,
            verification={
                **verification,
                "run_id": request.run_id,
                "step_id": request.step_id,
                "network_used_for_resolution": True,
                "timings_ms": {
                    "resolve_and_download": resolve_ms,
                    "build_and_verify": build_ms,
                },
            },
        )

    def prepare_from_lock(
        self,
        lock_path: str | os.PathLike[str],
        *,
        execution_network_required: bool = False,
        run_id: str = "",
        step_id: str = "",
    ) -> RuntimeEnvironmentHandle:
        """Replay a run-snapshotted resolved lock without resolving ``latest``.

        If the exact derived image still exists it is verified and returned
        without registry access.  Otherwise ``prepare`` downloads only the
        exact pinned wheels and verifies their recorded hashes.
        """

        source_path = Path(lock_path).resolve()
        try:
            lock = json.loads(source_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimePreparationError(
                f"Resolved runtime lock is invalid: {source_path}",
                failure_type="runtime_dependency_spec_invalid",
                failure_layer="framework_implementation",
            ) from exc
        base_lock, _ = self._validated_base()
        base_environment_hash = self._base_environment_hash(base_lock)
        required_identity = {
            "base_image_id": str(base_lock["image_id"]).lower(),
            "base_environment_hash": base_environment_hash,
            "platform": str(self.config.get("platform") or "linux/amd64"),
            "python_abi": str(self.config.get("python_abi") or "cp311"),
            "index_identity": str(self.config.get("index_identity") or ""),
        }
        for key, expected in required_identity.items():
            if str(lock.get(key) or "").lower() != str(expected).lower():
                raise RuntimePreparationError(
                    f"Resolved runtime lock {key} does not match the active RC1 policy.",
                    failure_type="dependency_integrity_failure",
                    failure_layer="framework_implementation",
                    details={"field": key, "expected": expected, "actual": lock.get(key)},
                )
        packages = tuple(
            ResolvedPackage(
                name=canonicalize_name(str(item["name"])),
                version=str(item["version"]),
                filename=str(item["filename"]),
                hashes=tuple(str(value).lower() for value in item.get("hashes") or []),
                sources=(f"lock-replay:{source_path.name}",),
            )
            for item in lock.get("packages") or []
        )
        if not packages or any(
            not item.hashes
            or any(not _HASH_RE.fullmatch(value) for value in item.hashes)
            for item in packages
        ):
            raise RuntimePreparationError(
                "Resolved runtime lock must contain packages with wheel hashes.",
                failure_type="runtime_dependency_spec_invalid",
                failure_layer="framework_implementation",
            )
        lock_hash = _sha256_json(lock)
        image_repository = str(
            self.config.get("derived_image_repository") or "sgar-runtime-deps"
        )
        image_ref = f"{image_repository}:{lock_hash.removeprefix('sha256:')}"
        existing = self._existing_environment_image(image_ref, lock_hash, packages)
        request_dependencies = tuple(
            PythonDependency(
                name=item.name,
                specifier=f"=={item.version}",
                hashes=item.hashes,
                sources=(f"lock-replay:{source_path.name}",),
                install_policies=("prepare_isolated",),
            )
            for item in packages
        )
        request_hash = self._request_hash(base_environment_hash, request_dependencies)
        if existing is None:
            handle = self.prepare(
                RuntimePreparationRequest(
                    python_requirements=request_dependencies,
                    execution_network_required=execution_network_required,
                    run_id=run_id,
                    step_id=step_id,
                    allow_build=True,
                )
            )
            if handle.lock_hash != lock_hash:
                raise RuntimePreparationError(
                    "Replayed runtime produced a different resolved lock.",
                    failure_type="dependency_integrity_failure",
                    failure_layer="framework_implementation",
                    details={"expected_lock_hash": lock_hash, "actual_lock_hash": handle.lock_hash},
                )
            return handle
        image_id, verification = existing
        event_id = uuid.uuid4().hex
        return RuntimeEnvironmentHandle(
            status="ready",
            image_id=image_id,
            image_ref=image_ref,
            base_image_id=str(base_lock["image_id"]).lower(),
            base_image_ref=str(base_lock["image"]),
            environment_hash=_sha256_json(
                {"base_environment_hash": base_environment_hash, "lock_hash": lock_hash}
            ),
            request_hash=request_hash,
            lock_hash=lock_hash,
            lock_path=str(source_path),
            cache_hit=True,
            execution_network_required=execution_network_required,
            preparation_event_id=event_id,
            preparation_event_ids=(event_id,),
            packages=packages,
            verification={
                **verification,
                "lock_replay": True,
                "run_id": run_id,
                "step_id": step_id,
                "network_used_for_resolution": False,
            },
        )

    async def prepare_async(self, request: RuntimePreparationRequest) -> RuntimeEnvironmentHandle:
        return await asyncio.to_thread(self.prepare, request)


__all__ = [
    "CONTROLLED_IMPORT_PACKAGE_MAP",
    "CONTROLLED_PACKAGE_IMPORT_MAP",
    "PreparedRuntimeHandle",
    "PythonDependency",
    "ResolvedPackage",
    "RuntimeEnvironmentHandle",
    "RuntimePreparationError",
    "RuntimePreparationRequest",
    "RuntimePreparer",
    "collect_manifest_python_dependencies",
    "dependencies_from_imports",
    "merge_python_dependencies",
]
