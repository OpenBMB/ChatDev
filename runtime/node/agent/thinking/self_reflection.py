from entity.configs import ReflectionThinkingConfig
from entity.messages import Message, MessageRole
from runtime.node.agent.thinking.thinking_manager import (
    ThinkingManagerBase,
    AgentInvoker,
    ThinkingPayload,
)


class SelfReflectionThinkingManager(ThinkingManagerBase):
    """
    A simple implementation of thinking manager, named self-reflection.
    This part of the code is borrowed from ChatDev (https://github.com/OpenBMB/ChatDev) and adapted.
    """

    def __init__(self, config: ReflectionThinkingConfig):
        super().__init__(config)
        self.before_gen_think_enabled = False
        self.after_gen_think_enabled = True
        self.base_prompt = """Here is a conversation between two roles: {conversations} {reflection_prompt}"""

        self.reflection_prompt = config.reflection_prompt or "Reflect on the given information and summarize key points in a few words."

    def _before_gen_think(
        self,
        agent_invoker: AgentInvoker,
        input_payload: ThinkingPayload,
        agent_role: str,
        memory: ThinkingPayload | None,
    ) -> tuple[str, bool]:
        ...

    def _after_gen_think(
        self,
        agent_invoker: AgentInvoker,
        input_payload: ThinkingPayload,
        agent_role: str,
        memory: ThinkingPayload | None,
        gen_payload: ThinkingPayload,
    ) -> tuple[str, bool]:
        conversations = [
            f"SYSTEM: {agent_role}",
            f"USER: {input_payload.text}",
            f"ASSISTANT: {gen_payload.text}",
        ]
        if memory and memory.text:
            conversations = [memory.text] + conversations
        prompt = self.base_prompt.format(conversations="\n\n".join(conversations),
                                         reflection_prompt=self.reflection_prompt)

        reflection_message = agent_invoker(
            [Message(role=MessageRole.USER, content=prompt)]
        )
        return reflection_message.text_content(), True