"""Safe runtime loading for immutable SGAR Skill packages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .pipeline_control import canonical_sha256
from .skill_package_identity import (
    SkillPackagePathCollisionError,
    skill_package_files,
)


DEFAULT_MAX_SKILL_BYTES = 128 * 1024


class SkillPackageError(ValueError):
    """Structured, user-safe failure raised before a Skill is injected."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class LoadedSkillFile:
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class LoadedSkillPackage:
    resource_id: str
    content: str
    main_bytes: int
    total_bytes: int
    loaded_references: List[str] | tuple[str, ...]
    content_hash: str
    source_commit: str
    selected_files: tuple[LoadedSkillFile, ...] = ()
    assembled_sha256: str = ""
    verified_package_sha256: str = ""
    integrity_verified: bool = False
    manifest_sha256: str = ""


class SkillPackageLoader:
    """Load SKILL.md plus explicitly requested, manifest-declared references.

    Files are decoded strictly as UTF-8, constrained to the immutable package
    directory, and never executed.  The loader rejects overflow instead of
    silently truncating instructions.
    """

    def __init__(
        self,
        project_root: str | Path,
        max_injected_bytes: int = DEFAULT_MAX_SKILL_BYTES,
    ):
        self.project_root = Path(project_root).resolve()
        self.max_injected_bytes = max(1, int(max_injected_bytes))

    def _resolve_project_file(self, uri: str) -> Path:
        raw = str(uri or "")
        if raw.startswith("file://"):
            raw = raw[len("file://") :]
        path = Path(raw)
        if not path.is_absolute():
            path = self.project_root / path
        resolved = path.resolve()
        if resolved != self.project_root and self.project_root not in resolved.parents:
            raise SkillPackageError(
                "skill_path_outside_workspace",
                f"Skill URI resolves outside the workspace: {uri}",
            )
        if not resolved.is_file():
            raise SkillPackageError(
                "skill_file_unavailable",
                f"Skill entrypoint is unavailable: {uri}",
            )
        return resolved

    @staticmethod
    def _strict_text(path: Path) -> tuple[str, int]:
        data = path.read_bytes()
        try:
            return data.decode("utf-8", errors="strict"), len(data)
        except UnicodeDecodeError as exc:
            raise SkillPackageError(
                "skill_invalid_utf8",
                f"Skill package file is not valid UTF-8: {path}",
            ) from exc

    @staticmethod
    def normalize_requested_references(value: Any) -> List[str]:
        """Normalize policy bindings without interpreting arbitrary prose."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple)):
            flattened: List[str] = []
            for item in value:
                flattened.extend(
                    SkillPackageLoader.normalize_requested_references(item)
                )
            return list(dict.fromkeys(flattened))
        if isinstance(value, dict):
            for key in ("literal", "value", "paths", "references"):
                if key in value:
                    return SkillPackageLoader.normalize_requested_references(
                        value[key]
                    )
        raise SkillPackageError(
            "skill_reference_binding_invalid",
            "skill_references must be a string, list, or literal/list binding.",
        )

    @staticmethod
    def _reference_catalog(skill_block: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        catalog: Dict[str, Dict[str, Any]] = {}
        raw_catalog = skill_block.get("reference_catalog", [])
        if not isinstance(raw_catalog, list):
            raise SkillPackageError(
                "skill_manifest_invalid",
                "type_specific.skill.reference_catalog must be a list.",
            )
        for item in raw_catalog:
            if not isinstance(item, dict) or not item.get("path"):
                raise SkillPackageError(
                    "skill_manifest_invalid",
                    "Every Skill reference must declare a relative path.",
                )
            key = Path(str(item["path"]).replace("\\", "/")).as_posix()
            catalog[key] = item
        return catalog

    @staticmethod
    def _resolve_package_reference(package_root: Path, relative: str) -> Path:
        relative_path = Path(relative.replace("\\", "/"))
        if relative_path.is_absolute():
            raise SkillPackageError(
                "skill_reference_path_invalid",
                f"Skill reference must be relative: {relative}",
            )
        resolved = (package_root / relative_path).resolve()
        package_resolved = package_root.resolve()
        if resolved != package_resolved and package_resolved not in resolved.parents:
            raise SkillPackageError(
                "skill_reference_path_invalid",
                f"Skill reference escapes its package: {relative}",
            )
        if not resolved.is_file():
            raise SkillPackageError(
                "skill_reference_unavailable",
                f"Skill reference is unavailable: {relative}",
            )
        return resolved

    def validate_manifest(self, manifest: Dict[str, Any]) -> None:
        resource_id = str(manifest.get("resource_id") or "")
        if manifest.get("resource_type") != "Skill":
            raise SkillPackageError(
                "skill_manifest_invalid",
                f"{resource_id or 'resource'} is not a Skill manifest.",
            )
        execution = manifest.get("execution", {})
        if execution.get("runtime") != "prompt_skill":
            raise SkillPackageError(
                "skill_manifest_invalid",
                f"{resource_id} must use execution.runtime=prompt_skill.",
            )
        entrypoint = self._resolve_project_file(str(execution.get("uri") or ""))
        _, main_bytes = self._strict_text(entrypoint)
        limit = min(
            self.max_injected_bytes,
            int(execution.get("max_injected_bytes") or self.max_injected_bytes),
        )
        if main_bytes > limit:
            raise SkillPackageError(
                "skill_context_budget_exceeded",
                f"{resource_id} main instructions exceed {limit} bytes.",
            )
        skill_block = manifest.get("type_specific", {}).get("skill", {})
        catalog = self._reference_catalog(skill_block)
        for relative in catalog:
            self._resolve_package_reference(entrypoint.parent, relative)

    def load(
        self,
        manifest: Dict[str, Any],
        requested_references: Sequence[str] | None = None,
        *,
        verify_integrity: bool = False,
    ) -> LoadedSkillPackage:
        self.validate_manifest(manifest)
        resource_id = str(manifest["resource_id"])
        execution = manifest["execution"]
        entrypoint = self._resolve_project_file(str(execution["uri"]))
        main_text, main_bytes = self._strict_text(entrypoint)
        selected_files = [LoadedSkillFile(
            entrypoint.name, hashlib.sha256(main_text.encode("utf-8")).hexdigest(), main_bytes,
        )]
        skill_block = manifest["type_specific"]["skill"]
        catalog = self._reference_catalog(skill_block)
        limit = min(
            self.max_injected_bytes,
            int(execution.get("max_injected_bytes") or self.max_injected_bytes),
        )

        requested = list(
            dict.fromkeys(
                Path(str(value).replace("\\", "/")).as_posix()
                for value in (requested_references or [])
            )
        )
        unknown = [value for value in requested if value not in catalog]
        if unknown:
            raise SkillPackageError(
                "skill_reference_not_declared",
                "Requested Skill references are not declared by the manifest: "
                + ", ".join(unknown),
            )

        parts = [f"--- Skill: {resource_id} ---\n{main_text}"]
        total_bytes = main_bytes
        loaded: List[str] = []
        for relative in requested:
            path = self._resolve_package_reference(entrypoint.parent, relative)
            text, size = self._strict_text(path)
            selected_files.append(LoadedSkillFile(
                relative, hashlib.sha256(text.encode("utf-8")).hexdigest(), size,
            ))
            if total_bytes + size > limit:
                raise SkillPackageError(
                    "skill_context_budget_exceeded",
                    f"{resource_id} plus requested references exceeds {limit} bytes.",
                )
            total_bytes += size
            loaded.append(relative)
            parts.append(f"--- Skill Reference: {relative} ---\n{text}")

        provenance = manifest.get("provenance", {})
        package_sha256 = ""
        if verify_integrity:
            source_hash = str(provenance.get("source_hash") or "").removeprefix("sha256:")
            if source_hash != selected_files[0].sha256:
                raise SkillPackageError("skill_source_hash_mismatch", "Skill main identity does not match its manifest.")
            expected_package = str(provenance.get("package_hash") or "").removeprefix("sha256:")
            if requested and not expected_package:
                raise SkillPackageError("skill_package_identity_missing", "Selected references require package identity.")
            if expected_package:
                # Same byte framing and exclusions as deterministic_skill_ingestion_v1.
                digest = hashlib.sha256()
                measured = {}
                try:
                    package_files = skill_package_files(entrypoint.parent)
                except SkillPackagePathCollisionError as exc:
                    raise SkillPackageError(exc.code, str(exc)) from exc
                for path in package_files:
                    relative = path.relative_to(entrypoint.parent)
                    safe_path = self._resolve_package_reference(entrypoint.parent, relative.as_posix())
                    data = safe_path.read_bytes()
                    name = relative.as_posix().encode("utf-8")
                    digest.update(len(name).to_bytes(4, "big"))
                    digest.update(name)
                    digest.update(len(data).to_bytes(8, "big"))
                    digest.update(data)
                    measured[relative.as_posix()] = hashlib.sha256(data).hexdigest()
                package_sha256 = digest.hexdigest()
                if package_sha256 != expected_package or any(
                    measured.get(item.relative_path) != item.sha256 for item in selected_files
                ):
                    raise SkillPackageError("skill_package_hash_mismatch", "Skill selected files do not match the sealed package.")
        content = "\n\n".join(parts)
        return LoadedSkillPackage(
            resource_id=resource_id,
            content=content,
            main_bytes=main_bytes,
            total_bytes=total_bytes,
            loaded_references=tuple(loaded) if verify_integrity else loaded,
            content_hash=str(provenance.get("source_hash") or ""),
            source_commit=str(provenance.get("source_commit") or ""),
            selected_files=tuple(selected_files),
            assembled_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            verified_package_sha256=package_sha256,
            integrity_verified=verify_integrity,
            manifest_sha256=canonical_sha256(manifest) if verify_integrity else "",
        )
