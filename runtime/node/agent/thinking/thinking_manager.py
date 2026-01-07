from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from entity.configs import ThinkingConfig
from entity.messages import Message, MessageRole, MessageBlock

AgentInvoker = Callable[[List[Message]], Message]


@dataclass
class ThinkingPayload:
    """Container used to pass multimodal context into thinking managers."""

    text: str
    blocks: List[MessageBlock] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Any | None = None

    def describe(self) -> str:
        return self.text



class ThinkingManagerBase(ABC):
    def __init__(self, config: ThinkingConfig):
        self.config = config
        self.before_gen_think_enabled = False
        self.after_gen_think_enabled = False

        # you can customize the prompt by override this attribute
        self.thinking_concat_prompt = "{origin}\n\nThinking Result: {thinking}"

    @abstractmethod
    def _before_gen_think(
        self,
        agent_invoker: AgentInvoker,
        input_payload: ThinkingPayload,
        agent_role: str,
        memory: ThinkingPayload | None,
    ) -> tuple[str, bool]:
        """
        think based on input_data before calling model API for node to generate

        Returns:
            str: thinking result
            bool: whether to replace the original input_data with the modified one
        """
        ...

    @abstractmethod
    def _after_gen_think(
        self,
        agent_invoker: AgentInvoker,
        input_payload: ThinkingPayload,
        agent_role: str,
        memory: ThinkingPayload | None,
        gen_payload: ThinkingPayload,
    ) -> tuple[str, bool]:
        """
        think based on input_data and gen_data after calling model API for node to generate

        Returns:
            str: thinking result
            bool: whether to replace the original gen_data with the modified one
        """
        ...

    def think(
        self,
        agent_invoker: AgentInvoker,
        input_payload: ThinkingPayload,
        agent_role: str,
        memory: ThinkingPayload | None,
        gen_payload: ThinkingPayload | None = None,
    ) -> str | Message:
        """
        think based on input_data and gen_data if provided

        Returns:
            str: result for next step
        """

        normalized_input = input_payload.text
        normalized_gen = gen_payload.text if gen_payload is not None else None

        if gen_payload is None and self.before_gen_think_enabled:
            think_result, replace_input = self._before_gen_think(
                agent_invoker, input_payload, agent_role, memory
            )
            if replace_input:
                return think_result
            else:
                return self.thinking_concat_prompt.format(origin=normalized_input, thinking=think_result)
        elif gen_payload is not None and self.after_gen_think_enabled:
            think_result, replace_gen = self._after_gen_think(
                agent_invoker, input_payload, agent_role, memory, gen_payload
            )
            if replace_gen:
                return think_result
            else:
                return self.thinking_concat_prompt.format(origin=normalized_gen or "", thinking=think_result)
        else:
            if gen_payload is not None:
                return gen_payload.raw if gen_payload.raw is not None else gen_payload.text
            return input_payload.raw if input_payload.raw is not None else input_payload.text
