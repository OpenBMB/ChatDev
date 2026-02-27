"""Doubao (豆包) provider implementation.

Doubao is ByteDance's AI service with OpenAI-compatible API.
Default base_url: https://aquasec.bytedance.net/api/v3 (or Volcano Engine Ark)
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI

from runtime.node.agent.providers.openai_provider import OpenAIProvider


class DoubaoProvider(OpenAIProvider):
    """Doubao (豆包) provider implementation.
    
    Inherits from OpenAIProvider since Doubao API is OpenAI-compatible.
    Supports both:
    - ByteDance Doubao: https://aquasec.bytedance.net/api/v3
    - Volcano Engine Ark: https://ark.cn-beijing.volces.com/api/v3
    """

    DEFAULT_BASE_URL = "https://aquasec.bytedance.net/api/v3"

    def create_client(self):
        """
        Create and return the OpenAI-compatible client for Doubao.
        
        Returns:
            OpenAI client instance configured for Doubao API
        """
        base_url = self.base_url if self.base_url else self.DEFAULT_BASE_URL
        return OpenAI(
            api_key=self.api_key,
            base_url=base_url,
        )

    def _is_chat_completions_mode(self, client: Any) -> bool:
        """
        Doubao only supports Chat Completions API, not Responses API.
        
        Always return True to force Chat Completions mode.
        """
        return True

    def _track_token_usage(self, response: Any) -> None:
        """Record token usage if a tracker is attached to the config."""
        token_tracker = getattr(self.config, "token_tracker", None)
        if not token_tracker:
            return

        usage = self.extract_token_usage(response)
        if usage.input_tokens == 0 and usage.output_tokens == 0 and not usage.metadata:
            return

        node_id = getattr(self.config, "node_id", "ALL")
        usage.node_id = node_id
        usage.model_name = self.model_name
        usage.workflow_id = token_tracker.workflow_id
        usage.provider = "doubao"

        token_tracker.record_usage(node_id, self.model_name, usage, provider="doubao")
