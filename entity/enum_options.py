"""Helper utilities for building EnumOption metadata."""

from enum import Enum
from typing import Dict, List, Mapping, Sequence, Type, TypeVar

from entity.configs.base import EnumOption
from entity.enums import LogLevel, AgentExecFlowStage, AgentInputMode
from utils.strs import titleize

EnumT = TypeVar("EnumT", bound=Enum)


_ENUM_DESCRIPTIONS: Dict[Type[Enum], Dict[Enum, str]] = {
    LogLevel: {
        LogLevel.DEBUG: "Verbose developer logging; useful when debugging graph behavior.",
        LogLevel.INFO: "High-level execution progress and key checkpoints.",
        LogLevel.WARNING: "Recoverable problems that require attention but do not stop the run.",
        LogLevel.ERROR: "Errors that abort the current node or edge execution, even the entire workflow.",
        LogLevel.CRITICAL: "Fatal issues that stop the workflow immediately.",
    },
    AgentInputMode: {
        AgentInputMode.PROMPT: "Send a single string prompt assembled from previous messages.",
        AgentInputMode.MESSAGES: "Send structured role/content messages (Chat Completions style) which is recommended.",
    },
    AgentExecFlowStage: {
        AgentExecFlowStage.PRE_GEN_THINKING_STAGE: "Pre-generation thinking / planning stage.",
        AgentExecFlowStage.GEN_STAGE: "Main generation stage; also covers tool calling.",
        AgentExecFlowStage.POST_GEN_THINKING_STAGE: "Reflection or verification after generation.",
        AgentExecFlowStage.FINISHED_STAGE: "Finalization stage for cleanup and summary.",
    },
}


def enum_options_for(enum_cls: Type[EnumT]) -> List[EnumOption]:
    """Return EnumOption entries for a Python Enum class."""

    descriptions = _ENUM_DESCRIPTIONS.get(enum_cls, {})
    options: List[EnumOption] = []
    for member in enum_cls:
        label = titleize(member.name)
        options.append(EnumOption(value=member.value, label=label, description=descriptions.get(member)))
    return options


def enum_options_from_values(
    values: Sequence[str],
    descriptions: Mapping[str, str | None] | None = None,
    *,
    preserve_label_case: bool = False,
) -> List[EnumOption]:
    """Create EnumOption entries from literal string values."""

    options: List[EnumOption] = []
    desc_map = descriptions or {}
    for value in values:
        label = value if preserve_label_case else titleize(value)
        options.append(EnumOption(value=value, label=label, description=desc_map.get(value)))
    return options


def describe_enums_map() -> Dict[str, Dict[str, str]]:
    """Return a serializable description map (mostly for tests/debugging)."""

    payload: Dict[str, Dict[str, str]] = {}
    for enum_cls, mapping in _ENUM_DESCRIPTIONS.items():
        payload[enum_cls.__name__] = {member.value: text for member, text in mapping.items() if text}
    return payload


__all__ = [
    "enum_options_for",
    "enum_options_from_values",
    "describe_enums_map",
]
