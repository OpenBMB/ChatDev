"""Configuration for passthrough nodes."""

from dataclasses import dataclass
from typing import Mapping, Any

from entity.configs.base import BaseConfig, ConfigFieldSpec, optional_bool, require_mapping


@dataclass
class PassthroughConfig(BaseConfig):
    """Configuration for passthrough nodes."""

    only_last_message: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "PassthroughConfig":
        if data is None:
            return cls(only_last_message=True, path=path)
        mapping = require_mapping(data, path)
        only_last_message = optional_bool(mapping, "only_last_message", path, default=True)
        return cls(only_last_message=only_last_message, path=path)

    FIELD_SPECS = {
        "only_last_message": ConfigFieldSpec(
            name="only_last_message",
            display_name="Only Last Message",
            type_hint="bool",
            required=False,
            default=True,
            description="If True, only pass the last received message. If False, pass all messages.",
        ),
    }
