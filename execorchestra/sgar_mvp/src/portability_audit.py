"""Independent host/hidden/secret scan for formal run projections."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Sequence

from .pipeline_control import canonical_sha256
from .path_policy import is_private_host_path_value


RUN_PORTABILITY_AUDIT_PROTOCOL = "sgar-run-portability-audit-v1"
_AUTHORIZATION_VALUE = re.compile(
    r"(?i)\b(?P<scheme>bearer|basic)\s+(?P<token>[A-Za-z0-9._~+/=-]{4,})"
)
_TEXT_EXTENSIONS = {".json", ".jsonl", ".log", ".md", ".txt"}
_EXCLUDED_PREFIXES = (
    "artifacts/blobs/",
    "artifacts/quarantined/",
    "inputs/blobs/",
    "inputs/trees/",
    "work/",
    "recovery/temporary_tools/",
    "pytest/",
    "final_output",
    "final_bundle/",
)


def _is_authorized_input_content(
    locator: str,
    semantic_path: tuple[str, ...],
) -> bool:
    return (
        locator == "inputs/input_snapshot.json"
        and semantic_path[-1:] == ("inline_text",)
        and "inputs" in semantic_path
        and "descriptor" in semantic_path
    )


def _iter_semantic_strings(
    value: Any,
    *,
    locator: str,
    semantic_path: tuple[str, ...] = (),
) -> Iterable[tuple[str, bool]]:
    if isinstance(value, str):
        yield value, not _is_authorized_input_content(locator, semantic_path)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            yield key_text, True
            yield from _iter_semantic_strings(
                item,
                locator=locator,
                semantic_path=(*semantic_path, key_text),
            )
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _iter_semantic_strings(
                item,
                locator=locator,
                semantic_path=(*semantic_path, str(index)),
            )


def _structured_strings(
    path: Path,
    content: str,
    *,
    locator: str,
) -> tuple[tuple[tuple[str, bool], ...], bool]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            return ((content, True),), False
        return tuple(_iter_semantic_strings(value, locator=locator)), True
    if suffix == ".jsonl":
        strings: list[tuple[str, bool]] = []
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                return ((content, True),), False
            strings.extend(_iter_semantic_strings(value, locator=locator))
        return tuple(strings), True
    return ((content, True),), True


def _contains_host_path(value: str, host_needles: Iterable[str]) -> bool:
    return bool(
        is_private_host_path_value(value)
        or any(needle and needle in value for needle in host_needles)
    )


def _contains_authorization_value(value: str) -> bool:
    """Distinguish Basic credentials from ordinary phrases such as basic coverage.

    RFC 7617 encodes a user-id/password pair separated by a colon. Known
    secret-value checks remain independent of this authorization classifier.
    """
    for match in _AUTHORIZATION_VALUE.finditer(value):
        token = match.group("token")
        if match.group("scheme").lower() == "bearer":
            if len(token) >= 8:
                return True
            continue
        try:
            decoded = base64.b64decode(token + "=" * (-len(token) % 4), validate=True)
        except (binascii.Error, ValueError):
            continue
        if b":" in decoded:
            return True
    return False


def _formal_projection_files(root: Path) -> tuple[Path, ...]:
    selected: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        locator = path.relative_to(root).as_posix()
        padded = f"/{locator}/"
        if any(
            locator == prefix.rstrip("/")
            or locator.startswith(prefix)
            or f"/{prefix}" in padded
            for prefix in _EXCLUDED_PREFIXES
        ):
            continue
        if path.suffix.lower() in _TEXT_EXTENSIONS:
            selected.append(path)
    return tuple(sorted(selected, key=lambda item: item.relative_to(root).as_posix()))


def audit_run_portability(
    run_dir: str | Path,
    *,
    host_roots: Sequence[str | Path] = (),
    secret_values: Sequence[str] = (),
    hidden_values: Sequence[str] = (),
) -> dict[str, Any]:
    """Scan only formal records, never public input or artifact payload bytes."""

    root = Path(run_dir).resolve()
    host_needles: set[str] = set()
    for item in host_roots:
        value = str(item)
        if not value:
            continue
        host_needles.add(value)
        host_needles.add(value.replace("\\", "/"))
        host_needles.add(value.replace("\\", "\\\\"))
    secret_needles = tuple(sorted({str(item) for item in secret_values if str(item)}, key=len, reverse=True))
    hidden_needles = tuple(sorted({str(item) for item in hidden_values if str(item)}, key=len, reverse=True))
    host_occurrences: list[str] = []
    secret_occurrences: list[str] = []
    hidden_occurrences: list[str] = []
    unreadable: list[str] = []
    scanned: list[dict[str, Any]] = []

    for path in _formal_projection_files(root):
        locator = path.relative_to(root).as_posix()
        try:
            content = path.read_text(encoding="utf-8-sig", errors="strict")
        except (OSError, UnicodeError):
            unreadable.append(locator)
            continue
        scanned.append({"locator": locator, "sha256": canonical_sha256(content), "byte_size": path.stat().st_size})
        semantic_strings, structured_valid = _structured_strings(
            path,
            content,
            locator=locator,
        )
        if not structured_valid:
            unreadable.append(locator)
        if any(
            _contains_host_path(value, host_needles)
            for value, _scan_sensitive in semantic_strings
        ):
            host_occurrences.append(locator)
        if any(
            _contains_authorization_value(value)
            or any(needle in value for needle in secret_needles)
            for value, scan_sensitive in semantic_strings
            if scan_sensitive
        ):
            secret_occurrences.append(locator)
        if any(
            needle in value
            for value, scan_sensitive in semantic_strings
            if scan_sensitive
            for needle in hidden_needles
        ):
            hidden_occurrences.append(locator)

    projection = {
        "protocol": RUN_PORTABILITY_AUDIT_PROTOCOL,
        "valid": not (host_occurrences or secret_occurrences or hidden_occurrences or unreadable),
        "scanned_file_count": len(scanned),
        "scanned_projection_sha256": canonical_sha256(scanned),
        "host_path_occurrences": sorted(set(host_occurrences)),
        "secret_occurrences": sorted(set(secret_occurrences)),
        "hidden_value_occurrences": sorted(set(hidden_occurrences)),
        "unreadable_formal_records": sorted(set(unreadable)),
    }
    return {**projection, "audit_sha256": canonical_sha256(projection)}


__all__ = ["RUN_PORTABILITY_AUDIT_PROTOCOL", "audit_run_portability"]
