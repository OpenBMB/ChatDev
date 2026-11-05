"""Local launch defaults shared by direct-script and module execution.

These settings locate existing authority; they never create or relax admission.
Machine-specific paths belong in the ignored config.json, not tracked source.
"""
from __future__ import annotations

from .direct_network import configure_direct_network

import argparse
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


class RuntimeBootstrapError(ValueError):
    pass


def prepare_retrieval_environment(runtime_authority: str) -> tuple[str, ...]:
    """Git runs use checkout/config authority, never inherited release overrides.

    Clear before probes AND lazy backend import. Release-mode validation remains
    strict and unchanged; only this process's environment is affected.
    """
    if runtime_authority not in {"git", "release"}:
        raise RuntimeBootstrapError("local_runtime_authority_invalid")
    if runtime_authority == "release":
        return ()
    ignored = tuple(name for name in (
        "SGAR_INDEX_DIR", "SGAR_RETRIEVAL_POLICY_PATH",
        "SGAR_SEALED_LOCAL_VALIDATION", "SGAR_SOURCE_SEAL_PATH",
    ) if name in os.environ)
    for name in ignored:
        os.environ.pop(name)
    if ignored:
        logging.getLogger(__name__).warning(
            "Git runtime ignores inherited release retrieval settings: %s; "
            "using checkout index and configured policy", ", ".join(ignored),
        )
    return ignored


_FIELDS = {
    "runtime_authority", "output_root", "temporary_directory",
    "pip_cache_directory", "release_storage_root", "activated_system_seal_path",
    "control_probe_receipt_path", "control_role_policy_path",
    "retrieval_policy_path", "evaluator_policy_path", "model_profile_path",
    "auto_refresh_control_receipt",
}


def configure_runtime(
    args: argparse.Namespace, *, config: Mapping[str, Any], project_root: Path,
) -> None:
    """Apply configured process-local defaults before creating a run workspace.

    Explicit CLI options override configured CLI defaults. Configured storage
    locations override stale shell environment values; absent settings preserve
    the environment. Source, receipt, health and execution gates remain downstream.
    """
    settings = config.get("runtime_settings", {})
    if not isinstance(settings, Mapping) or set(settings) - _FIELDS:
        raise RuntimeBootstrapError("local_runtime_settings_invalid")
    for key, value in settings.items():
        if key == "auto_refresh_control_receipt":
            if not isinstance(value, bool):
                raise RuntimeBootstrapError("local_runtime_setting_value_invalid")
            continue
        if not isinstance(value, str) or not value.strip():
            raise RuntimeBootstrapError("local_runtime_setting_value_invalid")
    configured_authority = settings.get("runtime_authority", "git")
    if configured_authority not in {"git", "release"}:
        raise RuntimeBootstrapError("local_runtime_authority_invalid")
    configure_direct_network()
    # Keep project-scoped resource credentials and dependency probes anchored
    # to the checkout even when the launcher is invoked from another cwd.
    os.environ["SGAR_PROJECT_ROOT"] = str(project_root.resolve())
    args.runtime_authority = args.runtime_authority or configured_authority
    prepare_retrieval_environment(args.runtime_authority)

    def location(value: str) -> Path:
        path = Path(value).expanduser()
        return (path if path.is_absolute() else project_root / path).resolve()

    if args.output_root is None:
        args.output_root = str(location(settings.get("output_root", "sgar_mvp/runs")))
    # Validate all configured path values before applying any environment changes.
    paths = {
        key: location(value)
        for key, value in settings.items()
        if key not in {"runtime_authority", "auto_refresh_control_receipt"}
    }
    if "temporary_directory" in paths:
        temporary = paths["temporary_directory"]
        temporary.mkdir(parents=True, exist_ok=True)
        for name in ("TEMP", "TMP", "TMPDIR"):
            os.environ[name] = str(temporary)
        # tempfile may already have cached a directory during module imports.
        tempfile.tempdir = str(temporary)
    if "pip_cache_directory" in paths:
        os.environ["PIP_CACHE_DIR"] = str(paths["pip_cache_directory"])
    if args.runtime_authority == "release":
        for key, env_name in (
            ("release_storage_root", "SGAR_RELEASE_STORAGE_ROOT"),
            ("activated_system_seal_path", "SGAR_ACTIVATED_SYSTEM_SEAL_PATH"),
        ):
            if key in paths:
                os.environ[env_name] = str(paths[key])
        if not str(os.environ.get("SGAR_ACTIVATED_SYSTEM_SEAL_PATH") or "").strip():
            raise RuntimeBootstrapError("local_release_activation_path_missing")
