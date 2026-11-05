"""RC1 resource readiness classification and effective-pool generation."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .skill_package_identity import skill_package_fingerprint
from .skill_runtime import SkillPackageError, SkillPackageLoader


READINESS_STATUSES = {
    "ready",
    "blocked",
    "inactive",
    "unavailable",
    "transient_failure",
}
REQUIRED_TOOL_RUNTIME_FIELDS = {
    "runtime_profile",
    "python",
    "python_packages",
    "node_packages",
    "system_packages",
    "commands",
    "env_vars",
    "network_required",
    "install_policy",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def resource_type(manifest: dict[str, Any]) -> str:
    nested = manifest.get("type") if isinstance(manifest.get("type"), dict) else {}
    return str(manifest.get("resource_type") or nested.get("resource_type") or "")


def resolve_file_uri(project_root: Path, uri: str) -> Path:
    text = str(uri or "")
    if not text.startswith("file://"):
        raise ValueError("file_uri_required")
    path = (project_root / text.removeprefix("file://")).resolve()
    if path != project_root and project_root not in path.parents:
        raise ValueError("file_uri_outside_project")
    if not path.is_file():
        raise ValueError("file_uri_missing")
    return path


def skill_package_hash(package_root: Path) -> str:
    digest, _ = skill_package_fingerprint(package_root)
    return "sha256:" + digest


def _evidence_index(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in payload.get(key, []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        for identifier_key in ("resource_id", "model_id", "agent_id"):
            identifier = str(item.get(identifier_key) or "")
            if identifier:
                index[identifier] = item
    return index


@dataclass
class ReadinessEntry:
    resource_id: str
    resource_type: str
    catalog_status: str
    readiness_status: str
    reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        if self.readiness_status not in READINESS_STATUSES:
            raise ValueError(f"Invalid readiness status: {self.readiness_status}")
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "catalog_status": self.catalog_status,
            "readiness_status": self.readiness_status,
            "reasons": list(dict.fromkeys(self.reasons)),
            "evidence": self.evidence,
        }


class RC1ReadinessBuilder:
    def __init__(
        self,
        project_root: str | Path,
        catalog: list[dict[str, Any]],
        *,
        tool_smoke: dict[str, Any] | None = None,
        model_health: dict[str, Any] | None = None,
        agent_smoke: dict[str, Any] | None = None,
        runtime_lock: dict[str, Any] | None = None,
        upstream_admission: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.catalog = catalog
        self.catalog_by_id = {
            str(item["resource_id"]): item for item in catalog if item.get("resource_id")
        }
        self.tool_smoke = tool_smoke or {}
        self.model_health = model_health or {}
        self.agent_smoke = agent_smoke or {}
        self.runtime_lock = runtime_lock or {}
        self.upstream_admission = upstream_admission or {}
        self.tool_evidence = _evidence_index(self.tool_smoke, "tools")
        self.model_evidence = _evidence_index(self.model_health, "models")
        self.agent_evidence = _evidence_index(self.agent_smoke, "agent_matrix")
        self.upstream_tool_evidence = _evidence_index(
            self.upstream_admission, "resources"
        )
        self.skill_loader = SkillPackageLoader(self.project_root)

    def _inactive_entry(self, manifest: dict[str, Any]) -> ReadinessEntry | None:
        status = str(manifest.get("status") or "").lower()
        execution = manifest.get("execution") if isinstance(manifest.get("execution"), dict) else {}
        execution_status = str(execution.get("execution_status") or "").lower()
        if status in {"inactive", "disabled"} or execution_status in {"inactive", "disabled"}:
            return ReadinessEntry(
                str(manifest["resource_id"]),
                resource_type(manifest),
                status or execution_status,
                "inactive",
                ["catalog_inactive"],
            )
        return None

    def _tool(self, manifest: dict[str, Any]) -> ReadinessEntry:
        inactive = self._inactive_entry(manifest)
        if inactive:
            return inactive
        rid = str(manifest["resource_id"])
        reasons: list[str] = []
        evidence: dict[str, Any] = {}
        requirements = manifest.get("runtime_requirements")
        if not isinstance(requirements, dict):
            reasons.append("runtime_requirements_missing")
        else:
            required_runtime_fields = set(REQUIRED_TOOL_RUNTIME_FIELDS)
            if requirements.get("runtime_profile") == "task-container":
                required_runtime_fields.discard("python")
            missing = sorted(required_runtime_fields - set(requirements))
            if missing:
                reasons.append("runtime_requirements_incomplete:" + ",".join(missing))
            if requirements.get("runtime_profile") == "unknown":
                reasons.append("runtime_profile_unknown")
            install_policy = str(requirements.get("install_policy") or "")
            if install_policy not in {"never", "prepare_isolated"}:
                reasons.append("install_policy_unsupported")
            if install_policy == "prepare_isolated":
                for package in requirements.get("python_packages") or []:
                    if not isinstance(package, dict):
                        reasons.append("prepare_dependency_not_structured")
                        continue
                    version = str(package.get("version") or "").strip()
                    if not version.startswith("==") or len(version) <= 2:
                        reasons.append("prepare_dependency_not_exactly_pinned")
            if int(requirements.get("max_auto_heals") or 0) != 0:
                reasons.append("max_auto_heals_not_zero")
            if requirements.get("docker_image") != "sgar-runtime:rc1":
                if requirements.get("runtime_profile") not in {
                    "task-container",
                    "host-python-stdlib",
                }:
                    reasons.append("runtime_image_not_rc1")
        actual_hash = ""
        try:
            implementation = resolve_file_uri(
                self.project_root,
                str((manifest.get("execution") or {}).get("uri") or ""),
            )
            actual_hash = sha256_bytes(implementation.read_bytes())
            declared_hash = str((manifest.get("provenance") or {}).get("source_hash") or "")
            evidence["source_hash"] = actual_hash
            if declared_hash != actual_hash:
                reasons.append("source_hash_mismatch")
        except ValueError as exc:
            reasons.append(str(exc))

        task_container_runtime = (
            isinstance(requirements, dict)
            and requirements.get("runtime_profile") == "task-container"
        )
        backend = str(self.runtime_lock.get("runtime_backend") or "docker")
        if backend == "apptainer" and not task_container_runtime:
            image_hash = str(self.runtime_lock.get("runtime_image_sha256") or "")
            smoke_hash = str(self.tool_smoke.get("runtime_image_sha256") or "")
            if not re.fullmatch(r"[a-f0-9]{64}", image_hash):
                reasons.append("runtime_lock_missing")
            if self.tool_smoke.get("runtime_backend") != "apptainer":
                reasons.append("smoke_runtime_backend_mismatch")
            if not image_hash or image_hash != smoke_hash:
                reasons.append("smoke_runtime_digest_mismatch")
            row = self.tool_evidence.get(rid) or {}
            if row.get("runtime_backend") != "apptainer" or row.get("runtime_image_sha256") != image_hash:
                reasons.append("smoke_resource_runtime_identity_mismatch")
            evidence["runtime_backend"] = backend
            evidence["runtime_image_sha256"] = image_hash
        elif backend == "docker":
            image_id = str(self.runtime_lock.get("image_id") or "")
            smoke_image_id = str(self.tool_smoke.get("docker_image_id") or "")
            if not image_id and not task_container_runtime:
                reasons.append("runtime_lock_missing")
            if image_id and smoke_image_id and image_id != smoke_image_id and not task_container_runtime:
                reasons.append("smoke_runtime_digest_mismatch")
        elif backend != "apptainer":
            reasons.append("runtime_backend_unsupported")

        if task_container_runtime:
            # The shared RC1 image is deliberately not authoritative for a
            # task-container resource.  The benchmark adapter must perform a
            # task-image preflight before dispatch; static catalog readiness
            # only proves the wrapper and contract are internally valid.
            evidence["task_container_preflight"] = "deferred_to_benchmark_adapter"
            return ReadinessEntry(rid, "Tool", "active", "ready" if not reasons else "blocked", reasons, evidence)

        upstream = self.upstream_tool_evidence.get(rid)
        if upstream:
            evidence["upstream_admission"] = upstream
            if str(upstream.get("status") or "").upper() != "PASS":
                reasons.append("upstream_admission_not_passed")
            declared_version = str(
                (manifest.get("provenance") or {}).get("version") or ""
            ).strip()
            admitted_version = str(upstream.get("upstream_version") or "").strip()
            if declared_version and admitted_version and declared_version != admitted_version:
                reasons.append("upstream_admission_version_mismatch")
            status = "ready" if not reasons else "blocked"
            return ReadinessEntry(rid, "Tool", "active", status, reasons, evidence)

        smoke = self.tool_evidence.get(rid)
        if not smoke:
            reasons.append("real_smoke_not_run")
            return ReadinessEntry(rid, "Tool", "active", "blocked", reasons, evidence)
        evidence["smoke"] = {
            key: smoke.get(key)
            for key in (
                "checked_at",
                "status",
                "latency_ms",
                "attempt_count",
                "output_sha256",
                "failure_type",
            )
            if key in smoke
        }
        smoke_source_hash = str(smoke.get("source_hash") or "")
        if actual_hash and smoke_source_hash != actual_hash:
            reasons.append("smoke_source_hash_mismatch")
        if isinstance(requirements, dict) and requirements.get("install_policy") == "prepare_isolated":
            preparation = (
                smoke.get("runtime_preparation")
                if isinstance(smoke.get("runtime_preparation"), dict)
                else {}
            )
            environment_hash = str(
                preparation.get("environment_hash")
                or smoke.get("runtime_environment_hash")
                or ""
            )
            prepared_image_id = str(
                preparation.get("image_id")
                or smoke.get("runtime_image_id")
                or ""
            )
            verified = bool(
                preparation.get("verified")
                if "verified" in preparation
                else smoke.get("runtime_preparation_verified", False)
            )
            evidence["runtime_preparation"] = {
                "environment_hash": environment_hash,
                "image_id": prepared_image_id,
                "verified": verified,
            }
            if not environment_hash:
                reasons.append("prepared_environment_hash_missing")
            if not prepared_image_id.startswith("sha256:"):
                reasons.append("prepared_image_id_missing")
            if not verified:
                reasons.append("prepared_runtime_not_verified")
        smoke_status = str(smoke.get("status") or "")
        if smoke_status == "transient_failure":
            return ReadinessEntry(
                rid,
                "Tool",
                "active",
                "transient_failure",
                reasons + [str(smoke.get("failure_type") or "transient_tool_failure")],
                evidence,
            )
        if smoke_status != "ready" or not smoke.get("smoke_passed"):
            reasons.append(str(smoke.get("failure_type") or "real_smoke_failed"))
        status = "ready" if not reasons else "blocked"
        return ReadinessEntry(rid, "Tool", "active", status, reasons, evidence)

    @staticmethod
    def _model_api_id(manifest: dict[str, Any]) -> str:
        model = (manifest.get("type_specific") or {}).get("model") or {}
        execution = manifest.get("execution") or {}
        return str(model.get("model_id") or execution.get("model_id") or "")

    def _model(self, manifest: dict[str, Any]) -> ReadinessEntry:
        rid = str(manifest["resource_id"])
        catalog_status = str(manifest.get("status") or "").lower()
        if manifest.get("selection_scope") == "control_only":
            return ReadinessEntry(rid, "Model", catalog_status, "inactive", ["control_model_outside_candidate_pool"])
        if catalog_status == "unavailable":
            return ReadinessEntry(rid, "Model", catalog_status, "unavailable", ["catalog_unavailable"])
        inactive = self._inactive_entry(manifest)
        if inactive:
            return inactive
        api_id = self._model_api_id(manifest)
        probe = self.model_evidence.get(rid) or self.model_evidence.get(api_id)
        evidence = {"api_model_id": api_id}
        if not probe:
            return ReadinessEntry(
                rid, "Model", catalog_status or "active", "blocked", ["live_text_probe_not_run"], evidence
            )
        evidence["probe"] = {
            key: probe.get(key)
            for key in (
                "checked_at",
                "status",
                "text_ok",
                "latency_ms",
                "error_code",
                "capability_evidence",
            )
            if key in probe
        }
        from .model_admission import operator_admission
        admission = operator_admission(probe, str(self.model_health.get("endpoint_identity_sha256") or ""))
        if admission is not None:
            evidence["operator_admission"] = admission
            evidence["observed_ready_state"] = probe.get("ready_state")
            return ReadinessEntry(rid, "Model", catalog_status or "active", "ready",
                                  ["operator_approved_model_admission"], evidence)
        ready_state = probe.get("ready_state")
        if isinstance(ready_state, dict):
            ready_status = str(ready_state.get("status") or "")
            evidence["ready_state"] = ready_state
            if ready_status == "ready":
                return ReadinessEntry(
                    rid, "Model", catalog_status or "active", "ready", [], evidence
                )
            if ready_status == "transient_failure":
                return ReadinessEntry(
                    rid,
                    "Model",
                    catalog_status or "active",
                    "transient_failure",
                    list(
                        ready_state.get("reason_codes")
                        or ["model_ready_state_transient"]
                    ),
                    evidence,
                )
            if ready_status in {"blocked", "unavailable"}:
                return ReadinessEntry(
                    rid,
                    "Model",
                    catalog_status or "active",
                    ready_status,
                    list(
                        ready_state.get("reason_codes")
                        or [f"model_ready_state_{ready_status}"]
                    ),
                    evidence,
                )
            return ReadinessEntry(
                rid,
                "Model",
                catalog_status or "active",
                "blocked",
                ["model_ready_state_invalid"],
                evidence,
            )
        status = str(probe.get("status") or "")
        if bool(probe.get("text_ok")) and status in {"ok", "ready", "live_verified"}:
            return ReadinessEntry(rid, "Model", catalog_status or "active", "ready", [], evidence)
        if status in {"transient_failure", "inconclusive"}:
            return ReadinessEntry(
                rid, "Model", catalog_status or "active", "transient_failure", ["live_probe_transient"], evidence
            )
        if status == "unavailable":
            return ReadinessEntry(
                rid, "Model", catalog_status or "active", "unavailable", ["live_probe_unavailable"], evidence
            )
        return ReadinessEntry(
            rid,
            "Model",
            catalog_status or "active",
            "blocked",
            [str(probe.get("error_code") or "live_text_probe_failed")],
            evidence,
        )

    def _agent(self, manifest: dict[str, Any]) -> ReadinessEntry:
        inactive = self._inactive_entry(manifest)
        if inactive:
            return inactive
        rid = str(manifest["resource_id"])
        reasons: list[str] = []
        evidence: dict[str, Any] = {}
        agent = (manifest.get("type_specific") or {}).get("agent") or {}
        try:
            card_path = resolve_file_uri(self.project_root, str(agent.get("agent_card_uri") or ""))
            actual_hash = sha256_bytes(card_path.read_bytes())
            evidence["agent_card_hash"] = actual_hash
            if str(agent.get("agent_card_hash") or "") != actual_hash:
                reasons.append("agent_card_hash_mismatch")
        except ValueError as exc:
            reasons.append(str(exc))
        recommended = list(agent.get("recommended_dependency_ids") or [])
        unresolved = sorted(item for item in recommended if item not in self.catalog_by_id)
        if unresolved:
            reasons.append("recommended_dependencies_unresolved:" + ",".join(unresolved))
        probe = self.agent_evidence.get(rid)
        if not probe:
            reasons.append("real_agent_smoke_not_run")
        else:
            evidence["probe"] = {
                key: probe.get(key)
                for key in ("bound_model_api_id", "success", "error", "cost_metric")
                if key in probe
            }
            if not probe.get("success"):
                reasons.append("real_agent_smoke_failed")
        return ReadinessEntry(
            rid,
            "Agent",
            "active",
            "ready" if not reasons else "blocked",
            reasons,
            evidence,
        )

    def _skill_static(self, manifest: dict[str, Any]) -> ReadinessEntry:
        inactive = self._inactive_entry(manifest)
        if inactive:
            return inactive
        rid = str(manifest["resource_id"])
        reasons: list[str] = []
        evidence: dict[str, Any] = {}
        try:
            self.skill_loader.validate_manifest(manifest)
            entrypoint = resolve_file_uri(
                self.project_root,
                str((manifest.get("execution") or {}).get("uri") or ""),
            )
            actual_source_hash = sha256_bytes(entrypoint.read_bytes())
            actual_package_hash = skill_package_hash(entrypoint.parent)
            evidence.update(
                {
                    "source_hash": actual_source_hash,
                    "package_hash": actual_package_hash,
                    "main_file_bytes": entrypoint.stat().st_size,
                }
            )
            provenance = manifest.get("provenance") or {}
            if str(provenance.get("source_hash") or "") != actual_source_hash:
                reasons.append("skill_source_hash_mismatch")
            if str(provenance.get("package_hash") or "") != actual_package_hash:
                reasons.append("skill_package_hash_mismatch")
        except (SkillPackageError, ValueError, OSError) as exc:
            reasons.append(getattr(exc, "code", None) or str(exc))
        return ReadinessEntry(
            rid,
            "Skill",
            "active",
            "ready" if not reasons else "blocked",
            reasons,
            evidence,
        )

    def build(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        preliminary: dict[str, ReadinessEntry] = {}
        for manifest in self.catalog:
            rid = str(manifest["resource_id"])
            rtype = resource_type(manifest)
            if rtype == "Tool":
                entry = self._tool(manifest)
            elif rtype == "Model":
                entry = self._model(manifest)
            elif rtype == "Agent":
                entry = self._agent(manifest)
            elif rtype == "Skill":
                entry = self._skill_static(manifest)
            elif rtype == "Resource":
                entry = ReadinessEntry(
                    rid, rtype, str(manifest.get("status") or "active"), "inactive", ["rc1_resource_pool_disabled"]
                )
            else:
                entry = ReadinessEntry(
                    rid, rtype, str(manifest.get("status") or ""), "blocked", ["unsupported_resource_type"]
                )
            preliminary[rid] = entry

        # Required Skill dependencies are hard readiness requirements. Optional
        # dependencies are intentionally not considered here.
        for manifest in self.catalog:
            if resource_type(manifest) != "Skill":
                continue
            rid = str(manifest["resource_id"])
            entry = preliminary[rid]
            if entry.readiness_status != "ready":
                continue
            skill = (manifest.get("type_specific") or {}).get("skill") or {}
            required = list(skill.get("required_resource_ids") or [])
            unavailable = [
                dependency
                for dependency in required
                if dependency not in preliminary
                or preliminary[dependency].readiness_status != "ready"
            ]
            portability = str(skill.get("portability") or "")
            if portability == "tool_assisted" and not any(
                resource_type(self.catalog_by_id.get(dependency, {})) == "Tool"
                for dependency in required
            ):
                unavailable.append("<required_ready_tool_not_declared>")
            if unavailable:
                entry.readiness_status = "blocked"
                entry.reasons.append("required_dependencies_not_ready:" + ",".join(unavailable))

        entries = [preliminary[rid].model_dump() for rid in sorted(preliminary)]
        effective = [
            self.catalog_by_id[item["resource_id"]]
            for item in entries
            if item["readiness_status"] == "ready"
        ]
        effective.sort(key=lambda item: (resource_type(item).casefold(), str(item["resource_id"]).casefold()))
        by_type_status = Counter(
            (item["resource_type"], item["readiness_status"]) for item in entries
        )
        report = {
            "schema_version": 1,
            "rc_version": "RC1",
            "generated_at": utc_now(),
            "catalog_sha256": sha256_bytes(canonical_json_bytes(self.catalog)),
            "evidence": {
                "tool_smoke_generated_at": self.tool_smoke.get("generated_at"),
                "model_health_generated_at": self.model_health.get("generated_at"),
                "agent_smoke_timestamp_utc": self.agent_smoke.get("timestamp_utc"),
                "upstream_admission_schema_version": self.upstream_admission.get(
                    "schema_version"
                ),
                "docker_image": self.runtime_lock.get("image"),
                "docker_image_id": self.runtime_lock.get("image_id"),
                "docker_repo_digests": self.runtime_lock.get("repo_digests", []),
            },
            "summary": {
                "catalog_total": len(self.catalog),
                "effective_total": len(effective),
                "by_type_status": {
                    f"{rtype}:{status}": count
                    for (rtype, status), count in sorted(by_type_status.items())
                },
            },
            "effective_resource_ids": [item["resource_id"] for item in effective],
            "resources": entries,
        }
        if self.runtime_lock.get("runtime_backend") == "apptainer":
            for key in ("docker_image", "docker_image_id", "docker_repo_digests"):
                report["evidence"].pop(key, None)
            report["evidence"].update(
                runtime_backend="apptainer",
                runtime_image_sha256=self.runtime_lock.get("runtime_image_sha256"),
                source_oci_digest=self.runtime_lock.get("source_oci_digest"),
            )
        return report, effective


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# SGAR Resource Pool RC1 Readiness Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Catalog total: **{summary['catalog_total']}**",
        f"- Effective total: **{summary['effective_total']}**",
        f"- Catalog SHA256: `{report['catalog_sha256']}`",
        f"- Docker image ID: `{report['evidence'].get('docker_image_id') or 'not built'}`",
        "",
        "## Readiness counts",
        "",
        "| Type and status | Count |",
        "| --- | ---: |",
    ]
    for key, count in summary["by_type_status"].items():
        lines.append(f"| `{key}` | {count} |")
    excluded = [item for item in report["resources"] if item["readiness_status"] != "ready"]
    lines.extend(
        [
            "",
            "## Excluded resources",
            "",
            "| Resource | Type | Status | Reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in excluded:
        reasons = "; ".join(item.get("reasons") or [])
        lines.append(
            f"| `{item['resource_id']}` | {item['resource_type']} | "
            f"{item['readiness_status']} | {reasons} |"
        )
    return "\n".join(lines) + "\n"
