"""Immutable production policy for SGAR semantic control roles."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .pipeline_control import FrozenContract, canonical_sha256


CONTROL_ROLE_POLICY_PROTOCOL = "sgar-control-role-policy-v2"
CONTROL_ROLE_POLICY_EXPERIMENT_PROTOCOL = "sgar-control-role-policy-v3"
CONTROL_ROLE_POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "control_role_policy.json"
)
CONTROL_MODEL_PROFILE_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "model_profile.json"
)
ControlRole = Literal[
    "profiler",
    "planner",
    "plan_compiler",
    "plan_adaptation",
    "evaluator",
]


class ControlRoleInvocationPolicyV1(FrozenContract):
    """Exact request policy for one production control role."""

    role: ControlRole
    resource_id: str = "model.gpt_5_6_sol.v1"
    api_model_id: str = "gpt-5.6-sol"
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] | None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    allow_model_failover: Literal[False] = False
    response_mode: Literal["native_strict_schema"] = "native_strict_schema"
    role_policy_sha256: str = ""

    @field_validator("resource_id")
    @classmethod
    def _resource_id_is_canonical(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not re.fullmatch(r"model\.[A-Za-z0-9][A-Za-z0-9_.:-]*", normalized):
            raise ValueError("control_role_resource_id_invalid")
        return normalized

    @field_validator("api_model_id")
    @classmethod
    def _api_model_id_is_present(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("control_role_api_model_id_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "ControlRoleInvocationPolicyV1":
        if self.reasoning_effort is not None and self.temperature is not None:
            raise ValueError("control_role_reasoning_and_temperature_conflict")
        projection = self.model_dump(mode="python", exclude={"role_policy_sha256"})
        expected = canonical_sha256(projection)
        if self.role_policy_sha256 and self.role_policy_sha256 != expected:
            raise ValueError("control_role_invocation_policy_sha256_mismatch")
        object.__setattr__(self, "role_policy_sha256", expected)
        return self

    def request_fields(self) -> dict[str, Any]:
        """Provider request fields authorized by this policy."""

        fields: dict[str, str | float] = {}
        if self.reasoning_effort is not None:
            fields["reasoning_effort"] = self.reasoning_effort
        if self.temperature is not None:
            fields["temperature"] = self.temperature
        return fields


class ControlRolePolicyV1(FrozenContract):
    """No-failover policy for every production semantic control role."""

    protocol: Literal[
        CONTROL_ROLE_POLICY_PROTOCOL,
        CONTROL_ROLE_POLICY_EXPERIMENT_PROTOCOL,
    ] = CONTROL_ROLE_POLICY_PROTOCOL
    roles: tuple[ControlRoleInvocationPolicyV1, ...]
    policy_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ControlRolePolicyV1":
        names = tuple(item.role for item in self.roles)
        if names != (
            "profiler",
            "planner",
            "plan_compiler",
            "plan_adaptation",
            "evaluator",
        ):
            raise ValueError("control_role_policy_roles_invalid")
        projection = self.model_dump(mode="python", exclude={"policy_sha256"})
        expected = canonical_sha256(projection)
        if self.policy_sha256 and self.policy_sha256 != expected:
            raise ValueError("control_role_policy_sha256_mismatch")
        object.__setattr__(self, "policy_sha256", expected)
        return self

    def for_role(self, role: ControlRole) -> ControlRoleInvocationPolicyV1:
        for item in self.roles:
            if item.role == role:
                return item
        raise ValueError(f"control_role_policy_role_missing:{role}")


class ControlModelProfileV1(FrozenContract):
    """Human-edited source of truth for one SGAR control-plane model bundle."""

    protocol: Literal["sgar-control-model-profile-v1"] = "sgar-control-model-profile-v1"
    roles: tuple[ControlRoleInvocationPolicyV1, ...]
    evaluation_mode: Literal["off", "semantic"] = "off"
    embedding_model: str = Field(min_length=1)
    embedding_candidate_id: str = Field(min_length=1)
    profile_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ControlModelProfileV1":
        names = tuple(item.role for item in self.roles)
        if names != ("profiler", "planner", "plan_compiler", "plan_adaptation", "evaluator"):
            raise ValueError("control_model_profile_roles_invalid")
        if self.for_role("plan_adaptation").resource_id != self.for_role("plan_compiler").resource_id:
            raise ValueError("control_model_profile_adaptation_compiler_mismatch")
        if self.for_role("plan_adaptation").api_model_id != self.for_role("plan_compiler").api_model_id:
            raise ValueError("control_model_profile_adaptation_compiler_mismatch")
        projection = self.model_dump(mode="python", exclude={"profile_sha256"})
        expected = canonical_sha256(projection)
        if self.profile_sha256 and self.profile_sha256 != expected:
            raise ValueError("control_model_profile_sha256_mismatch")
        object.__setattr__(self, "profile_sha256", expected)
        return self

    def for_role(self, role: ControlRole) -> ControlRoleInvocationPolicyV1:
        return ControlRolePolicyV1(protocol=CONTROL_ROLE_POLICY_EXPERIMENT_PROTOCOL, roles=self.roles).for_role(role)

    def policy(self, *, protocol: Literal[CONTROL_ROLE_POLICY_PROTOCOL, CONTROL_ROLE_POLICY_EXPERIMENT_PROTOCOL]) -> ControlRolePolicyV1:
        return ControlRolePolicyV1(protocol=protocol, roles=self.roles)


def load_control_role_policy(
    path: Path = CONTROL_ROLE_POLICY_PATH,
) -> ControlRolePolicyV1:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    policy = ControlRolePolicyV1.model_validate(payload)
    if path.resolve() == CONTROL_ROLE_POLICY_PATH.resolve() and CONTROL_MODEL_PROFILE_PATH.is_file():
        profile = ControlModelProfileV1.model_validate(
            json.loads(CONTROL_MODEL_PROFILE_PATH.read_text(encoding="utf-8-sig"))
        )
        require_policy_matches_model_profile(policy, profile)
    return policy


def load_control_model_profile(
    path: Path = CONTROL_MODEL_PROFILE_PATH,
) -> ControlModelProfileV1:
    return ControlModelProfileV1.model_validate(
        json.loads(path.read_text(encoding="utf-8-sig"))
    )


def require_policy_matches_model_profile(
    policy: ControlRolePolicyV1,
    profile: ControlModelProfileV1,
) -> None:
    if tuple(policy.roles) != tuple(profile.roles):
        raise ValueError("control_policy_model_profile_mismatch")


__all__ = [
    "CONTROL_ROLE_POLICY_PATH",
    "CONTROL_MODEL_PROFILE_PATH",
    "CONTROL_ROLE_POLICY_PROTOCOL",
    "CONTROL_ROLE_POLICY_EXPERIMENT_PROTOCOL",
    "ControlRole",
    "ControlRoleInvocationPolicyV1",
    "ControlRolePolicyV1",
    "ControlModelProfileV1",
    "load_control_role_policy",
    "load_control_model_profile",
    "require_policy_matches_model_profile",
]
