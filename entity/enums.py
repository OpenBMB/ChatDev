from enum import Enum


class AgentExecFlowStage(str, Enum):
    """Execution stages used to orchestrate agent workflows."""
    # INPUT_STAGE = "input"
    PRE_GEN_THINKING_STAGE = "pre_gen_thinking"
    GEN_STAGE = "gen"  # Includes tool calling plus the final response when applicable
    POST_GEN_THINKING_STAGE = "post_gen_thinking"
    FINISHED_STAGE = "finished"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    __level_values = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
    }

    @property
    def level(self) -> int:
        return self.__level_values[self.value]

    def __lt__(self, other):
        if isinstance(other, LogLevel):
            return self.level < other.level
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, LogLevel):
            return self.level <= other.level
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, LogLevel):
            return self.level > other.level
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, LogLevel):
            return self.level >= other.level
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, LogLevel):
            return self.level == other.level
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class EventType(str, Enum):
    NODE_START = "NODE_START"
    NODE_END = "NODE_END"
    EDGE_PROCESS = "EDGE_PROCESS"
    MODEL_CALL = "MODEL_CALL"
    TOOL_CALL = "TOOL_CALL"
    AGENT_CALL = "AGENT_CALL"
    HUMAN_INTERACTION = "HUMAN_INTERACTION"
    THINKING_PROCESS = "THINKING_PROCESS"
    MEMORY_OPERATION = "MEMORY_OPERATION"
    WORKFLOW_START = "WORKFLOW_START"
    WORKFLOW_END = "WORKFLOW_END"

    TEST = "TEST"


class CallStage(str, Enum):
    BEFORE = "before"
    AFTER = "after"


class AgentInputMode(str, Enum):
    """Controls how node inputs are fed into agent providers."""

    PROMPT = "prompt"
    MESSAGES = "messages"
