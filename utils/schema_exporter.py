"""Schema exporter for dynamic configuration metadata."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Type

from entity.configs import BaseConfig
from entity.configs.graph import DesignConfig

SCHEMA_VERSION = "0.1.0"


class SchemaResolutionError(ValueError):
    """Raised when breadcrumbs fail to resolve to a config node."""


@dataclass(frozen=True)
class Breadcrumb:
    """Describes one hop in the config tree."""

    node: str
    field: str | None = None
    value: Any | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Breadcrumb":
        node = str(data.get("node")) if data.get("node") else ""
        if not node:
            raise SchemaResolutionError("breadcrumb entry missing 'node'")
        field = data.get("field")
        if field is not None:
            field = str(field)
        index = data.get("index")
        if index is not None and not isinstance(index, int):
            raise SchemaResolutionError("breadcrumb 'index' must be integer when provided")
        value = data.get("value")
        return cls(node=node, field=field, value=value)

    def to_json(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"node": self.node}
        if self.field is not None:
            payload["field"] = self.field
        if self.value is not None:
            payload["value"] = self.value
        return payload


def _normalize_breadcrumbs(raw: Sequence[Mapping[str, Any]] | None) -> List[Breadcrumb]:
    if not raw:
        return []
    return [Breadcrumb.from_mapping(item) for item in raw]


def _resolve_config_class(
    breadcrumbs: Sequence[Breadcrumb],
    *,
    root_cls: Type[BaseConfig] = DesignConfig,
) -> Type[BaseConfig]:
    current_cls: Type[BaseConfig] = root_cls
    for crumb in breadcrumbs:
        if crumb.node != current_cls.__name__:
            raise SchemaResolutionError(
                f"breadcrumb node '{crumb.node}' does not match current config '{current_cls.__name__}'"
            )
        if crumb.field is None:
            continue
        child_cls = current_cls.resolve_child(crumb.field, crumb.value)
        if child_cls is None:
            spec = current_cls.field_specs().get(crumb.field)
            if not spec or spec.child is None:
                raise SchemaResolutionError(
                    f"field '{crumb.field}' on {current_cls.__name__} is not navigable"
                )
            child_cls = spec.child
        current_cls = child_cls
    return current_cls


def _serialize_field(config_cls: Type[BaseConfig], name: str, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
    field_spec = spec_dict[name]
    data = field_spec.to_json()
    routes = [
        {
            "childKey": key.to_json(),
            "childNode": target.__name__,
        }
        for key, target in config_cls.child_routes().items()
        if key.field == name
    ]
    if routes:
        data["childRoutes"] = routes
    return data


def _ordered_field_names(specs: Mapping[str, Any]) -> List[str]:
    """Return field names with required ones first while keeping relative order."""

    items = list(specs.items())
    required_names = [name for name, spec in items if getattr(spec, "required", False)]
    optional_names = [name for name, spec in items if not getattr(spec, "required", False)]
    return required_names + optional_names


def _hash_payload(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def build_schema_response(
    breadcrumbs_raw: Sequence[Mapping[str, Any]] | None = None,
    *,
    root_cls: Type[BaseConfig] = DesignConfig,
) -> Dict[str, Any]:
    """Return a JSON-serializable schema response for the provided breadcrumbs."""

    breadcrumbs = _normalize_breadcrumbs(breadcrumbs_raw)
    target_cls = _resolve_config_class(breadcrumbs, root_cls=root_cls)
    schema_node = target_cls.collect_schema()
    field_specs = target_cls.field_specs()
    ordered_fields = _ordered_field_names(field_specs)
    fields_payload = [_serialize_field(target_cls, name, field_specs) for name in ordered_fields]

    response = {
        "schemaVersion": SCHEMA_VERSION,
        "node": schema_node.node,
        "fields": fields_payload,
        "constraints": [constraint.to_json() for constraint in schema_node.constraints],
        "breadcrumbs": [crumb.to_json() for crumb in breadcrumbs],
    }
    response["cacheKey"] = _hash_payload({"node": schema_node.node, "breadcrumbs": response["breadcrumbs"]})
    return response


__all__ = [
    "Breadcrumb",
    "SchemaResolutionError",
    "build_schema_response",
]
