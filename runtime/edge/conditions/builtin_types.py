"""Register built-in edge condition manager implementations."""
from entity.configs.edge.edge_condition import (
    FunctionEdgeConditionConfig,
    KeywordEdgeConditionConfig,
)
from runtime.edge.conditions.registry import register_edge_condition
from runtime.edge.conditions.function_manager import FunctionEdgeConditionManager
from runtime.edge.conditions.keyword_manager import KeywordEdgeConditionManager

register_edge_condition(
    "function",
    manager_cls=FunctionEdgeConditionManager,
    summary="Calls registered Python functions from functions/edge (default 'true').",
    config_cls=FunctionEdgeConditionConfig
)
register_edge_condition(
    "keyword",
    manager_cls=KeywordEdgeConditionManager,
    summary="Declarative conditions based on include/exclude keywords or regex matching",
    config_cls=KeywordEdgeConditionConfig
)
