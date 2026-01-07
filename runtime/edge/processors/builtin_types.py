"""Register built-in edge payload processors."""

from entity.configs.edge.edge_processor import (
    RegexEdgeProcessorConfig,
    FunctionEdgeProcessorConfig,
)
from .registry import register_edge_processor
from .regex_processor import RegexEdgePayloadProcessor
from .function_processor import FunctionEdgePayloadProcessor

register_edge_processor(
    "regex_extract",
    processor_cls=RegexEdgePayloadProcessor,
    summary="Extract payload fragments via Python regular expressions.",
    config_cls=RegexEdgeProcessorConfig,
)

register_edge_processor(
    "function",
    processor_cls=FunctionEdgePayloadProcessor,
    summary="Delegate message transformation to Python functions in functions/edge_processor.",
    config_cls=FunctionEdgeProcessorConfig,
)
