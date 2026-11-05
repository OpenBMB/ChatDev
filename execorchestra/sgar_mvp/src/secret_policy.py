"""Fail-closed formal credential policy and value-safe sanitization."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .pipeline_control import canonical_sha256


FORMAL_SECRET_POLICY_PROTOCOL = "formal-secret-policy-v1"
FORMAL_PROVIDER_CREDENTIAL_ENV_ALLOWLIST = frozenset(
    {
        "LLM_API_KEY",
    }
)
_SECRET_KEY = re.compile(
    r"(?i)(?:api[_-]?key|apikey|secret|password|credential|^llm[_-]?key$|"
    r"^(?:(?:access|refresh|bearer|auth)[_-]?)?token$)"
)
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
_ENV_REFERENCE = re.compile(r"^(?:env:([A-Z][A-Z0-9_]{1,127})|\$\{([A-Z][A-Z0-9_]{1,127})\})$")
_BEARER = re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_WINDOWS_HOST_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[a-z]:[\\/]|\\\\)[^\r\n\t\"'<>|]*"
)


class FormalSecretPolicyError(RuntimeError):
    def __init__(self, failure_code: str, *, occurrence_locators: Sequence[str] = ()) -> None:
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.occurrence_locators = tuple(occurrence_locators)


@dataclass(frozen=True)
class FormalSecretPolicyEvidence:
    protocol: str
    valid: bool
    checked_secret_fields: int
    literal_secret_occurrence_locators: tuple[str, ...]
    referenced_environment_names: tuple[str, ...]
    credential_env_allowlist_sha256: str
    policy_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "valid": self.valid,
            "checked_secret_fields": self.checked_secret_fields,
            "literal_secret_occurrence_locators": list(self.literal_secret_occurrence_locators),
            "referenced_environment_names": list(self.referenced_environment_names),
            "credential_env_allowlist_sha256": self.credential_env_allowlist_sha256,
            "policy_sha256": self.policy_sha256,
        }


def _environment_reference(value: Any) -> str | None:
    if isinstance(value, str):
        match = _ENV_REFERENCE.fullmatch(value.strip())
        if match:
            return match.group(1) or match.group(2)
    if isinstance(value, Mapping) and set(value) == {"env"}:
        name = str(value.get("env") or "").strip()
        if _ENV_NAME.fullmatch(name):
            return name
    return None


def _is_empty(value: Any) -> bool:
    return value is None or value == ""


def validate_formal_secret_config(
    config: Mapping[str, Any],
    *,
    allowed_environment_names: Sequence[str] = tuple(FORMAL_PROVIDER_CREDENTIAL_ENV_ALLOWLIST),
    raise_on_error: bool = True,
) -> FormalSecretPolicyEvidence:
    """Reject literal credentials while never retaining their values."""

    allowed = frozenset(str(item) for item in allowed_environment_names)
    literal: list[str] = []
    references: list[str] = []
    checked = 0

    def walk(value: Any, locator: str) -> None:
        nonlocal checked
        if isinstance(value, Mapping):
            for key, item in value.items():
                child = f"{locator}.{key}" if locator else str(key)
                if _SECRET_KEY.search(str(key)):
                    checked += 1
                    reference = _environment_reference(item)
                    if reference is not None:
                        if reference not in allowed:
                            literal.append(child)
                        else:
                            references.append(reference)
                    elif not _is_empty(item):
                        literal.append(child)
                else:
                    walk(item, child)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                walk(item, f"{locator}[{index}]")

    walk(config, "config")
    locators = tuple(sorted(set(literal)))
    env_names = tuple(sorted(set(references)))
    policy_projection = {
        "protocol": FORMAL_SECRET_POLICY_PROTOCOL,
        "credential_environment_allowlist": sorted(allowed),
        "literal_secret_values": "reject",
        "secret_serialization": "forbidden",
    }
    evidence = FormalSecretPolicyEvidence(
        protocol=FORMAL_SECRET_POLICY_PROTOCOL,
        valid=not locators,
        checked_secret_fields=checked,
        literal_secret_occurrence_locators=locators,
        referenced_environment_names=env_names,
        credential_env_allowlist_sha256=canonical_sha256(sorted(allowed)),
        policy_sha256=canonical_sha256(policy_projection),
    )
    if locators and raise_on_error:
        raise FormalSecretPolicyError(
            "formal_literal_credential_forbidden",
            occurrence_locators=locators,
        )
    return evidence


def sanitize_sensitive_text(
    text: str,
    *,
    secret_values: Sequence[str] = (),
    host_roots: Sequence[str] = (),
    hidden_values: Sequence[str] = (),
) -> tuple[str, dict[str, int]]:
    """Sanitize diagnostics without recording any removed value."""

    sanitized = str(text)
    counts = {"secret": 0, "host_path": 0, "hidden": 0, "authorization": 0}
    for label, values, replacement in (
        ("secret", secret_values, "<redacted-secret>"),
        ("hidden", hidden_values, "<redacted-hidden>"),
        ("host_path", host_roots, "<runtime-locator>"),
    ):
        for value in sorted({str(item) for item in values if str(item)}, key=len, reverse=True):
            occurrences = sanitized.count(value)
            if occurrences:
                sanitized = sanitized.replace(value, replacement)
                counts[label] += occurrences
            alternate = value.replace("\\", "/")
            if alternate != value:
                occurrences = sanitized.count(alternate)
                if occurrences:
                    sanitized = sanitized.replace(alternate, replacement)
                    counts[label] += occurrences
    sanitized, count = _BEARER.subn("<redacted-authorization>", sanitized)
    counts["authorization"] += count
    sanitized, count = _WINDOWS_HOST_PATH.subn("<runtime-locator>", sanitized)
    counts["host_path"] += count
    return sanitized, counts


def secret_value_sha256(value: str) -> str:
    """Hash-only helper for private audit comparisons."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


__all__ = [
    "FORMAL_PROVIDER_CREDENTIAL_ENV_ALLOWLIST",
    "FORMAL_SECRET_POLICY_PROTOCOL",
    "FormalSecretPolicyError",
    "FormalSecretPolicyEvidence",
    "sanitize_sensitive_text",
    "secret_value_sha256",
    "validate_formal_secret_config",
]
