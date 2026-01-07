"""FastAPI router for dynamic configuration schema endpoints."""

from typing import Any, Dict, List, Mapping

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from entity.config_loader import load_design_from_mapping
from entity.configs import ConfigError
from utils.schema_exporter import build_schema_response, SchemaResolutionError


router = APIRouter(prefix="/api/config", tags=["config-schema"])


class SchemaRequest(BaseModel):
    breadcrumbs: List[Mapping[str, Any]] | None = Field(
        default=None,
        description="Breadcrumb path starting from DesignConfig, e.g. [{\"node\":\"DesignConfig\",\"field\":\"graph\"}]",
    )


class SchemaValidateRequest(SchemaRequest):
    document: str = Field(..., description="Full YAML/JSON content")


def _resolve_schema(breadcrumbs: List[Mapping[str, Any]] | None) -> Dict[str, Any] | None:
    if not breadcrumbs:
        return None
    try:
        return build_schema_response(breadcrumbs)
    except SchemaResolutionError:
        return None


@router.post("/schema")
def get_schema(request: SchemaRequest) -> Dict[str, Any]:
    try:
        return build_schema_response(request.breadcrumbs)
    except SchemaResolutionError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc


@router.post("/schema/validate")
def validate_document(request: SchemaValidateRequest) -> Dict[str, Any]:
    try:
        parsed = yaml.safe_load(request.document)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail={"message": "invalid_yaml", "error": str(exc)}) from exc

    if not isinstance(parsed, Mapping):
        raise HTTPException(status_code=422, detail={"message": "document_root_not_mapping"})

    try:
        load_design_from_mapping(parsed)
    except ConfigError as exc:
        return {
            "valid": False,
            "error": str(exc),
            "path": exc.path,
            "schema": _resolve_schema(request.breadcrumbs),
        }

    return {
        "valid": True,
        "schema": _resolve_schema(request.breadcrumbs),
    }


__all__ = ["router"]
