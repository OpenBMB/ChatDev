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
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

from camel.agents import BaseAgent
from camel.configs import ChatGPTConfig
from camel.messages import ChatMessage, MessageType, SystemMessage
from camel.model_backend import ModelBackend, ModelFactory
from camel.typing import ModelType, RoleType
from camel.utils import (
    get_model_token_limit,
    num_tokens_from_messages,
    openai_api_key_required,
)


@dataclass(frozen=True)
class ChatAgentResponse:
    r"""Response of a ChatAgent.

    Attributes:
        msgs (List[ChatMessage]): A list of zero, one or several messages.
            If the list is empty, there is some error in message generation.
            If the list has one message, this is normal mode.
            If the list has several messages, this is the critic mode.
        terminated (bool): A boolean indicating whether the agent decided
            to terminate the chat session.
        info (Dict[str, Any]): Extra information about the chat message.
    """
    msgs: List[ChatMessage]
    terminated: bool
    info: Dict[str, Any]

    @property
    def msg(self):
        if self.terminated:
            raise RuntimeError("error in ChatAgentResponse, info:{}".format(str(self.info)))
        if len(self.msgs) > 1:
            raise RuntimeError("Property msg is only available for a single message in msgs")
        elif len(self.msgs) == 0:
            if len(self.info) > 0:
                raise RuntimeError("Empty msgs in ChatAgentResponse, info:{}".format(str(self.info)))
            else:
                # raise RuntimeError("Known issue that msgs is empty and there is no error info, to be fix")
                return None
        return self.msgs[0]


class ChatAgent(BaseAgent):
    r"""Class for managing conversations of CAMEL Chat Agents.

    Args:
        system_message (SystemMessage): The system message for the chat agent.
        model (ModelType, optional): The LLM model to use for generating
            responses. (default :obj:`ModelType.GPT_3_5_TURBO`)
        model_config (Any, optional): Configuration options for the LLM model.
            (default: :obj:`None`)
        message_window_size (int, optional): The maximum number of previous
            messages to include in the context window. If `None`, no windowing
            is performed. (default: :obj:`None`)
    """

    def __init__(
            self,
            system_message: SystemMessage,
            model: Optional[ModelType] = None,
            model_config: Optional[Any] = None,
            message_window_size: Optional[int] = None,
    ) -> None:

        self.system_message: SystemMessage = system_message
        self.role_name: str = system_message.role_name
        self.role_type: RoleType = system_message.role_type
        self.model: ModelType = (model if model is not None else ModelType.GPT_3_5_TURBO)
        self.model_config: ChatGPTConfig = model_config or ChatGPTConfig()
        self.model_token_limit: int = get_model_token_limit(self.model)
        self.message_window_size: Optional[int] = message_window_size
        self.model_backend: ModelBackend = ModelFactory.create(self.model, self.model_config.__dict__)
        self.terminated: bool = False
        self.info: bool = False
        self.init_messages()

    def reset(self) -> List[MessageType]:
        r"""Resets the :obj:`ChatAgent` to its initial state and returns the
        stored messages.

        Returns:
            List[MessageType]: The stored messages.
        """
        self.terminated = False
        self.init_messages()
        return self.stored_messages

    def get_info(
            self,
            id: Optional[str],
            usage: Optional[Dict[str, int]],
            termination_reasons: List[str],
            num_tokens: int,
    ) -> Dict[str, Any]:
        r"""Returns a dictionary containing information about the chat session.

        Args:
            id (str, optional): The ID of the chat session.
            usage (Dict[str, int], optional): Information about the usage of
                the LLM model.
            termination_reasons (List[str]): The reasons for the termination of
                the chat session.
            num_tokens (int): The number of tokens used in the chat session.

        Returns:
            Dict[str, Any]: The chat session information.
        """
        return {
            "id": id,
            "usage": usage,
            "termination_reasons": termination_reasons,
            "num_tokens": num_tokens,
        }

    def init_messages(self) -> None:
        r"""Initializes the stored messages list with the initial system
        message.
        """
        self.stored_messages: List[MessageType] = [self.system_message]

    def update_messages(self, message: ChatMessage) -> List[MessageType]:
        r"""Updates the stored messages list with a new message.

        Args:
            message (ChatMessage): The new message to add to the stored
                messages.

        Returns:
            List[ChatMessage]: The updated stored messages.
        """
        self.stored_messages.append(message)
        return self.stored_messages

    @retry(wait=wait_exponential(min=5, max=60), stop=stop_after_attempt(5))
    @openai_api_key_required
    def step(
            self,
            input_message: ChatMessage,
    ) -> ChatAgentResponse:
        r"""Performs a single step in the chat session by generating a response
        to the input message.

        Args:
            input_message (ChatMessage): The input message to the agent.

        Returns:
            ChatAgentResponse: A struct
                containing the output messages, a boolean indicating whether
                the chat session has terminated, and information about the chat
                session.
        """
        messages = self.update_messages(input_message)
        if self.message_window_size is not None and len(
                messages) > self.message_window_size:
            messages = [self.system_message
                        ] + messages[-self.message_window_size:]
        openai_messages = [message.to_openai_message() for message in messages]
        num_tokens = num_tokens_from_messages(openai_messages, self.model)

        # for openai_message in openai_messages:
        #     # print("{}\t{}".format(openai_message.role, openai_message.content))
        #     print("{}\t{}\t{}".format(openai_message["role"], hash(openai_message["content"]), openai_message["content"][:60].replace("\n", "")))
        # print()

        output_messages: Optional[List[ChatMessage]]
        info: Dict[str, Any]

        if num_tokens < self.model_token_limit:
            response = self.model_backend.run(messages=openai_messages)
            if not isinstance(response, dict):
                raise RuntimeError("OpenAI returned unexpected struct")
            output_messages = [
                ChatMessage(role_name=self.role_name, role_type=self.role_type,
                            meta_dict=dict(), **dict(choice["message"]))
                for choice in response["choices"]
            ]
            info = self.get_info(
                response["id"],
                response["usage"],
                [str(choice["finish_reason"]) for choice in response["choices"]],
                num_tokens,
            )

            # TODO strict <INFO> check, only in the beginning of the line
            # if "<INFO>" in output_messages[0].content:
            if output_messages[0].content.split("\n")[-1].startswith("<INFO>"):
                self.info = True
        else:
            self.terminated = True
            output_messages = []

            info = self.get_info(
                None,
                None,
                ["max_tokens_exceeded_by_camel"],
                num_tokens,
            )

        return ChatAgentResponse(output_messages, self.terminated, info)

    def __repr__(self) -> str:
        r"""Returns a string representation of the :obj:`ChatAgent`.

        Returns:
            str: The string representation of the :obj:`ChatAgent`.
        """
        return f"ChatAgent({self.role_name}, {self.role_type}, {self.model})"
