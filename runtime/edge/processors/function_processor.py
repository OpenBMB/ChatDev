"""Payload processor that delegates to Python functions."""

from typing import Any, Callable, Mapping

from entity.messages import Message
from utils.log_manager import LogManager
from utils.structured_logger import get_server_logger
from .base import EdgePayloadProcessor, ProcessorFactoryContext
from entity.configs.edge.edge_processor import FunctionEdgeProcessorConfig
from runtime.node.executor import ExecutionContext


class FunctionEdgePayloadProcessor(EdgePayloadProcessor[FunctionEdgeProcessorConfig]):
    def __init__(self, config: FunctionEdgeProcessorConfig, ctx: ProcessorFactoryContext) -> None:
        super().__init__(config, ctx)
        self._name = config.name
        self.label = f"function({self._name})"
        self.metadata = {"function": self._name}
        self._callable = self._resolve()

    def transform(
        self,
        payload: Message,
        *,
        source_result: Message,
        from_node,
        edge_link,
        log_manager: LogManager,
        context: ExecutionContext,
    ) -> Message | None:
        if self._callable is None:
            log_manager.warning(
                f"Processor function '{self._name}' not found. Falling back to passthrough."
            )
            return payload
        try:
            result = self._callable(payload.text_content(), context.global_state)
        except Exception as exc:  # pragma: no cover - defensive logging
            error_msg = f"Processor function '{self._name}' failed: {exc}"
            log_manager.error(error_msg)
            server_logger = get_server_logger()
            server_logger.log_exception(exc, error_msg, processor_name=self._name)
            return payload

        if result is None:
            return None

        return self._coerce_result(payload, result)

    def _resolve(self) -> Callable[[str, dict[str, Any]], Any] | None:
        manager = self.ctx.function_manager if self.ctx else None
        if not manager:
            return None
        func = manager.get_function(self._name)
        if func is None:
            return None
        return func

    def _coerce_result(self, payload: Message, result: Any) -> Message | None:
        if isinstance(result, Message):
            return result
        cloned = payload.clone()
        if isinstance(result, str):
            cloned.content = result
            return cloned
        if isinstance(result, Mapping):
            if result.get("drop"):
                return None
            if "content" in result:
                cloned.content = result["content"]
            metadata = dict(cloned.metadata)
            metadata.update(result.get("metadata") or {})
            cloned.metadata = metadata
            return cloned
        cloned.content = str(result)
        return cloned
