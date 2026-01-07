"""Human-in-the-loop prompt service with pluggable channels."""

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from entity.messages import MessageBlock, MessageBlockType, MessageContent
from utils.log_manager import LogManager


@dataclass
class PromptResult:
    """Typed result returned from prompt channels."""

    text: str
    blocks: Optional[List[MessageBlock]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_message_content(self) -> MessageContent:
        return self.blocks if self.blocks is not None else self.text


class PromptChannel(Protocol):
    """Channel interface that performs the actual user interaction."""

    def request(
        self,
        *,
        node_id: str,
        task: str,
        inputs: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptResult:
        """Collect user feedback and return the structured response."""


@dataclass
class CliPromptChannel:
    """Default channel that prompts the operator via CLI input()."""

    input_func: Callable[[str], str] = input

    def request(
        self,
        *,
        node_id: str,
        task: str,
        inputs: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptResult:
        header = ["===== HUMAN INPUT REQUIRED ====="]
        if inputs:
            header.append("=== Node inputs ===")
            header.append(inputs)
        header.append(f"=== Task for human ({node_id}) ===")
        header.append(task)
        header.append("=== Your response: ===")
        prompt = "\n".join(header) + "\n"
        response = self.input_func(prompt)
        return PromptResult(
            text=response,
            blocks=[MessageBlock.text_block(response or "")],
        )


class HumanPromptService:
    """Coordinates human feedback collection across nodes and tools."""

    def __init__(
        self,
        *,
        log_manager: LogManager,
        channel: PromptChannel,
        session_id: Optional[str] = None,
    ) -> None:
        self._log_manager = log_manager
        self._channel = channel
        self._session_id = session_id
        self._lock = threading.Lock()

    def request(
        self,
        node_id: str,
        task_description: str,
        *,
        inputs: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptResult:
        """Request human input through the configured channel."""

        meta = dict(metadata or {})
        if self._session_id and "session_id" not in meta:
            meta["session_id"] = self._session_id

        with self._lock:
            with self._log_manager.human_timer(node_id):
                raw_result = self._channel.request(
                    node_id=node_id,
                    task=task_description,
                    inputs=inputs,
                    metadata=meta,
                )

        prompt_result = self._normalize_result(raw_result)
        sanitized_text = self._sanitize_response(prompt_result.text)
        normalized_blocks = self._normalize_blocks(prompt_result.blocks, sanitized_text)
        combined_metadata = {**prompt_result.metadata, **meta}

        self._log_manager.record_human_interaction(
            node_id,
            inputs,
            sanitized_text,
            details={"task_description": task_description, **combined_metadata},
        )
        return PromptResult(
            text=sanitized_text,
            blocks=normalized_blocks,
            metadata=combined_metadata,
        )

    @staticmethod
    def _sanitize_response(response: Any) -> str:
        text = response if isinstance(response, str) else str(response)
        return text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")

    def _normalize_result(self, raw_result: PromptResult | str | Any) -> PromptResult:
        if isinstance(raw_result, PromptResult):
            return raw_result
        text = self._sanitize_response(raw_result)
        return PromptResult(text=text, blocks=[MessageBlock.text_block(text)])

    def _normalize_blocks(
        self,
        blocks: Optional[List[MessageBlock]],
        fallback_text: str,
    ) -> List[MessageBlock]:
        if not blocks:
            return [MessageBlock.text_block(fallback_text)]
        normalized: List[MessageBlock] = []
        for block in blocks:
            dup = block.copy()
            if dup.type is MessageBlockType.TEXT and dup.text is not None:
                dup.text = self._sanitize_response(dup.text)
            normalized.append(dup)
        return normalized


def resolve_prompt_channel(workspace_hook: Any) -> PromptChannel | None:
    """Helper to fetch a PromptChannel from a workspace hook if available."""

    if workspace_hook is None:
        return None

    getter = getattr(workspace_hook, "get_prompt_channel", None)
    if callable(getter):
        channel = getter()
        if channel is not None:
            return channel

    channel = getattr(workspace_hook, "prompt_channel", None)
    if channel is not None:
        return channel

    return None
