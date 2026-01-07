"""Edge condition configuration models."""

from dataclasses import dataclass, field, fields, replace
from typing import Any, Dict, Mapping, Type, TypeVar, cast

from entity.enum_options import enum_options_from_values
from schema_registry import (
    SchemaLookupError,
    get_edge_condition_schema,
    iter_edge_condition_schemas,
)

from entity.configs.base import (
    BaseConfig,
    ChildKey,
    ConfigError,
    ConfigFieldSpec,
    ensure_list,
    optional_bool,
    require_mapping,
    require_str,
    extend_path,
)
from utils.function_catalog import get_function_catalog
from utils.function_manager import EDGE_FUNCTION_DIR


def _serialize_config(config: BaseConfig) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for field_obj in fields(config):
        if field_obj.name == "path":
            continue
        payload[field_obj.name] = getattr(config, field_obj.name)
    return payload


class EdgeConditionTypeConfig(BaseConfig):
    """Base helper for condition-specific configuration classes."""

    def display_label(self) -> str:
        return self.__class__.__name__

    def to_external_value(self) -> Any:
        return _serialize_config(self)


@dataclass
class FunctionEdgeConditionConfig(EdgeConditionTypeConfig):
    """Configuration for function-based conditions."""

    name: str = "true"

    FIELD_SPECS = {
        "name": ConfigFieldSpec(
            name="name",
            display_name="Function Name",
            type_hint="str",
            required=True,
            default="true",
            description="Function Name or 'true' (indicating perpetual satisfaction)",
        )
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "FunctionEdgeConditionConfig":
        if data is None:
            return cls(name="true", path=path)
        mapping = require_mapping(data, path)
        function_name = require_str(mapping, "name", path, allow_empty=False)
        return cls(name=function_name, path=path)

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        name_spec = specs.get("name")
        if name_spec is None:
            return specs

        catalog = get_function_catalog(EDGE_FUNCTION_DIR)
        names = catalog.list_function_names()
        metadata = catalog.list_metadata()
        description = name_spec.description or "Conditional function name"
        if catalog.load_error:
            description = f"{description} (Loading failed: {catalog.load_error})"
        elif not names:
            description = f"{description} (No available conditional functions found)"

        if "true" not in names:
            names.insert(0, "true")
        descriptions = {"true": "Default condition (always met)"}
        for name in names:
            if name == "true":
                continue
            meta = metadata.get(name)
            descriptions[name] = (meta.description if meta else None) or "The conditional function is not described."
        specs["name"] = replace(
            name_spec,
            enum=names or None,
            enum_options=enum_options_from_values(names, descriptions, preserve_label_case=True),
            description=description,
        )
        return specs

    def display_label(self) -> str:
        return self.name or "true"

    def to_external_value(self) -> Any:
        return self.name or "true"


def _normalize_keyword_list(value: Any, path: str) -> list[str]:
    items = ensure_list(value)
    normalized: list[str] = []
    for idx, item in enumerate(items):
        if not isinstance(item, str):
            raise ConfigError("entries must be strings", extend_path(path, f"[{idx}]"))
        normalized.append(item)
    return normalized


@dataclass
class KeywordEdgeConditionConfig(EdgeConditionTypeConfig):
    """Configuration for declarative keyword checks."""

    any_keywords: list[str] = field(default_factory=list)
    none_keywords: list[str] = field(default_factory=list)
    regex_patterns: list[str] = field(default_factory=list)
    case_sensitive: bool = True
    default: bool = False

    FIELD_SPECS = {
        "any": ConfigFieldSpec(
            name="any",
            display_name="Contains keywords",
            type_hint="list[str]",
            required=False,
            description="Returns True if any keyword is matched.",
        ),
        "none": ConfigFieldSpec(
            name="none",
            display_name="Exclude keywords",
            type_hint="list[str]",
            required=False,
            description="If any of the excluded keywords are matched, return False (highest priority).",
        ),
        "regex": ConfigFieldSpec(
            name="regex",
            display_name="Regular expressions",
            type_hint="list[str]",
            required=False,
            description="Returns True if any regular expression is matched.",
            advance=True,
        ),
        "case_sensitive": ConfigFieldSpec(
            name="case_sensitive",
            display_name="case sensitive",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether to distinguish between uppercase and lowercase letters (default is true).",
        ),
        # "default": ConfigFieldSpec(
        #     name="default",
        #     display_name="Default Result",
        #     type_hint="bool",
        #     required=False,
        #     default=False,
        #     description="Return value when no condition matches; defaults to False",
        #     advance=True,
        # ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "KeywordEdgeConditionConfig":
        mapping = require_mapping(data, path)
        any_keywords = _normalize_keyword_list(mapping.get("any", []), extend_path(path, "any"))
        none_keywords = _normalize_keyword_list(mapping.get("none", []), extend_path(path, "none"))
        regex_patterns = _normalize_keyword_list(mapping.get("regex", []), extend_path(path, "regex"))
        case_sensitive = optional_bool(mapping, "case_sensitive", path, default=True)
        default_value = optional_bool(mapping, "default", path, default=False)

        if not (any_keywords or none_keywords or regex_patterns):
            raise ConfigError("keyword condition requires any/none/regex", path)

        return cls(
            any_keywords=any_keywords,
            none_keywords=none_keywords,
            regex_patterns=regex_patterns,
            case_sensitive=True if case_sensitive is None else bool(case_sensitive),
            default=False if default_value is None else bool(default_value),
            path=path,
        )

    def display_label(self) -> str:
        return f"keyword(any={len(self.any_keywords)}, none={len(self.none_keywords)}, regex={len(self.regex_patterns)})"

    def to_external_value(self) -> Any:
        payload: Dict[str, Any] = {}
        if self.any_keywords:
            payload["any"] = list(self.any_keywords)
        if self.none_keywords:
            payload["none"] = list(self.none_keywords)
        if self.regex_patterns:
            payload["regex"] = list(self.regex_patterns)
        payload["case_sensitive"] = self.case_sensitive
        payload["default"] = self.default
        return payload


TConditionConfig = TypeVar("TConditionConfig", bound=EdgeConditionTypeConfig)


@dataclass
class EdgeConditionConfig(BaseConfig):
    """Wrapper config that stores condition type + concrete config."""

    type: str
    config: EdgeConditionTypeConfig

    FIELD_SPECS = {
        "type": ConfigFieldSpec(
            name="type",
            display_name="Condition Type",
            type_hint="str",
            required=True,
            description="Select which condition implementation to run (function, keyword, etc.) so the engine can resolve the schema.",
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Condition Config",
            type_hint="object",
            required=True,
            description="Payload interpreted by the chosen function or any/none/regex lists for keyword mode.",
        ),
    }

    @classmethod
    def _normalize_value(cls, value: Any, path: str) -> Mapping[str, Any]:
        if value is None:
            return {"type": "function", "config": {"name": "true"}}
        if isinstance(value, bool):
            if value:
                return {"type": "function", "config": {"name": "true"}}
            return {"type": "function", "config": {"name": "always_false"}}
        if isinstance(value, str):
            return {"type": "function", "config": {"name": value}}
        return require_mapping(value, path)

    @classmethod
    def from_dict(cls, data: Any, *, path: str) -> "EdgeConditionConfig":
        mapping = cls._normalize_value(data, path)
        condition_type = require_str(mapping, "type", path)
        config_payload = mapping.get("config")
        config_path = extend_path(path, "config")

        try:
            schema = get_edge_condition_schema(condition_type)
        except SchemaLookupError as exc:
            raise ConfigError(f"unknown condition type '{condition_type}'", extend_path(path, "type")) from exc
        if config_payload is None:
            raise ConfigError("condition config is required", config_path)
        condition_config = schema.config_cls.from_dict(config_payload, path=config_path)
        return cls(type=condition_type, config=condition_config, path=path)

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, Type[BaseConfig]]:
        return {
            ChildKey(field="config", value=name): schema.config_cls
            for name, schema in iter_edge_condition_schemas().items()
        }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_edge_condition_schemas()
            names = list(registrations.keys())
            descriptions = {name: schema.summary for name, schema in registrations.items()}
            specs["type"] = replace(
                type_spec,
                enum=names,
                enum_options=enum_options_from_values(names, descriptions, preserve_label_case=True),
            )
        return specs

    def display_label(self) -> str:
        return self.config.display_label()

    def to_external_value(self) -> Any:
        if self.type == "function":
            return self.config.to_external_value()
        return {
            "type": self.type,
            "config": self.config.to_external_value(),
        }

    def as_config(self, expected_type: Type[TConditionConfig]) -> TConditionConfig | None:
        config = self.config
        if isinstance(config, expected_type):
            return cast(TConditionConfig, config)
        return None
