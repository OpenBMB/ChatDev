"""Pool-blind, deterministic capability context for Planner V6.

The catalog deliberately exposes role-shaped affordances rather than concrete
resources.  It is built locally from sealed capability cards and cannot select
or authorize an executable resource.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Literal

from pydantic import Field, model_validator

from .capability_cards import CapabilityCard
from .pipeline_control import FrozenContract, canonical_sha256


PLANNER_CAPABILITY_SURFACE_PROTOCOL = "sgar-planner-capability-surface-v1"
PLANNER_CAPABILITY_CATALOG_PROTOCOL = "sgar-planner-capability-catalog-v1"


class PlannerCapabilitySurfaceV1(FrozenContract):
    """One abstract role affordance that is safe to show to the Planner."""

    protocol: Literal[PLANNER_CAPABILITY_SURFACE_PROTOCOL] = (
        PLANNER_CAPABILITY_SURFACE_PROTOCOL
    )
    role_archetype: str = Field(min_length=1)
    capability_summary: tuple[str, ...] = Field(min_length=1)
    supported_materials: tuple[str, ...]
    deliverable_kinds: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    surface_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "PlannerCapabilitySurfaceV1":
        for values, field_name in (
            (self.capability_summary, "capability_summary"),
            (self.supported_materials, "supported_materials"),
            (self.deliverable_kinds, "deliverable_kinds"),
            (self.limitations, "limitations"),
        ):
            if tuple(values) != tuple(sorted(set(values))):
                raise ValueError(f"planner_capability_surface_{field_name}_not_canonical")
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"surface_sha256"})
        )
        if self.surface_sha256 and self.surface_sha256 != expected:
            raise ValueError("planner_capability_surface_sha256_mismatch")
        object.__setattr__(self, "surface_sha256", expected)
        return self

    def model_projection(self) -> dict[str, object]:
        """Return only the five advisory fields allowed in Planner input."""

        return {
            "role_archetype": self.role_archetype,
            "capability_summary": list(self.capability_summary),
            "supported_materials": list(self.supported_materials),
            "deliverable_kinds": list(self.deliverable_kinds),
            "limitations": list(self.limitations),
        }


class PlannerCapabilityCatalogV1(FrozenContract):
    """Sealed sidecar identity plus the pool-blind model projection."""

    protocol: Literal[PLANNER_CAPABILITY_CATALOG_PROTOCOL] = (
        PLANNER_CAPABILITY_CATALOG_PROTOCOL
    )
    resource_pool_sha256: str
    builder_sha256: str
    source_card_count: int = Field(ge=0)
    surfaces: tuple[PlannerCapabilitySurfaceV1, ...] = Field(min_length=1, max_length=16)
    catalog_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "PlannerCapabilityCatalogV1":
        names = tuple(item.role_archetype for item in self.surfaces)
        if names != tuple(sorted(set(names))):
            raise ValueError("planner_capability_catalog_roles_not_canonical")
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"catalog_sha256"})
        )
        if self.catalog_sha256 and self.catalog_sha256 != expected:
            raise ValueError("planner_capability_catalog_sha256_mismatch")
        object.__setattr__(self, "catalog_sha256", expected)
        return self

    def model_projection(self) -> list[dict[str, object]]:
        return [item.model_projection() for item in self.surfaces]


_ROLE_TEMPLATES: dict[str, dict[str, tuple[str, ...]]] = {
    "artifact transformation specialist": {
        "signals": ("convert", "transform", "extract", "parse", "serialize", "file"),
        "capabilities": (
            "Can convert authorized artifacts between declared representations",
            "Can preserve typed content while producing a consumable intermediate artifact",
        ),
        "materials": ("files", "structured data", "text"),
        "deliverables": ("converted artifacts", "structured data"),
    },
    "code engineering specialist": {
        "signals": ("code", "python", "javascript", "repository", "source", "test"),
        "capabilities": (
            "Can inspect and modify declared source artifacts",
            "Can produce code and test-oriented deliverables",
        ),
        "materials": ("code", "directories", "text"),
        "deliverables": ("code", "test artifacts"),
    },
    "document and text analyst": {
        "signals": ("document", "markdown", "pdf", "plaintext", "text", "summar"),
        "capabilities": (
            "Can inspect authorized textual materials",
            "Can extract and organize evidence-grounded textual findings",
        ),
        "materials": ("documents", "markdown", "text"),
        "deliverables": ("analytical notes", "structured findings"),
    },
    "evidence-grounded researcher": {
        "signals": ("evidence", "research", "search", "citation", "reference", "source"),
        "capabilities": (
            "Can synthesize findings from explicitly authorized evidence",
            "Can preserve source boundaries in an analytical deliverable",
        ),
        "materials": ("documents", "references", "text"),
        "deliverables": ("evidence summaries", "research findings"),
    },
    "metrics analyst": {
        "signals": ("aggregate", "calculate", "metric", "number", "statistic", "table"),
        "capabilities": (
            "Can calculate row-level and aggregate metrics from declared inputs",
            "Can produce independently checkable quantitative results",
        ),
        "materials": ("structured data", "tabular data"),
        "deliverables": ("metrics", "structured data"),
    },
    "policy and requirements interpreter": {
        "signals": ("contract", "policy", "requirement", "rule", "schema", "specification"),
        "capabilities": (
            "Can interpret declared rules and requirements",
            "Can express comparison criteria without selecting runtime resources",
        ),
        "materials": ("policies", "requirements", "text"),
        "deliverables": ("comparison criteria", "requirement interpretations"),
    },
    "report and communication author": {
        "signals": ("markdown", "report", "write", "generate", "plaintext", "document"),
        "capabilities": (
            "Can synthesize supplied findings into a coherent user-facing deliverable",
            "Can follow declared content and formatting requirements",
        ),
        "materials": ("analytical findings", "structured data", "text"),
        "deliverables": ("analytical reports", "user-facing documents"),
    },
    "schema validation specialist": {
        "signals": ("json", "schema", "validate", "verification", "check", "csv"),
        "capabilities": (
            "Can validate a declared artifact against structural requirements",
            "Can produce explicit validation findings",
        ),
        "materials": ("json", "structured data", "tabular data"),
        "deliverables": ("validation findings", "verification results"),
    },
    "structured data analyst": {
        "signals": ("csv", "json", "record", "structured", "table", "tabular"),
        "capabilities": (
            "Can inspect complete structured datasets",
            "Can produce structured analytical results",
        ),
        "materials": ("csv", "json", "tabular data"),
        "deliverables": ("analytical reports", "structured data"),
    },
    "visual content analyst": {
        "signals": ("image", "vision", "visual", "pixel", "diagram", "screenshot"),
        "capabilities": (
            "Can inspect authorized visual materials",
            "Can produce evidence-grounded visual observations",
        ),
        "materials": ("images", "visual documents"),
        "deliverables": ("structured observations", "visual findings"),
    },
}

_CATALOG_BUILDER_SHA256 = canonical_sha256(_ROLE_TEMPLATES)
_FORBIDDEN_VISIBLE_TERMS = (
    "resource_id", "operation_id", "provider", "endpoint", "reasoning_effort",
    "entrypoint", "resource count", "resource ranking",
)


def _card_signals(card: CapabilityCard) -> set[str]:
    values: list[str] = []
    values.extend(card.domains)
    values.extend(card.outputs)
    values.extend(item.kind for item in card.inputs)
    for operation in card.capability_operations:
        values.extend(operation.accepted_artifact_types)
        values.extend(operation.produced_artifact_types)
        values.extend(operation.modalities)
        values.extend(operation.output_semantics)
    text = " ".join(values).lower().replace("-", "_")
    return {token for token in text.replace("/", " ").replace("_", " ").split() if token}


def build_planner_capability_catalog(
    cards: Iterable[CapabilityCard],
) -> PlannerCapabilityCatalogV1:
    """Aggregate active manifest cards into a deterministic pool-blind catalog."""

    source_cards = tuple(
        sorted(
            (card for card in cards if card.availability != "unavailable"),
            key=lambda item: (item.resource_id, item.card_sha256),
        )
    )
    signal_counts: defaultdict[str, int] = defaultdict(int)
    all_signals: set[str] = set()
    for card in source_cards:
        signals = _card_signals(card)
        all_signals.update(signals)
        for signal in signals:
            signal_counts[signal] += 1

    surfaces: list[PlannerCapabilitySurfaceV1] = []
    for role, template in sorted(_ROLE_TEMPLATES.items()):
        matched = {
            signal
            for signal in template["signals"]
            if any(signal in observed or observed in signal for observed in all_signals)
        }
        if not matched:
            continue
        limitations = (
            "Does not identify or authorize a concrete runtime resource",
            "Does not imply support for undeclared inputs or external side effects",
        )
        surfaces.append(
            PlannerCapabilitySurfaceV1(
                role_archetype=role,
                capability_summary=tuple(sorted(template["capabilities"])),
                supported_materials=tuple(sorted(template["materials"])),
                deliverable_kinds=tuple(sorted(template["deliverables"])),
                limitations=tuple(sorted(limitations)),
            )
        )

    if not surfaces:
        surfaces.append(
            PlannerCapabilitySurfaceV1(
                role_archetype="general artifact specialist",
                capability_summary=(
                    "Can transform explicitly authorized inputs into a declared artifact",
                ),
                supported_materials=("declared artifacts",),
                deliverable_kinds=("declared artifacts",),
                limitations=(
                    "Does not identify or authorize a concrete runtime resource",
                    "Does not imply support for undeclared inputs or external side effects",
                ),
            )
        )
    model_visible = str([item.model_projection() for item in surfaces]).lower()
    if any(term in model_visible for term in _FORBIDDEN_VISIBLE_TERMS):
        raise ValueError("planner_capability_catalog_identity_leak")
    concrete_ids = {
        value.lower()
        for card in source_cards
        for value in (
            card.resource_id,
            *(item.capability_operation_id for item in card.capability_operations),
        )
        if value
    }
    if any(identifier in model_visible for identifier in concrete_ids):
        raise ValueError("planner_capability_catalog_concrete_identity_leak")
    return PlannerCapabilityCatalogV1(
        resource_pool_sha256=canonical_sha256(
            [card.model_dump(mode="json") for card in source_cards]
        ),
        builder_sha256=_CATALOG_BUILDER_SHA256,
        source_card_count=len(source_cards),
        surfaces=tuple(surfaces),
    )


__all__ = [
    "PLANNER_CAPABILITY_CATALOG_PROTOCOL",
    "PLANNER_CAPABILITY_SURFACE_PROTOCOL",
    "PlannerCapabilityCatalogV1",
    "PlannerCapabilitySurfaceV1",
    "build_planner_capability_catalog",
]
