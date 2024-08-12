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
#  Enhanced by Startr.Team (2024)
# =========== Copyright 2024 @  Startr LLC   All Rights Reserved. ===========


from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from camel.messages import (
    OpenAIAssistantMessage,
    OpenAIChatMessage,
    OpenAIMessage,
    OpenAISystemMessage,
    OpenAIUserMessage,
)
from camel.prompts import CodePrompt, TextPrompt
from camel.typing import ModelType, RoleType

try:
    from openai.types.chat.chat_completion_message_tool_call import (
        ChatCompletionMessageToolCall,
    )
    from openai.types.chat.chat_completion_message import FunctionCall

    openai_new_api = True
except ImportError:
    openai_new_api = False


@dataclass
class BaseMessage:
    """Base class for messages used in the CAMEL chat system.

    Attributes:
        role_name (str): The name of the role (user or assistant).
        role_type (RoleType): Type of role (ASSISTANT or USER).
        meta_dict (Optional[Dict[str, str]]): Extra data for the message.
        role (str): The role of the message (system, user, or assistant).
        content (str): The content of the message.
        refusal (Optional[str]): Refusal message.
        function_call (Optional[FunctionCall]): Function call info for new API.
        tool_calls (Optional[ChatCompletionMessageToolCall]): Tool call info.
    """

    role_name: str
    role_type: RoleType
    meta_dict: Optional[Dict[str, str]]
    role: str
    content: str
    refusal: Optional[str] = None
    if openai_new_api:
        function_call: Optional[FunctionCall] = None
        tool_calls: Optional[ChatCompletionMessageToolCall] = None

    def __getattribute__(self, name: str) -> Any:
        """Override to delegate string methods to the content."""
        delegate_methods = [method for method in dir(str) if not method.startswith("_")]
        if name in delegate_methods:
            content = super().__getattribute__("content")
            if isinstance(content, str):
                content_method = getattr(content, name, None)
                if callable(content_method):

                    def modify_arg(arg: Any) -> Any:
                        if isinstance(arg, BaseMessage):
                            return arg.content
                        elif isinstance(arg, (list, tuple)):
                            return type(arg)(modify_arg(item) for item in arg)
                        else:
                            return arg

                    def wrapper(*args: Any, **kwargs: Any) -> Any:
                        modified_args = [modify_arg(arg) for arg in args]
                        modified_kwargs = {k: modify_arg(v) for k, v in kwargs.items()}
                        output = content_method(*modified_args, **modified_kwargs)
                        return (
                            self._create_new_instance(output)
                            if isinstance(output, str)
                            else output
                        )

                    return wrapper

        return super().__getattribute__(name)

    def _create_new_instance(self, content: str) -> "BaseMessage":
        """Create a new BaseMessage instance with updated content."""
        return self.__class__(
            role_name=self.role_name,
            role_type=self.role_type,
            meta_dict=self.meta_dict,
            role=self.role,
            content=content,
        )

    def __add__(self, other: Any) -> Union["BaseMessage", Any]:
        """Addition operator for BaseMessage."""
        if isinstance(other, BaseMessage):
            combined_content = self.content + other.content
        elif isinstance(other, str):
            combined_content = self.content + other
        else:
            raise TypeError(f"Cannot add '{type(self)}' and '{type(other)}'")
        return self._create_new_instance(combined_content)

    def __mul__(self, other: Any) -> Union["BaseMessage", Any]:
        """Multiplication operator for BaseMessage."""
        if isinstance(other, int):
            multiplied_content = self.content * other
            return self._create_new_instance(multiplied_content)
        else:
            raise TypeError(f"Cannot multiply '{type(self)}' and '{type(other)}'")

    def __len__(self) -> int:
        """Get length of the message content."""
        return len(self.content)

    def __contains__(self, item: str) -> bool:
        """Check if an item is in the message content."""
        return item in self.content

    def token_len(self, model: ModelType = ModelType.GPT_3_5_TURBO) -> int:
        """Calculate the token length of the message for the specified model."""
        from camel.utils import num_tokens_from_messages

        return num_tokens_from_messages([self.to_openai_chat_message()], model)

    def extract_text_and_code_prompts(
        self,
    ) -> Tuple[List[TextPrompt], List[CodePrompt]]:
        """Extract text and code prompts from the message content."""
        text_prompts = []
        code_prompts = []

        lines = self.content.split("\n")
        idx = 0
        start_idx = 0

        while idx < len(lines):
            while idx < len(lines) and not lines[idx].lstrip().startswith("```"):
                idx += 1
            text = "\n".join(lines[start_idx:idx]).strip()
            text_prompts.append(TextPrompt(text))

            if idx >= len(lines):
                break

            code_type = lines[idx].strip()[3:].strip()
            idx += 1
            start_idx = idx
            while not lines[idx].lstrip().startswith("```"):
                idx += 1
            code = "\n".join(lines[start_idx:idx]).strip()
            code_prompts.append(CodePrompt(code, code_type=code_type))

            idx += 1
            start_idx = idx

        return text_prompts, code_prompts

    def to_openai_message(self, role: Optional[str] = None) -> OpenAIMessage:
        """Convert to an OpenAIMessage object."""
        role = role or self.role
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"Unrecognized role: {role}")
        return {"role": role, "content": self.content}

    def to_openai_chat_message(self, role: Optional[str] = None) -> OpenAIChatMessage:
        """Convert to an OpenAIChatMessage object."""
        role = role or self.role
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unrecognized role: {role}")
        return {"role": role, "content": self.content}

    def to_openai_system_message(self) -> OpenAISystemMessage:
        """Convert to an OpenAISystemMessage object."""
        return {"role": "system", "content": self.content}

    def to_openai_user_message(self) -> OpenAIUserMessage:
        """Convert to an OpenAIUserMessage object."""
        return {"role": "user", "content": self.content}

    def to_openai_assistant_message(self) -> OpenAIAssistantMessage:
        """Convert to an OpenAIAssistantMessage object."""
        return {"role": "assistant", "content": self.content}

    def to_dict(self) -> Dict:
        """Convert the message to a dictionary."""
        return {
            "role_name": self.role_name,
            "role_type": self.role_type.name,
            **(self.meta_dict or {}),
            "role": self.role,
            "content": self.content,
        }
