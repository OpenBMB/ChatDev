"""Committed source and activated-system identities for formal SGAR releases."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from .pipeline_control import canonical_json_bytes, canonical_sha256
from .planner import planner_release_prompt_identity
from .release_environment import is_approved_release_branch


RELEASE_SOURCE_SEAL_PROTOCOL = "sgar-release-source-seal-v1"
ACTIVATED_SYSTEM_SEAL_PROTOCOL = "sgar-activated-system-seal-v2"
ReleaseSealStage = Literal["release", "activated"]

_ROOT_SOURCE_NAMES = {
    "build_index.py",
    "cost_calculator.py",
    "retrieval_profiles.py",
    "retrieve.py",
}
_SOURCE_SUFFIXES = {
    ".py",
    ".json",
    ".jsonl",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
}
_PROJECT_SUBTREES = (
    "sgar_mvp/config",
    "sgar_mvp/src",
    "sgar_mvp/tests",
    "tests",
)
_FORMAL_SCRIPT_NAMES = {
    "build_release_probe_admission.py",
    "finalize_release_promotion.py",
    "promote_release_retrieval.py",
    "rebind_release_retrieval.py",
    "rollback_release_retrieval.py",
    "run_release_provider_probes.py",
    "run_live_golden_cases.py",
    "seal_release_source.py",
}
_EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    "profile_cache",
    "runs",
    "readiness",
}
_EXCLUDED_NAMES = {"latest_run.json"}
_ACTIVATED_INDEX_NAMES = {
    "faiss_cap.index",
    "faiss_con.index",
    "resource_meta.pkl",
    "retrieval_profile_audit.json",
    "index_build_manifest.json",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _run_git(project_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def _is_source_file(path: Path, *, subtree: Path) -> bool:
    relative = path.relative_to(subtree)
    if any(part in _EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.name in _EXCLUDED_NAMES:
        return False
    return path.suffix.lower() in _SOURCE_SUFFIXES


def _release_paths(project_root: Path, stage: ReleaseSealStage) -> list[Path]:
    tracked = {
        item.replace("\\", "/")
        for item in _run_git(project_root, "ls-files", "-z").split("\0")
        if item
    }

    def is_tracked(candidate: Path) -> bool:
        return candidate.relative_to(project_root).as_posix() in tracked

    paths: set[Path] = set()
    for name in _ROOT_SOURCE_NAMES:
        candidate = project_root / name
        if candidate.is_file() and is_tracked(candidate):
            paths.add(candidate)
    for name in ("main.py", "real_case_batch.py"):
        candidate = project_root / "sgar_mvp" / name
        if candidate.is_file() and is_tracked(candidate):
            paths.add(candidate)
    for relative in _PROJECT_SUBTREES:
        subtree = project_root / relative
        if not subtree.is_dir():
            continue
        for candidate in subtree.rglob("*"):
            if (
                candidate.is_file()
                and is_tracked(candidate)
                and _is_source_file(candidate, subtree=subtree)
            ):
                paths.add(candidate)
    scripts_root = project_root / "sgar_mvp" / "scripts"
    for name in _FORMAL_SCRIPT_NAMES:
        candidate = scripts_root / name
        if candidate.is_file() and is_tracked(candidate):
            paths.add(candidate)
    resource_root = project_root / "Pool" / "resources"
    if not resource_root.is_dir():
        raise RuntimeError("release_source_seal_resource_pool_missing")
    paths.update(
        path
        for path in resource_root.rglob("*")
        if path.is_file() and is_tracked(path)
    )
    if stage == "activated":
        index_root = project_root / "Pool" / "index_meta"
        for name in _ACTIVATED_INDEX_NAMES:
            candidate = index_root / name
            if not candidate.is_file() or not is_tracked(candidate):
                raise RuntimeError(f"activated_system_index_file_missing:{name}")
            paths.add(candidate)
    return sorted(paths, key=lambda item: item.relative_to(project_root).as_posix())


def _file_hashes(project_root: Path, stage: ReleaseSealStage) -> dict[str, str]:
    return {
        path.relative_to(project_root).as_posix(): _sha256_file(path)
        for path in _release_paths(project_root, stage)
    }


def _source_status(project_root: Path, files: Iterable[str]) -> dict[str, Any]:
    relevant = set(files)
    tracked = {
        item.replace("\\", "/")
        for item in _run_git(project_root, "ls-files", "-z").split("\0")
        if item
    }
    unstaged = {
        item.replace("\\", "/")
        for item in _run_git(
            project_root, "diff", "--relative", "--name-only", "-z", "--no-renames"
        ).split("\0")
        if item
    }
    staged = {
        item.replace("\\", "/")
        for item in _run_git(
            project_root,
            "diff",
            "--cached",
            "--relative",
            "--name-only",
            "-z",
            "--no-renames",
        ).split("\0")
        if item
    }
    relevant_changes: list[str] = []
    for path in sorted(relevant & (unstaged | staged)):
        status = ("M" if path in staged else " ") + ("M" if path in unstaged else " ")
        relevant_changes.append(f"{status} {path}")
    for path in sorted(relevant - tracked):
        relevant_changes.append(f"?? {path}")
    return {
        "framework_source_clean": not relevant_changes,
        "relevant_change_count": len(relevant_changes),
        "relevant_status_sha256": canonical_sha256(relevant_changes),
    }


def loaded_project_module_origins(project_root: Path) -> dict[str, str]:
    """Fail when a loaded SGAR module came from another checkout or package."""

    root = project_root.resolve()
    origins: dict[str, str] = {}
    for name, module in sorted(sys.modules.items()):
        if not (
            name in {"retrieve", "build_index", "retrieval_profiles", "sgar_mvp"}
            or name.startswith("sgar_mvp.")
        ):
            continue
        raw = getattr(module, "__file__", None)
        if not raw:
            continue
        path = Path(raw).resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"release_module_loaded_outside_checkout:{name}:{path}") from exc
        origins[name] = relative
    return origins


def build_release_source_seal(project_root: Path) -> dict[str, Any]:
    """Build ReleaseSourceSealV1 only from a committed, scoped-clean source tree."""

    root = project_root.resolve()
    branch = _run_git(root, "branch", "--show-current")
    if not is_approved_release_branch(branch):
        raise RuntimeError("release_source_seal_branch_invalid")
    files = _file_hashes(root, "release")
    status = _source_status(root, files)
    if not status["framework_source_clean"]:
        raise RuntimeError("release_source_seal_requires_committed_clean_source")
    payload: dict[str, Any] = {
        "protocol": RELEASE_SOURCE_SEAL_PROTOCOL,
        "stage": "release",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "git_branch": branch,
        "git_head": _run_git(root, "rev-parse", "HEAD"),
        "git_tree": _run_git(root, "rev-parse", "HEAD^{tree}"),
        **status,
        "file_count": len(files),
        "files_sha256": files,
        "source_collection_sha256": canonical_sha256(files),
        "loaded_module_origins": loaded_project_module_origins(root),
        "planner_prompt_identity": planner_release_prompt_identity(),
    }
    payload["seal_sha256"] = canonical_sha256(payload)
    return payload


def build_activated_system_seal(
    project_root: Path,
    *,
    parent_release_source_seal_sha256: str,
    promotion_receipt: Path,
) -> dict[str, Any]:
    """Build ActivatedSystemSealV2 after policy/index activation is committed."""

    root = project_root.resolve()
    branch = _run_git(root, "branch", "--show-current")
    if not is_approved_release_branch(branch):
        raise RuntimeError("activated_system_seal_branch_invalid")
    files = _file_hashes(root, "activated")
    status = _source_status(root, files)
    if not status["framework_source_clean"]:
        raise RuntimeError("activated_system_seal_requires_committed_clean_source")
    if _run_git(root, "diff", "--name-only", "-z", "--no-renames") or _run_git(
        root,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--no-renames",
    ):
        raise RuntimeError("activated_system_seal_requires_committed_clean_tree")
    receipt = promotion_receipt.resolve()
    if not receipt.is_file():
        raise RuntimeError("activated_system_promotion_receipt_missing")
    # Function-local import keeps the Source Seal and Promotion modules acyclic
    # while sharing the one formal PromotionReceiptV8 verifier.
    from .release_promotion import _load_and_verify_promotion_receipt

    _load_and_verify_promotion_receipt(
        project_root=root,
        promotion_receipt_path=receipt,
        expected_parent_release_source_seal_sha256=(
            parent_release_source_seal_sha256
        ),
        verify_current_after_hashes=True,
        verify_backups=False,
    )
    payload: dict[str, Any] = {
        "protocol": ACTIVATED_SYSTEM_SEAL_PROTOCOL,
        "stage": "activated",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "git_branch": branch,
        "git_head": _run_git(root, "rev-parse", "HEAD"),
        "git_tree": _run_git(root, "rev-parse", "HEAD^{tree}"),
        **status,
        "file_count": len(files),
        "files_sha256": files,
        "source_collection_sha256": canonical_sha256(files),
        "loaded_module_origins": loaded_project_module_origins(root),
        "planner_prompt_identity": planner_release_prompt_identity(),
        "parent_release_source_seal_sha256": parent_release_source_seal_sha256,
        "promotion_receipt_path": str(receipt),
        "promotion_receipt_file_sha256": _sha256_file(receipt),
    }
    payload["seal_sha256"] = canonical_sha256(payload)
    return payload


def write_source_seal(path: Path, payload: dict[str, Any]) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_bytes(canonical_json_bytes(payload) + b"\n")
    temporary.replace(destination)


def load_and_verify_source_seal(
    path: Path,
    *,
    project_root: Path,
    allowed_stages: tuple[ReleaseSealStage, ...] = ("release",),
) -> dict[str, Any]:
    source = path.resolve()
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    claimed = str(payload.get("seal_sha256") or "")
    unsigned = dict(payload)
    unsigned.pop("seal_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("release_source_seal_hash_mismatch")
    stage = str(payload.get("stage") or "")
    if stage not in allowed_stages:
        raise RuntimeError("release_source_seal_stage_invalid")
    expected_protocol = (
        RELEASE_SOURCE_SEAL_PROTOCOL
        if stage == "release"
        else ACTIVATED_SYSTEM_SEAL_PROTOCOL
    )
    if payload.get("protocol") != expected_protocol:
        raise RuntimeError("release_source_seal_protocol_invalid")
    root = project_root.resolve()
    if Path(str(payload.get("project_root") or "")).resolve() != root:
        raise RuntimeError("release_source_seal_project_root_mismatch")
    if payload.get("git_branch") != _run_git(root, "branch", "--show-current"):
        raise RuntimeError("release_source_seal_branch_drift")
    if payload.get("git_head") != _run_git(root, "rev-parse", "HEAD"):
        raise RuntimeError("release_source_seal_head_drift")
    if payload.get("git_tree") != _run_git(root, "rev-parse", "HEAD^{tree}"):
        raise RuntimeError("release_source_seal_tree_drift")
    current_files = _file_hashes(root, stage)  # detects modified, added, and removed source
    if current_files != payload.get("files_sha256"):
        raise RuntimeError("release_source_seal_file_drift")
    if canonical_sha256(current_files) != payload.get("source_collection_sha256"):
        raise RuntimeError("release_source_seal_collection_mismatch")
    if payload.get("planner_prompt_identity") != planner_release_prompt_identity():
        raise RuntimeError("release_source_seal_planner_prompt_identity_drift")
    status = _source_status(root, current_files)
    if not status["framework_source_clean"]:
        raise RuntimeError("release_source_seal_source_dirty")
    loaded_project_module_origins(root)
    return payload


def source_seal_reference(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol": payload["protocol"],
        "stage": payload["stage"],
        "seal_sha256": payload["seal_sha256"],
        "source_collection_sha256": payload["source_collection_sha256"],
        "git_branch": payload["git_branch"],
        "git_head": payload["git_head"],
        "git_tree": payload["git_tree"],
        "framework_source_clean": payload["framework_source_clean"],
        "planner_prompt_identity": payload["planner_prompt_identity"],
    }


__all__ = [
    "ACTIVATED_SYSTEM_SEAL_PROTOCOL",
    "RELEASE_SOURCE_SEAL_PROTOCOL",
    "build_activated_system_seal",
    "build_release_source_seal",
    "load_and_verify_source_seal",
    "loaded_project_module_origins",
    "source_seal_reference",
    "write_source_seal",
]
