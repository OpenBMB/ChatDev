"""GAIA benchmark adapter; benchmark glue only, with no routing logic."""

from .adapter import AgentVisibleTask, EvaluatorRecord, GaiaTaskAdapter
from .answer import GaiaAnswer, extract_model_answer
from .scorer import score_answer

__all__ = [
    "AgentVisibleTask",
    "EvaluatorRecord",
    "GaiaTaskAdapter",
    "GaiaAnswer",
    "extract_model_answer",
    "score_answer",
]
