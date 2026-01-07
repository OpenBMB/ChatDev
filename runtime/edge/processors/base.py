"""Base classes for payload processors applied on edges."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from entity.messages import Message
from runtime.node.executor import ExecutionContext
from utils.log_manager import LogManager
from utils.function_manager import FunctionManager

TConfig = TypeVar("TConfig")


@dataclass(slots=True)
class ProcessorFactoryContext:
    """Context passed to processor implementations."""

    function_manager: "FunctionManager | None" = None
    log_manager: "LogManager | None" = None


class EdgePayloadProcessor(Generic[TConfig], ABC):
    """Base payload processor API."""

    label: str | None = None
    metadata: dict[str, Any] | None = None

    def __init__(self, config: TConfig, ctx: ProcessorFactoryContext) -> None:
        self.config = config
        self.ctx = ctx

    @abstractmethod
    def transform(
        self,
        payload: Message,
        *,
        source_result: Message,
        from_node: Any,
        edge_link: Any,
        log_manager: LogManager,
        context: ExecutionContext,
    ) -> Message | None:
        """Return transformed payload or None to drop the message."""

    def _clone(self, payload: Message) -> Message:
        return payload.clone()

    def _text(self, payload: Message) -> str:
        return payload.text_content()
