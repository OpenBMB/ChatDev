"""Edge payload processor configuration dataclasses."""

from dataclasses import dataclass, field, fields, replace
from typing import Any, Dict, Mapping, Type, TypeVar, cast

from entity.enum_options import enum_options_from_values
from utils.function_catalog import get_function_catalog
from utils.function_manager import EDGE_PROCESSOR_FUNCTION_DIR
from schema_registry import (
    SchemaLookupError,
    get_edge_processor_schema,
    iter_edge_processor_schemas,
)
from entity.configs.base import (
    BaseConfig,
    ChildKey,
    ConfigError,
    ConfigFieldSpec,
    ensure_list,
    optional_bool,
    optional_str,
    require_mapping,
    require_str,
    extend_path,
)


def _serialize_config(config: BaseConfig) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for field_obj in fields(config):
        if field_obj.name == "path":
            continue
        payload[field_obj.name] = getattr(config, field_obj.name)
    return payload


class EdgeProcessorTypeConfig(BaseConfig):
    """Base helper class for payload processor configs."""

    def display_label(self) -> str:
        return self.__class__.__name__

    def to_external_value(self) -> Any:
        return _serialize_config(self)




_NO_MATCH_DESCRIPTIONS = {
    "pass": "Leave the payload untouched when no match is found.",
    "default": "Apply default_value (or empty string) if nothing matches.",
    "drop": "Discard the payload entirely when the regex does not match.",
}


@dataclass
class RegexEdgeProcessorConfig(EdgeProcessorTypeConfig):
    """Configuration for regex-based payload extraction."""

    pattern: str = ""
    group: str | int | None = None
    case_sensitive: bool = True
    multiline: bool = False
    dotall: bool = False
    multiple: bool = False
    template: str | None = None
    on_no_match: str = "pass"
    default_value: str | None = None

    FIELD_SPECS = {
        "pattern": ConfigFieldSpec(
            name="pattern",
            display_name="Regex Pattern",
            type_hint="str",
            required=True,
            description="Python regular expression used to extract content.",
        ),
        "group": ConfigFieldSpec(
            name="group",
            display_name="Capture Group",
            type_hint="str",
            required=False,
            description="Capture group name or index. Defaults to the entire match.",
        ),
        "case_sensitive": ConfigFieldSpec(
            name="case_sensitive",
            display_name="Case Sensitive",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether the regex should be case sensitive.",
        ),
        "multiline": ConfigFieldSpec(
            name="multiline",
            display_name="Multiline Flag",
            type_hint="bool",
            required=False,
            default=False,
            description="Enable multiline mode (re.MULTILINE).",
            advance=True,
        ),
        "dotall": ConfigFieldSpec(
            name="dotall",
            display_name="Dotall Flag",
            type_hint="bool",
            required=False,
            default=False,
            description="Enable dotall mode (re.DOTALL).",
            advance=True,
        ),
        "multiple": ConfigFieldSpec(
            name="multiple",
            display_name="Return Multiple Matches",
            type_hint="bool",
            required=False,
            default=False,
            description="Whether to collect all matches instead of only the first.",
            advance=True,
        ),

        "template": ConfigFieldSpec(
            name="template",
            display_name="Output Template",
            type_hint="str",
            required=False,
            description="Optional template applied to the extracted value. Use '{match}' placeholder.",
            advance=True,
        ),
        "on_no_match": ConfigFieldSpec(
            name="on_no_match",
            display_name="No Match Behavior",
            type_hint="enum",
            required=False,
            default="pass",
            enum=["pass", "default", "drop"],
            description="Behavior when no match is found.",
            enum_options=enum_options_from_values(
                list(_NO_MATCH_DESCRIPTIONS.keys()),
                _NO_MATCH_DESCRIPTIONS,
                preserve_label_case=True,
            ),
            advance=True,
        ),
        "default_value": ConfigFieldSpec(
            name="default_value",
            display_name="Default Value",
            type_hint="str",
            required=False,
            description="Fallback content when on_no_match=default.",
            advance=True,
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "RegexEdgeProcessorConfig":
        mapping = require_mapping(data, path)
        pattern = require_str(mapping, "pattern", path, allow_empty=False)
        group_value = mapping.get("group")
        group_normalized: str | int | None = None
        if group_value is not None:
            if isinstance(group_value, int):
                group_normalized = group_value
            elif isinstance(group_value, str):
                if group_value.isdigit():
                    group_normalized = int(group_value)
                else:
                    group_normalized = group_value
            else:
                raise ConfigError("group must be str or int", extend_path(path, "group"))
        multiple = optional_bool(mapping, "multiple", path, default=False)
        case_sensitive = optional_bool(mapping, "case_sensitive", path, default=True)
        multiline = optional_bool(mapping, "multiline", path, default=False)
        dotall = optional_bool(mapping, "dotall", path, default=False)
        on_no_match = optional_str(mapping, "on_no_match", path) or "pass"
        if on_no_match not in {"pass", "default", "drop"}:
            raise ConfigError("on_no_match must be pass, default or drop", extend_path(path, "on_no_match"))

        template = optional_str(mapping, "template", path)
        default_value = optional_str(mapping, "default_value", path)

        return cls(
            pattern=pattern,
            group=group_normalized,
            case_sensitive=True if case_sensitive is None else bool(case_sensitive),
            multiline=bool(multiline) if multiline is not None else False,
            dotall=bool(dotall) if dotall is not None else False,
            multiple=bool(multiple) if multiple is not None else False,
            template=template,
            on_no_match=on_no_match,
            default_value=default_value,
            path=path,
        )

    def display_label(self) -> str:
        return f"regex({self.pattern})"


@dataclass
class FunctionEdgeProcessorConfig(EdgeProcessorTypeConfig):
    """Configuration for function-based payload processors."""

    name: str = ""

    FIELD_SPECS = {
        "name": ConfigFieldSpec(
            name="name",
            display_name="Function Name",
            type_hint="str",
            required=True,
            description="Name of the Python function located in functions/edge_processor.",
        )
    }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        name_spec = specs.get("name")
        if not name_spec:
            return specs

        catalog = get_function_catalog(EDGE_PROCESSOR_FUNCTION_DIR)
        names = catalog.list_function_names()
        metadata = catalog.list_metadata()
        description = name_spec.description or "Processor function name"
        if catalog.load_error:
            description = f"{description} (Loading failed: {catalog.load_error})"
        elif not names:
            description = f"{description} (No processor functions found in functions/edge_processor)"

        descriptions = {}
        for name in names:
            meta = metadata.get(name)
            descriptions[name] = (meta.description if meta else None) or "No description provided."

        specs["name"] = replace(
            name_spec,
            enum=names or None,
            enum_options=enum_options_from_values(names, descriptions, preserve_label_case=True) if names else None,
            description=description,
        )
        return specs

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "FunctionEdgeProcessorConfig":
        mapping = require_mapping(data, path)
        name = require_str(mapping, "name", path, allow_empty=False)
        return cls(name=name, path=path)

    def display_label(self) -> str:
        return self.name or "function"

    def to_external_value(self) -> Any:
        return {"name": self.name}


TProcessorConfig = TypeVar("TProcessorConfig", bound=EdgeProcessorTypeConfig)


@dataclass
class EdgeProcessorConfig(BaseConfig):
    """Wrapper config storing processor type and payload."""

    type: str
    config: EdgeProcessorTypeConfig

    FIELD_SPECS = {
        "type": ConfigFieldSpec(
            name="type",
            display_name="Processor Type",
            type_hint="str",
            required=True,
            description="Select which processor implementation to use (regex_extract, function, etc.).",
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Processor Config",
            type_hint="object",
            required=True,
            description="Payload interpreted by the selected processor.",
        ),
    }

    @classmethod
    def from_dict(cls, data: Any, *, path: str) -> "EdgeProcessorConfig":
        if data is None:
            raise ConfigError("processor configuration cannot be null", path)
        mapping = require_mapping(data, path)
        processor_type = require_str(mapping, "type", path)
        config_payload = mapping.get("config")
        if config_payload is None:
            raise ConfigError("processor config is required", extend_path(path, "config"))
        try:
            schema = get_edge_processor_schema(processor_type)
        except SchemaLookupError as exc:
            raise ConfigError(f"unknown processor type '{processor_type}'", extend_path(path, "type")) from exc
        processor_config = schema.config_cls.from_dict(config_payload, path=extend_path(path, "config"))
        return cls(type=processor_type, config=processor_config, path=path)

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, Type[BaseConfig]]:
        return {
            ChildKey(field="config", value=name): schema.config_cls
            for name, schema in iter_edge_processor_schemas().items()
        }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_edge_processor_schemas()
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
        return {
            "type": self.type,
            "config": self.config.to_external_value(),
        }

    def as_config(self, expected_type: Type[TProcessorConfig]) -> TProcessorConfig | None:
        config = self.config
        if isinstance(config, expected_type):
            return cast(TProcessorConfig, config)
        return None
