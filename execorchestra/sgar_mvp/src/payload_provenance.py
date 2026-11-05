"""Hash-bound provenance for model-bound payloads.

Raw source material is kept in memory for leakage decisions.  Formal records
receive only hashes and DAG identities, so the audit itself cannot disclose a
hidden value or a private host path.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence

from .path_policy import is_private_host_path_value


PAYLOAD_PROVENANCE_PROTOCOL = "model-request-provenance-v2"
OBSERVABLE_ATOM_PROTOCOL = "observable-payload-atoms-v1"
ALLOWED_SOURCE_ORIGINS = frozenset(
    {
        "public_case",
        "public_fixture",
        "candidate_bundle",
        "validated_plan",
        "current_run_checkpoint_output",
        "current_run_step_output",
        "static_framework",
    }
)


class PayloadProvenanceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


_JSON_NUMBER_RE = re.compile(
    r"(?<![\w.])-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])"
)
_JSON_LITERAL_RE = re.compile(r"(?<!\w)(?:true|false|null)(?!\w)", re.IGNORECASE)
_WORD_RE = re.compile(r"(?u)\w+")


def _normalized_text(value: str) -> str:
    return " ".join(str(value).split())


def _string_atom_hashes(value: str) -> set[str]:
    """Return typed atoms that are directly observable in a text source.

    Model-bound data crosses representation boundaries repeatedly: a public
    Markdown cell containing ``2`` may later become the JSON number ``2`` and a
    structured value may later be embedded in a prompt string.  Exact-leaf
    hashing alone treats those two public representations as unrelated.  This
    routine provides the single, format-independent observation rule used on
    hidden material, registered sources, and outgoing payloads.

    The derivation is deliberately lexical rather than task-aware.  It does not
    inspect Case IDs, filenames, schemas, or expected answers.
    """

    hashes: set[str] = set()
    if not value:
        return hashes
    hashes.add(canonical_hash(value))
    normalized = _normalized_text(value)
    if normalized and normalized != value:
        hashes.add(canonical_hash(normalized))
    whole_forms = {value, normalized}
    for token in _WORD_RE.findall(value):
        # Numeric lexemes are handled as complete JSON numbers below.  Treating
        # the ``0`` and ``25`` fragments of ``0.25`` as independent words
        # creates low-entropy atoms that were never separately observable.
        if token.isdecimal():
            continue
        if token not in whole_forms:
            hashes.add(canonical_hash(token))
    for match in _JSON_NUMBER_RE.finditer(value):
        token = match.group(0)
        try:
            parsed = json.loads(token)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if token not in whole_forms:
            hashes.add(canonical_hash(token))
        hashes.add(canonical_hash(parsed))
    for match in _JSON_LITERAL_RE.finditer(value):
        token = match.group(0).casefold()
        parsed = {"true": True, "false": False, "null": None}[token]
        if match.group(0) not in whole_forms:
            hashes.add(canonical_hash(match.group(0)))
        hashes.add(canonical_hash(parsed))
    return hashes


def observable_scalar_hashes(value: Any) -> set[str]:
    """Hash all scalar observations, including typed literals embedded in text."""

    hashes: set[str] = set()
    if isinstance(value, Mapping):
        for child in value.values():
            hashes.update(observable_scalar_hashes(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            hashes.update(observable_scalar_hashes(child))
    elif isinstance(value, str):
        hashes.update(_string_atom_hashes(value))
    elif value is None or isinstance(value, (bool, int, float)):
        hashes.add(canonical_hash(value))
        # Provider envelopes encode structured primitives into prompt JSON.
        # Record both the typed value and its canonical JSON lexeme so the
        # structured->text and text->structured directions are symmetric.
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        hashes.add(canonical_hash(rendered))
    return hashes


def material_contains_text(value: Any, token: str) -> bool:
    """Return whether a normalized text token is observable in string leaves.

    Searching leaves avoids JSON escaping artifacts.  Short word-like tokens
    use lexical boundaries so a one-character secret is not explained merely
    because it occurs inside an unrelated word.
    """

    needle = _normalized_text(token)
    if not needle:
        return False
    if isinstance(value, Mapping):
        return any(material_contains_text(child, needle) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(material_contains_text(child, needle) for child in value)
    if not isinstance(value, str):
        return False
    haystack = _normalized_text(value)
    if not haystack:
        return False
    if len(needle) >= 8:
        return needle in haystack
    escaped = re.escape(needle)
    prefix = r"(?<!\w)" if needle[0].isalnum() or needle[0] == "_" else ""
    suffix = r"(?!\w)" if needle[-1].isalnum() or needle[-1] == "_" else ""
    return re.search(prefix + escaped + suffix, haystack) is not None


def build_public_execution_context(
    schema_version: str,
    fixture_entries: Sequence[Mapping[str, Any]],
) -> str:
    """Build the canonical public context supplied to downstream execution."""

    blocks = [
        f"{schema_version} frozen task inputs. Do not invent files or facts."
    ]
    for entry in fixture_entries:
        blocks.append(
            f"\n[fixture {entry['fixture_id']}] role={entry['role']} path={entry['path']}"
        )
        if entry.get("content_available_as_context"):
            blocks.append(str(entry.get("content") or ""))
        elif entry.get("path_kind") == "directory":
            blocks.append(
                json.dumps(
                    {"directory_entries": entry.get("directory_entries") or []},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
    blocks.append(
        "\nReturn only the requested final artifact; it will be checked by a deterministic validator."
    )
    return "\n".join(blocks)


@dataclass(frozen=True)
class PayloadSource:
    source_id: str
    origin: str
    material: Any
    content_hash: str
    parent_source_ids: tuple[str, ...]
    producer: Mapping[str, Any]

    def audit_view(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "origin": self.origin,
            "content_hash": self.content_hash,
            "parent_source_ids": list(self.parent_source_ids),
            "producer": dict(self.producer),
        }


class PayloadSourceRegistry:
    """Per-record source registry with strict identity and parent checks."""

    def __init__(self, *, subtask_id: str, mode: str, attempt_id: str) -> None:
        self.identity = {
            "subtask_id": str(subtask_id),
            "mode": str(mode),
            "attempt_id": str(attempt_id),
        }
        if not all(self.identity.values()):
            raise PayloadProvenanceError(
                "provenance_identity_incomplete",
                "Payload provenance requires subtask, mode, and attempt identities.",
            )
        self._sources: Dict[str, PayloadSource] = {}
        self._default_source_ids: list[str] = []

    @property
    def default_source_ids(self) -> tuple[str, ...]:
        return tuple(self._default_source_ids)

    def register(
        self,
        source_id: str,
        *,
        origin: str,
        material: Any,
        parent_source_ids: Iterable[str] = (),
        producer: Mapping[str, Any] | None = None,
        default: bool = False,
    ) -> PayloadSource:
        source_name = str(source_id or "").strip()
        source_origin = str(origin or "").strip()
        if not source_name:
            raise PayloadProvenanceError(
                "provenance_source_id_missing", "Payload source id is required."
            )
        if source_origin not in ALLOWED_SOURCE_ORIGINS:
            raise PayloadProvenanceError(
                "provenance_origin_forbidden",
                f"Payload source origin is not authorized: {source_origin}",
            )
        parents = tuple(dict.fromkeys(str(item) for item in parent_source_ids))
        missing = [item for item in parents if item not in self._sources]
        if missing:
            raise PayloadProvenanceError(
                "provenance_parent_missing",
                f"Payload source has unknown parents: {missing}",
            )
        if source_origin in {
            "current_run_checkpoint_output",
            "current_run_step_output",
        } and not parents:
            raise PayloadProvenanceError(
                "provenance_step_output_parents_missing",
                "Current-run step output requires explicit upstream provenance.",
            )
        producer_payload = {
            str(key): value for key, value in dict(producer or {}).items()
        }
        mismatched_identity = {
            key: value
            for key, value in producer_payload.items()
            if key in self.identity and str(value) != self.identity[key]
        }
        if mismatched_identity:
            raise PayloadProvenanceError(
                "provenance_producer_identity_mismatch",
                "Payload source producer cannot override the registry identity: "
                + ", ".join(sorted(mismatched_identity)),
            )
        source = PayloadSource(
            source_id=source_name,
            origin=source_origin,
            material=material,
            content_hash=canonical_hash(material),
            parent_source_ids=parents,
            producer={**self.identity, **producer_payload},
        )
        existing = self._sources.get(source_name)
        if existing is not None and existing.audit_view() != source.audit_view():
            raise PayloadProvenanceError(
                "provenance_source_redefinition",
                f"Payload source was redefined: {source_name}",
            )
        self._sources[source_name] = source
        if default and source_name not in self._default_source_ids:
            self._default_source_ids.append(source_name)
        return source

    def require(self, source_ids: Sequence[str]) -> tuple[PayloadSource, ...]:
        normalized = tuple(dict.fromkeys(str(item) for item in source_ids))
        missing = [item for item in normalized if item not in self._sources]
        if missing:
            raise PayloadProvenanceError(
                "provenance_source_missing",
                f"Model request references unknown payload sources: {missing}",
            )
        return tuple(self._sources[item] for item in normalized)

    def request_attestation(
        self,
        *,
        request_kind: str,
        source_ids: Sequence[str],
        request_identity: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        sources = self.require(source_ids)
        requested_identity = {
            str(key): value for key, value in dict(request_identity or {}).items()
        }
        mismatched = {
            key: value
            for key, value in requested_identity.items()
            if key in self.identity and str(value) != self.identity[key]
        }
        if mismatched:
            raise PayloadProvenanceError(
                "provenance_identity_mismatch",
                f"Model request identity does not match registry: {sorted(mismatched)}",
            )
        identity = {**self.identity, **requested_identity}
        payload = {
            "protocol": PAYLOAD_PROVENANCE_PROTOCOL,
            "request_kind": str(request_kind),
            "identity": identity,
            "sources": [source.audit_view() for source in sources],
        }
        return {**payload, "provenance_hash": canonical_hash(payload)}

    def material_for(self, source_ids: Sequence[str]) -> tuple[Any, ...]:
        return tuple(source.material for source in self.require(source_ids))


def _host_path_occurrences(value: Any, path: str = "payload") -> list[str]:
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            matches.extend(_host_path_occurrences(child, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            matches.extend(_host_path_occurrences(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if is_private_host_path_value(value):
            matches.append(path)
    return matches


class BoundProductionPayloadGuard:
    def __init__(
        self,
        owner: "ProductionModelPayloadGuard",
        *,
        request_kind: str,
        source_ids: Sequence[str],
        request_identity: Mapping[str, Any] | None,
    ) -> None:
        self.owner = owner
        self.request_kind = str(request_kind)
        self.source_ids = tuple(dict.fromkeys(str(item) for item in source_ids))
        self.request_identity = dict(request_identity or {})
        self._refresh()

    def _refresh(self) -> None:
        self.attestation = self.owner.registry.request_attestation(
            request_kind=self.request_kind,
            source_ids=self.source_ids,
            request_identity=self.request_identity,
        )
        self.provenance_hash = str(self.attestation["provenance_hash"])

    def register_source(self, source_id: str, **kwargs: Any) -> Dict[str, Any]:
        audit = self.owner.register_source(source_id, **kwargs)
        if source_id not in self.source_ids:
            self.source_ids = (*self.source_ids, str(source_id))
        self._refresh()
        return audit

    def __call__(self, payload: Mapping[str, Any]) -> None:
        self.owner.check(payload, self)


class ProductionModelPayloadGuard:
    """Source-bound production guard without any experiment hidden material."""

    forbidden_keys = frozenset(
        {
            "api_key",
            "authorization",
            "password",
            "secret",
            "gold",
            "validator_result",
            "hidden_reference_output_path",
        }
    )

    def __init__(self, registry: PayloadSourceRegistry, *, default_source_ids: Sequence[str] | None = None) -> None:
        self.registry = registry
        self._default_source_ids = tuple(default_source_ids) if default_source_ids is not None else None
        if self._default_source_ids is not None:
            registry.require(self._default_source_ids)
        self.checks: list[dict[str, Any]] = []

    @property
    def default_source_ids(self) -> tuple[str, ...]:
        return self._default_source_ids if self._default_source_ids is not None else self.registry.default_source_ids

    def derive_parent_source_ids(
        self,
        *,
        upstream_source_ids: Sequence[str] = (),
    ) -> tuple[str, ...]:
        """Resolve a derived source from the registry, never symbolic aliases.

        Defaults identify the currently authorized public, pool, static, and
        sealed-plan sources. Explicit upstream IDs add only already-registered
        step/checkpoint outputs. ``require`` keeps the boundary fail-closed.
        """

        resolved = tuple(
            dict.fromkeys((*self.default_source_ids, *upstream_source_ids))
        )
        self.registry.require(resolved)
        return resolved

    def register_source(
        self,
        source_id: str,
        *,
        origin: str,
        material: Any,
        parent_source_ids: Sequence[str] = (),
        producer: Mapping[str, Any] | None = None,
        default: bool = False,
    ) -> Dict[str, Any]:
        return self.registry.register(
            source_id,
            origin=origin,
            material=material,
            parent_source_ids=parent_source_ids,
            producer=producer,
            default=default,
        ).audit_view()

    def for_request(
        self,
        request_kind: str,
        *,
        source_ids: Sequence[str] | None = None,
        request_identity: Mapping[str, Any] | None = None,
    ) -> BoundProductionPayloadGuard:
        return BoundProductionPayloadGuard(
            self,
            request_kind=request_kind,
            source_ids=source_ids or self.default_source_ids,
            request_identity=request_identity,
        )

    def __call__(self, payload: Mapping[str, Any]) -> None:
        self.for_request("unspecified")(payload)

    def check(
        self,
        payload: Mapping[str, Any],
        bound: BoundProductionPayloadGuard,
    ) -> None:
        leaked_keys: list[str] = []

        def inspect(value: Any, path: str) -> None:
            if isinstance(value, Mapping):
                for key, child in value.items():
                    if str(key).strip().casefold() in self.forbidden_keys:
                        leaked_keys.append(f"{path}.{key}")
                    inspect(child, f"{path}.{key}")
            elif isinstance(value, (list, tuple)):
                for index, child in enumerate(value):
                    inspect(child, f"{path}[{index}]")

        inspect(payload, "payload")
        host_paths = _host_path_occurrences(payload)
        check = {
            "passed": not leaked_keys and not host_paths,
            "payload_sha256": canonical_hash(payload),
            "provenance_hash": bound.provenance_hash,
            "source_ids": list(bound.source_ids),
            "source_hashes": [
                item["content_hash"] for item in bound.attestation["sources"]
            ],
            "request_kind": bound.request_kind,
            "request_identity": dict(bound.attestation["identity"]),
            "leaked_key_paths": leaked_keys,
            "host_path_locations": host_paths,
        }
        self.checks.append(check)
        if not check["passed"]:
            raise PayloadProvenanceError(
                "production_model_payload_guard_failed",
                "Production model payload contains a forbidden key or host path.",
            )
