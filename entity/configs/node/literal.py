"""Configuration for literal nodes."""

from dataclasses import dataclass
from typing import Mapping, Any

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    EnumOption,
    optional_str,
    require_mapping,
    require_str,
)
from entity.messages import MessageRole


@dataclass
class LiteralNodeConfig(BaseConfig):
    """Config describing the literal payload emitted by the node."""

    content: str = ""
    role: MessageRole = MessageRole.USER

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "LiteralNodeConfig":
        mapping = require_mapping(data, path)
        content = require_str(mapping, "content", path)
        if not content:
            raise ConfigError("content cannot be empty", f"{path}.content")

        role_value = optional_str(mapping, "role", path)
        role = MessageRole.USER
        if role_value:
            normalized = role_value.strip().lower()
            if normalized not in (MessageRole.USER.value, MessageRole.ASSISTANT.value):
                raise ConfigError("role must be 'user' or 'assistant'", f"{path}.role")
            role = MessageRole(normalized)

        return cls(content=content, role=role, path=path)

    def validate(self) -> None:
        if not self.content:
            raise ConfigError("content cannot be empty", f"{self.path}.content")
        if self.role not in (MessageRole.USER, MessageRole.ASSISTANT):
            raise ConfigError("role must be 'user' or 'assistant'", f"{self.path}.role")

    FIELD_SPECS = {
        "content": ConfigFieldSpec(
            name="content",
            display_name="Literal Content",
            type_hint="text",
            required=True,
            description="Plain text emitted whenever the node executes.",
        ),
        "role": ConfigFieldSpec(
            name="role",
            display_name="Message Role",
            type_hint="str",
            required=False,
            default=MessageRole.USER.value,
            enum=[MessageRole.USER.value, MessageRole.ASSISTANT.value],
            enum_options=[
                EnumOption(value=MessageRole.USER.value, label="user"),
                EnumOption(value=MessageRole.ASSISTANT.value, label="assistant"),
            ],
            description="Select whether the literal message should appear as a user or assistant entry.",
        ),
    }
