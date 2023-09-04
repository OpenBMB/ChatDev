# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
from typing import Any, Dict, List, Optional, Tuple

from colorama import Fore

from camel.agents import BaseToolAgent, ChatAgent, HuggingFaceToolAgent
from camel.messages import ChatMessage, SystemMessage
from camel.typing import ModelType
from camel.utils import print_text_animated


class EmbodiedAgent(ChatAgent):
    r"""Class for managing conversations of CAMEL Embodied Agents.

    Args:
        system_message (SystemMessage): The system message for the chat agent.
        model (ModelType, optional): The LLM model to use for generating
            responses. (default :obj:`ModelType.GPT_4`)
        model_config (Any, optional): Configuration options for the LLM model.
            (default: :obj:`None`)
        message_window_size (int, optional): The maximum number of previous
            messages to include in the context window. If `None`, no windowing
            is performed. (default: :obj:`None`)
        action_space (List[Any], optional): The action space for the embodied
            agent. (default: :obj:`None`)
        verbose (bool, optional): Whether to print the critic's messages.
        logger_color (Any): The color of the logger displayed to the user.
            (default: :obj:`Fore.MAGENTA`)
    """

    def __init__(
        self,
        system_message: SystemMessage,
        model: ModelType = ModelType.GPT_4,
        model_config: Optional[Any] = None,
        message_window_size: Optional[int] = None,
        action_space: Optional[List[BaseToolAgent]] = None,
        verbose: bool = False,
        logger_color: Any = Fore.MAGENTA,
    ) -> None:
        default_action_space = [
            HuggingFaceToolAgent('hugging_face_tool_agent', model=model.value),
        ]
        self.action_space = action_space or default_action_space
        action_space_prompt = self.get_action_space_prompt()
        system_message.content = system_message.content.format(
            action_space=action_space_prompt)
        self.verbose = verbose
        self.logger_color = logger_color
        super().__init__(
            system_message=system_message,
            model=model,
            model_config=model_config,
            message_window_size=message_window_size,
        )

    def get_action_space_prompt(self) -> str:
        r"""Returns the action space prompt.

        Returns:
            str: The action space prompt.
        """
        return "\n".join([
            f"*** {action.name} ***:\n {action.description}"
            for action in self.action_space
        ])

    def step(
        self,
        input_message: ChatMessage,
    ) -> Tuple[ChatMessage, bool, Dict[str, Any]]:
        r"""Performs a step in the conversation.

        Args:
            input_message (ChatMessage): The input message.

        Returns:
            Tuple[ChatMessage, bool, Dict[str, Any]]: A tuple
                containing the output messages, termination status, and
                additional information.
        """
        response = super().step(input_message)

        if response.msgs is None or len(response.msgs) == 0:
            raise RuntimeError("Got None output messages.")
        if response.terminated:
            raise RuntimeError(f"{self.__class__.__name__} step failed.")

        # NOTE: Only single output messages are supported
        explanations, codes = response.msg.extract_text_and_code_prompts()

        if self.verbose:
            for explanation, code in zip(explanations, codes):
                print_text_animated(self.logger_color +
                                    f"> Explanation:\n{explanation}")
                print_text_animated(self.logger_color + f"> Code:\n{code}")

            if len(explanations) > len(codes):
                print_text_animated(self.logger_color +
                                    f"> Explanation:\n{explanations}")

        content = response.msg.content

        if codes is not None:
            content = "\n> Executed Results:"
            global_vars = {action.name: action for action in self.action_space}
            for code in codes:
                executed_outputs = code.execute(global_vars)
                content += (
                    f"- Python standard output:\n{executed_outputs[0]}\n"
                    f"- Local variables:\n{executed_outputs[1]}\n")
                content += "*" * 50 + "\n"

        # TODO: Handle errors
        content = input_message.content + (Fore.RESET +
                                           f"\n> Embodied Actions:\n{content}")
        message = ChatMessage(input_message.role_name, input_message.role_type,
                              input_message.meta_dict, input_message.role,
                              content)
        return message, response.terminated, response.info
