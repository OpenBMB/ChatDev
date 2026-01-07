"""Abstract base classes for agent providers."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from entity.configs import AgentConfig
from entity.messages import Message
from schema_registry import register_model_provider_schema
from entity.tool_spec import ToolSpec
from runtime.node.agent.providers.response import ModelResponse
from utils.token_tracker import TokenUsage
from utils.registry import Registry


class ModelProvider(ABC):
    """Abstract base class for all agent providers."""
    
    def __init__(self, config: AgentConfig):
        """
        Initialize the agent provider with configuration.
        
        Args:
            config: Agent configuration instance
        """
        self.config = config
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.model_name = config.name if isinstance(config.name, str) else str(config.name)
        self.provider = config.provider
        self.params = config.params or {}

    @abstractmethod
    def create_client(self):
        """
        Create and return the appropriate client for this provider.
        
        Returns:
            Client instance for making API calls
        """
        pass

    @abstractmethod
    def call_model(
        self,
        client,
        conversation: List[Message],
        timeline: List[Any],
        tool_specs: Optional[List[ToolSpec]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Call the model with the given messages and parameters.
        
        Args:
            client: Provider-specific client instance
            conversation: List of messages in the conversation
            tool_specs: Tool specifications available for this call
            **kwargs: Additional parameters for the model call
            
        Returns:
            ModelResponse containing content and potentially tool calls
        """
        pass

    @abstractmethod
    def extract_token_usage(self, response: Any) -> TokenUsage:
        """
        Extract token usage from the API response.
        
        Args:
            response: Raw API response from the model call
            
        Returns:
            TokenUsage instance with token counts
        """
        pass


_provider_registry = Registry("agent_provider")


class ProviderRegistry:
    """Registry facade for agent providers."""

    @classmethod
    def register(
        cls,
        name: str,
        provider_class: type,
        *,
        label: str | None = None,
        summary: str | None = None,
    ) -> None:
        metadata = {
            "label": label,
            "summary": summary,
        }
        # Drop None values so schema consumers don't need to filter.
        metadata = {key: value for key, value in metadata.items() if value is not None}
        _provider_registry.register(name, target=provider_class, metadata=metadata)
        register_model_provider_schema(name, label=label, summary=summary)

    @classmethod
    def get_provider(cls, name: str) -> type | None:
        try:
            entry = _provider_registry.get(name)
        except Exception:
            return None
        return entry.load()

    @classmethod
    def list_providers(cls) -> List[str]:
        return list(_provider_registry.names())

    @classmethod
    def iter_metadata(cls) -> Dict[str, Dict[str, Any]]:
        return {name: dict(entry.metadata or {}) for name, entry in _provider_registry.items()}
