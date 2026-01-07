"""FunctionEdgeManager centralizes function-based edge conditions."""

from typing import Callable, Optional

from entity.configs.edge.edge_condition import FunctionEdgeConditionConfig
from utils.structured_logger import get_server_logger
from .base import ConditionFactoryContext
from .base import EdgeConditionManager
from utils.function_manager import FunctionManager
from ...node.executor import ExecutionContext


class FunctionEdgeConditionManager(EdgeConditionManager[FunctionEdgeConditionConfig]):
    def __init__(self, config: FunctionEdgeConditionConfig, ctx: ConditionFactoryContext, execution_context: ExecutionContext) -> None:
        super().__init__(config, ctx, execution_context)
        self._name = config.name or "true"
        self.label = self._name or "true"
        self.metadata = {"function": self._name}
        self._evaluator = self._build_evaluator()

    def _build_evaluator(self) -> Callable[[str], bool]:
        if self._name == "true":
            return lambda _: True

        function_obj = self._resolve_function(self._name, self.ctx.function_manager)
        if function_obj is None:
            logger = get_server_logger()
            logger.warning(f"Edge condition function '{self._name}' not found; defaulting to true")
            self.metadata = {"function": self._name, "missing": True}

            def missing(_: str) -> bool:
                if self.ctx.log_manager:
                    self.ctx.log_manager.warning(
                        f"Condition function '{self._name}' not found, defaulting to true"
                    )
                return True

            return missing

        def evaluator(data: str) -> bool:
            return bool(function_obj(data))

        return evaluator

    def process(
        self,
        edge_link,
        source_result,
        from_node,
        log_manager,
    ) -> None:
        self._process_with_condition(
            self._evaluator,
            label=self.label,
            metadata=self.metadata,
            edge_link=edge_link,
            source_result=source_result,
            from_node=from_node,
            log_manager=log_manager,
        )

    def _resolve_function(
        self, name: str, function_manager: Optional["FunctionManager"]
    ) -> Optional[Callable[[str], bool]]:
        if not function_manager:
            return None
        return function_manager.get_function(name)
