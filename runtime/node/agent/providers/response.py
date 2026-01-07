"""Normalized provider response dataclasses."""

from dataclasses import dataclass
from typing import Any

from entity.messages import Message


@dataclass
class ModelResponse:
    """Represents a provider response with normalized message payload."""

    message: Message
    raw_response: Any | None = None

    def has_tool_calls(self) -> bool:
        return bool(self.message.tool_calls)

    def to_dict(self) -> dict:
        """Return a simple dict representation for compatibility."""
        payload = {
            "role": self.message.role.value,
        }
        if isinstance(self.message.content, list):
            payload["content"] = [
                block.to_dict() if hasattr(block, "to_dict") else block for block in self.message.content  # type: ignore[arg-type]
            ]
        else:
            payload["content"] = self.message.content
        if self.message.tool_calls:
            payload["tool_calls"] = [call.to_openai_dict() for call in self.message.tool_calls]
        if self.message.tool_call_id:
            payload["tool_call_id"] = self.message.tool_call_id
        if self.message.name:
            payload["name"] = self.message.name
        return payload

    def str_raw_response(self):
        return self.raw_response.__str__()
