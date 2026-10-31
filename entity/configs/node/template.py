"""Configuration for template nodes."""

from dataclasses import dataclass
from typing import Mapping, Any

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    require_mapping,
    require_str,
)


@dataclass
class TemplateNodeConfig(BaseConfig):
    """Config describing the Jinja2 template used to format output."""

    template: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "TemplateNodeConfig":
        mapping = require_mapping(data, path)
        template = require_str(mapping, "template", path)
        if not template:
            raise ConfigError("template cannot be empty", f"{path}.template")

        return cls(template=template, path=path)

    def validate(self) -> None:
        if not self.template:
            raise ConfigError("template cannot be empty", f"{self.path}.template")

    FIELD_SPECS = {
        "template": ConfigFieldSpec(
            name="template",
            display_name="Jinja2 Template",
            type_hint="text",
            required=True,
            description="Jinja2 template string for formatting output. Available context: {{ input }} (latest message content), {{ environment }} (execution environment variables).",
        ),
    }
