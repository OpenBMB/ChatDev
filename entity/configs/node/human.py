"""Human node configuration."""

from dataclasses import dataclass
from typing import Any, Mapping

from entity.configs.base import BaseConfig, ConfigFieldSpec, optional_str, require_mapping


@dataclass
class HumanConfig(BaseConfig):
    description: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "HumanConfig":
        if data is None:
            return cls(description=None, path=path)
        mapping = require_mapping(data, path)
        description = optional_str(mapping, "description", path)
        return cls(description=description, path=path)

    FIELD_SPECS = {
        "description": ConfigFieldSpec(
            name="description",
            display_name="Human Task Description",
            type_hint="text",
            required=False,
            description="Description of the task for human to complete",
        )
    }
