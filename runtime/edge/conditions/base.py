"""EdgeConditionManager abstraction that unifies edge condition compilation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from entity.messages import Message, MessageRole
from runtime.node.executor import ExecutionContext
from utils.log_manager import LogManager
from utils.structured_logger import get_server_logger
from entity.configs.node.node import EdgeLink, Node
from entity.configs.edge.edge_condition import EdgeConditionTypeConfig
from utils.function_manager import FunctionManager

ConditionEvaluator = Callable[[str], bool]

TConfig = TypeVar("TConfig", bound="EdgeConditionTypeConfig")


@dataclass(slots=True)
class ConditionFactoryContext:
    """Context passed to managers at initialization time."""

    function_manager: "FunctionManager | None" = None
    log_manager: "LogManager | None" = None


class EdgeConditionManager(Generic[TConfig], ABC):
    """An abstract base class is required, and all edge condition types must implement the process logic."""

    def __init__(self, config: TConfig, ctx: ConditionFactoryContext, execution_context: ExecutionContext) -> None:
        self.config = config
        self.ctx = ctx
        self.execution_context = execution_context

    @abstractmethod
    def process(
        self,
        edge_link: "EdgeLink",
        source_result: Message,
        from_node: "Node",
        log_manager: LogManager,
    ) -> None:
        """The execution logic is implemented by the subclasses."""

    def transform_payload(
        self,
        payload: Message,
        *,
        source_result: Message,
        from_node: "Node",
        edge_link: "EdgeLink",
        log_manager: LogManager,
    ) -> Message | None:
        processor = edge_link.payload_processor
        if not processor:
            return payload
        try:
            return processor.transform(
                payload,
                source_result=source_result,
                from_node=from_node,
                edge_link=edge_link,
                log_manager=log_manager,
                context=self.execution_context,
            )
        except Exception as exc:  # pragma: no cover
            error_msg = (
                f"Edge payload processor failed for {from_node.id}->{edge_link.target.id}: {exc}"
            )
            if self.ctx and self.ctx.log_manager:
                self.ctx.log_manager.error(
                    error_msg,
                    details={
                        "processor_type": getattr(edge_link, "process_type", None),
                        "processor_metadata": getattr(edge_link, "process_metadata", {}),
                    },
                )
            server_logger = get_server_logger()
            server_logger.log_exception(
                exc,
                error_msg,
                processor_type=getattr(edge_link, "process_type", None),
                processor_metadata=getattr(edge_link, "process_metadata", {}),
            )
            return payload

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _process_with_condition(
        self,
        evaluator: ConditionEvaluator,
        *,
        label: str,
        metadata: dict[str, Any],
        edge_link: "EdgeLink",
        source_result: Message,
        from_node: "Node",
        log_manager: LogManager,
    ) -> None:
        target_node = edge_link.target
        log_manager.record_edge_process(from_node.id, target_node.id, edge_link.config)

        serialized_source = self._payload_to_text(source_result)
        try:
            condition_met = bool(evaluator(serialized_source))
        except Exception as exc:  # pragma: no cover
            error_msg = f"Error calling condition '{label}': {exc}"
            log_manager.error(
                error_msg,
                details={
                    "condition_type": edge_link.condition_type,
                    "condition_metadata": metadata,
                },
            )
            server_logger = get_server_logger()
            server_logger.log_exception(
                exc,
                error_msg,
                condition_type=edge_link.condition_type,
                condition_metadata=metadata,
            )
            condition_met = True

        if not condition_met:
            log_manager.debug(
                f"Edge condition not met for {from_node.id} -> {target_node.id}, skipping edge processing"
            )
            return

        log_manager.info(f"Edge condition met for {from_node.id} -> {target_node.id}")
        self._clear_target_context(
            target_node,
            drop_non_keep=getattr(edge_link, "clear_context", False),
            drop_keep=getattr(edge_link, "clear_kept_context", False),
            from_node=from_node,
            log_manager=log_manager,
        )

        if edge_link.carry_data:
            payload = self._prepare_payload_for_target(source_result, from_node, target_node, edge_link.keep_message)
            payload = self.transform_payload(
                payload,
                source_result=source_result,
                from_node=from_node,
                edge_link=edge_link,
                log_manager=log_manager,
            )
            if payload is None:
                log_manager.debug(
                    f"Payload processor dropped message for edge {from_node.id} -> {target_node.id}"
                )
                return
            
            # Tag message with dynamic edge info for later processing
            if edge_link.dynamic_config is not None:
                metadata = dict(payload.metadata)
                metadata["_from_dynamic_edge"] = True
                metadata["_dynamic_edge_source"] = from_node.id
                payload.metadata = metadata
            
            target_node.append_input(payload)
            log_manager.debug(
                f"Data passed from {from_node.id} to {target_node.id}'s input queue "
                f"(type: {self._describe_payload(payload)})"
            )
        else:
            log_manager.debug(
                f"Edge {from_node.id} -> {target_node.id} does not carry data, skipping data transfer"
            )

        if edge_link.trigger:
            edge_link.triggered = True
            log_manager.debug(f"Edge {from_node.id} -> {target_node.id} triggered")

    def _payload_to_text(self, payload: Any) -> str:
        if isinstance(payload, Message):
            return payload.text_content()
        if payload is None:
            return ""
        return str(payload)

    def _prepare_payload_for_target(
        self,
        payload: Any,
        from_node: Node,
        target_node: Node,
        keep: bool = False,
    ) -> Message:
        if not isinstance(payload, Message):
            payload = Message(role=MessageRole.ASSISTANT, content=str(payload))
        cloned = payload.clone()
        if not cloned.preserve_role:
            cloned_role = MessageRole.ASSISTANT if from_node.id == target_node.id else MessageRole.USER
            cloned.role = cloned_role
        metadata = dict(cloned.metadata)
        metadata["source"] = from_node.id
        cloned.metadata = metadata
        if keep:
            cloned.keep = True
        return cloned

    def _clear_target_context(
        self,
        target_node: Node,
        *,
        drop_non_keep: bool,
        drop_keep: bool,
        from_node: Node,
        log_manager: LogManager,
    ) -> None:
        if not drop_non_keep and not drop_keep:
            return
        removed_non_keep, removed_keep = target_node.clear_inputs_by_flag(
            drop_non_keep=drop_non_keep,
            drop_keep=drop_keep,
        )
        if removed_non_keep or removed_keep:
            log_manager.debug(
                f"Cleared target context for edge {from_node.id} -> {target_node.id}",
                details={
                    "removed_non_keep": removed_non_keep,
                    "removed_keep": removed_keep,
                    "drop_non_keep": drop_non_keep,
                    "drop_keep": drop_keep,
                },
            )

    def _describe_payload(self, payload: Any) -> str:
        if isinstance(payload, Message):
            return f"message:{payload.role.value}"
        return type(payload).__name__
