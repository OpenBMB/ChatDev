"""MiniMax provider implementation.

MiniMax models are accessed via an OpenAI-compatible Chat Completions API.
Supported models include MiniMax-M2.7, MiniMax-M2.7-highspeed,
MiniMax-M2.5, and MiniMax-M2.5-highspeed, all with 204K context windows.

API endpoint: https://api.minimax.io/v1
"""

import os
import re
from typing import Any, Dict, List, Optional

from entity.configs import AgentConfig
from entity.messages import Message, MessageBlockType, MessageBlock, MessageRole
from entity.tool_spec import ToolSpec
from runtime.node.agent.providers.openai_provider import OpenAIProvider
from runtime.node.agent.providers.response import ModelResponse
from utils.token_tracker import TokenUsage

# MiniMax requires temperature in (0.0, 1.0]
_MINIMAX_TEMP_MIN = 0.01
_MINIMAX_TEMP_MAX = 1.0

_MINIMAX_DEFAULT_BASE_URL = "https://api.minimax.io/v1"

# Pattern to strip <think>…</think> blocks from reasoning-model output
_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class MiniMaxProvider(OpenAIProvider):
    """MiniMax provider via the OpenAI-compatible Chat Completions API."""

    def __init__(self, config: AgentConfig):
        # Apply MiniMax defaults before parent init
        if not config.base_url:
            config.base_url = _MINIMAX_DEFAULT_BASE_URL
        if not config.api_key:
            config.api_key = os.environ.get("MINIMAX_API_KEY", "")
        super().__init__(config)

    def _is_chat_completions_mode(self, client: Any) -> bool:
        """MiniMax only supports the Chat Completions protocol."""
        return True

    def _build_chat_payload(
        self,
        conversation: List[Message],
        tool_specs: Optional[List[ToolSpec]],
        raw_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build payload with MiniMax-specific temperature clamping."""
        params = dict(raw_params)
        temp = params.get("temperature")
        if temp is not None:
            temp = float(temp)
            if temp <= 0:
                temp = _MINIMAX_TEMP_MIN
            elif temp > _MINIMAX_TEMP_MAX:
                temp = _MINIMAX_TEMP_MAX
            params["temperature"] = temp
        return super()._build_chat_payload(conversation, tool_specs, params)

    def _deserialize_chat_response(self, response: Any) -> Message:
        """Deserialize and strip <think> tags from reasoning model output."""
        message = super()._deserialize_chat_response(response)
        return self._strip_think_tags(message)

    def _strip_think_tags(self, message: Message) -> Message:
        """Remove <think>…</think> blocks from assistant text content."""
        if message.role is not MessageRole.ASSISTANT:
            return message

        content = message.content
        if isinstance(content, str):
            cleaned = _THINK_TAG_RE.sub("", content).strip()
            return Message(
                role=message.role,
                content=cleaned,
                tool_calls=message.tool_calls,
                tool_call_id=message.tool_call_id,
                name=message.name,
            )

        if isinstance(content, list):
            cleaned_blocks: List[MessageBlock] = []
            for block in content:
                if isinstance(block, MessageBlock) and block.type is MessageBlockType.TEXT:
                    cleaned_text = _THINK_TAG_RE.sub("", block.text or "").strip()
                    cleaned_blocks.append(
                        MessageBlock(MessageBlockType.TEXT, text=cleaned_text)
                    )
                else:
                    cleaned_blocks.append(block)
            return Message(
                role=message.role,
                content=cleaned_blocks,
                tool_calls=message.tool_calls,
                tool_call_id=message.tool_call_id,
                name=message.name,
            )

        return message

    def _track_token_usage(self, response: Any) -> None:
        """Record token usage with provider set to 'minimax'."""
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
        usage.provider = "minimax"

        token_tracker.record_usage(node_id, self.model_name, usage, provider="minimax")
