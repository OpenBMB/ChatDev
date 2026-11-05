"""Semantic evidence location; independent of provider and execution mode."""
from typing import Any, Literal

from pydantic import BaseModel, model_serializer, model_validator


class EvidenceSourceDeclaration(BaseModel):
    evidence_source_scope: Literal["supplied_materials", "external_sources", "mixed"] | None = None

    external_acquisition_mode: Literal["required", "if_needed"] | None = None

    external_discovery_mode: Literal["required", "if_needed"] | None = None

    @model_validator(mode="after")
    def _validate_acquisition_mode(self):
        if self.external_acquisition_mode == "if_needed" and self.evidence_source_scope != "mixed":
            raise ValueError("conditional_acquisition_requires_mixed_scope")
        if self.external_acquisition_mode == "required" and self.evidence_source_scope == "supplied_materials":
            raise ValueError("external_acquisition_conflicts_with_local_scope")
        if self.external_discovery_mode is not None and self.evidence_source_scope not in {"external_sources", "mixed"}:
            raise ValueError("external_discovery_requires_external_scope")
        return self

    @model_serializer(mode="wrap")
    def _serialize_evidence_scope(self, handler: Any) -> dict[str, Any]:
        value = handler(self)
        if self.evidence_source_scope is None:
            value.pop("evidence_source_scope", None)
        if self.external_acquisition_mode is None:
            value.pop("external_acquisition_mode", None)
        if self.external_discovery_mode is None:
            value.pop("external_discovery_mode", None)
        return value
