"""Provider-agnostic tool specification dataclasses."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ToolSpec:
    """Generic representation of a callable tool."""

    name: str
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_openai_dict(self) -> Dict[str, Any]:
        """Convert to OpenAI Responses API function schema."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters or {"type": "object", "properties": {}},
        }

    def to_gemini_function(self) -> Dict[str, Any]:
        """Convert to Gemini FunctionDeclaration schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters or {"type": "object", "properties": {}},
        }
