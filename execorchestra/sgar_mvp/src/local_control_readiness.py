"""Reuse exact control-role health evidence for a local Git checkout.

The receipt retains its original source provenance. Local admission checks the
current endpoint, role policy, probe request, prompt and schema; it does not
attest that the current checkout is a sealed release. Candidate health remains
independent. This loader never sends requests or discovers another receipt.
"""
from pathlib import Path
from typing import Any, Mapping

from .control_role_policy import ControlRolePolicyV1
from .release_provider_receipt import load_and_verify_release_provider_probe_receipt


def load_git_control_probe_receipt(
    project_root: str | Path, *, config: Mapping[str, Any],
    expected_endpoint_identity_sha256: str,
    control_role_policy: ControlRolePolicyV1 | None = None,
) -> tuple[Path, dict[str, Any]]:
    raw = config.get("runtime_settings", {}).get(
        "control_probe_receipt_path",
        "sgar_mvp/runtime_state/control_role_probe_receipt.json",
    )
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("git_control_probe_receipt_path_invalid")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(project_root) / path
    path = path.resolve()
    if not path.is_file():
        raise RuntimeError("git_control_probe_receipt_missing")
    return path, load_and_verify_release_provider_probe_receipt(
        path,
        expected_endpoint_identity_sha256=expected_endpoint_identity_sha256,
        control_role_policy=control_role_policy,
    )
