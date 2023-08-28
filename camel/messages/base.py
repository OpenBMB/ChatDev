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


@dataclass
class BaseMessage:
    r"""Base class for message objects used in CAMEL chat system.

    Args:
        role_name (str): The name of the user or assistant role.
        role_type (RoleType): The type of role, either
            :obj:`RoleType.ASSISTANT` or :obj:`RoleType.USER`.
        meta_dict (Optional[Dict[str, str]]): Additional metadata dictionary
            for the message.
        role (str): The role of the message in OpenAI chat system, either
            :obj:`"system"`, :obj:`"user"`, or :obj:`"assistant"`.
        content (str): The content of the message.
    """
    role_name: str
    role_type: RoleType
    meta_dict: Optional[Dict[str, str]]
    role: str
    content: str

    def __getattribute__(self, name: str) -> Any:
        r"""Get attribute override to delegate string methods to the
        :obj:`content`.

        Args:
            name (str): The name of the attribute.

        Returns:
            Any: The attribute value.
        """
        delegate_methods = [
            method for method in dir(str) if not method.startswith('_')
        ]
        if name in delegate_methods:
            content = super().__getattribute__('content')
            if isinstance(content, str):
                content_method = getattr(content, name, None)
                if callable(content_method):

                    def modify_arg(arg: Any) -> Any:
                        r"""Modify the argument for delegate method.

                        Args:
                            arg (Any): The argument value.

                        Returns:
                            Any: The modified argument value.
                        """
                        if isinstance(arg, BaseMessage):
                            return arg.content
                        elif isinstance(arg, (list, tuple)):
                            return type(arg)(modify_arg(item) for item in arg)
                        else:
                            return arg

                    def wrapper(*args: Any, **kwargs: Any) -> Any:
                        r"""Wrapper function for delegate method.

                        Args:
                            *args (Any): Variable length argument list.
                            **kwargs (Any): Arbitrary keyword arguments.

                        Returns:
                            Any: The result of the delegate method.
                        """
                        modified_args = [modify_arg(arg) for arg in args]
                        modified_kwargs = {
                            k: modify_arg(v)
                            for k, v in kwargs.items()
                        }
                        output = content_method(*modified_args,
                                                **modified_kwargs)
                        return self._create_new_instance(output) if isinstance(
                            output, str) else output

                    return wrapper

        return super().__getattribute__(name)

    def _create_new_instance(self, content: str) -> "BaseMessage":
        r"""Create a new instance of the :obj:`BaseMessage` with updated
        content.

        Args:
            content (str): The new content value.

        Returns:
            BaseMessage: The new instance of :obj:`BaseMessage`.
        """
        return self.__class__(role_name=self.role_name,
                              role_type=self.role_type,
                              meta_dict=self.meta_dict, role=self.role,
                              content=content)

    def __add__(self, other: Any) -> Union["BaseMessage", Any]:
        r"""Addition operator override for :obj:`BaseMessage`.

        Args:
            other (Any): The value to be added with.

        Returns:
            Union[BaseMessage, Any]: The result of the addition.
        """
        if isinstance(other, BaseMessage):
            combined_content = self.content.__add__(other.content)
        elif isinstance(other, str):
            combined_content = self.content.__add__(other)
        else:
            raise TypeError(
                f"Unsupported operand type(s) for +: '{type(self)}' and "
                f"'{type(other)}'")
        return self._create_new_instance(combined_content)

    def __mul__(self, other: Any) -> Union["BaseMessage", Any]:
        r"""Multiplication operator override for :obj:`BaseMessage`.

        Args:
            other (Any): The value to be multiplied with.

        Returns:
            Union[BaseMessage, Any]: The result of the multiplication.
        """
        if isinstance(other, int):
            multiplied_content = self.content.__mul__(other)
            return self._create_new_instance(multiplied_content)
        else:
            raise TypeError(
                f"Unsupported operand type(s) for *: '{type(self)}' and "
                f"'{type(other)}'")

    def __len__(self) -> int:
        r"""Length operator override for :obj:`BaseMessage`.

        Returns:
            int: The length of the content.
        """
        return len(self.content)

    def __contains__(self, item: str) -> bool:
        r"""Contains operator override for :obj:`BaseMessage`.

        Args:
            item (str): The item to check for containment.

        Returns:
            bool: :obj:`True` if the item is contained in the content,
                :obj:`False` otherwise.
        """
        return item in self.content

    def token_len(self, model: ModelType = ModelType.GPT_3_5_TURBO) -> int:
        r"""Calculate the token length of the message for the specified model.

        Args:
            model (ModelType, optional): The model type to calculate the token
                length. (default: :obj:`ModelType.GPT_3_5_TURBO`)

        Returns:
            int: The token length of the message.
        """
        from camel.utils import num_tokens_from_messages
        return num_tokens_from_messages([self.to_openai_chat_message()], model)

    def extract_text_and_code_prompts(
            self) -> Tuple[List[TextPrompt], List[CodePrompt]]:
        r"""Extract text and code prompts from the message content.

        Returns:
            Tuple[List[TextPrompt], List[CodePrompt]]: A tuple containing a
                list of text prompts and a list of code prompts extracted
                from the content.
        """
        text_prompts: List[TextPrompt] = []
        code_prompts: List[CodePrompt] = []

        lines = self.content.split("\n")
        idx = 0
        start_idx = 0
        while idx < len(lines):
            while idx < len(lines) and (
                    not lines[idx].lstrip().startswith("```")):
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
        r"""Converts the message to an :obj:`OpenAIMessage` object.

        Args:
            role (Optional[str]): The role of the message in OpenAI chat
                system, either :obj:`"system"`, :obj:`"user"`, or
                obj:`"assistant"`. (default: :obj:`None`)

        Returns:
            OpenAIMessage: The converted :obj:`OpenAIMessage` object.
        """
        role = role or self.role
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"Unrecognized role: {role}")
        return {"role": role, "content": self.content}

    def to_openai_chat_message(
        self,
        role: Optional[str] = None,
    ) -> OpenAIChatMessage:
        r"""Converts the message to an :obj:`OpenAIChatMessage` object.

        Args:
            role (Optional[str]): The role of the message in OpenAI chat
                system, either :obj:`"user"`, or :obj:`"assistant"`.
                (default: :obj:`None`)

        Returns:
            OpenAIChatMessage: The converted :obj:`OpenAIChatMessage` object.
        """
        role = role or self.role
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unrecognized role: {role}")
        return {"role": role, "content": self.content}

    def to_openai_system_message(self) -> OpenAISystemMessage:
        r"""Converts the message to an :obj:`OpenAISystemMessage` object.

        Returns:
            OpenAISystemMessage: The converted :obj:`OpenAISystemMessage`
                object.
        """
        return {"role": "system", "content": self.content}

    def to_openai_user_message(self) -> OpenAIUserMessage:
        r"""Converts the message to an :obj:`OpenAIUserMessage` object.

        Returns:
            OpenAIUserMessage: The converted :obj:`OpenAIUserMessage` object.
        """
        return {"role": "user", "content": self.content}

    def to_openai_assistant_message(self) -> OpenAIAssistantMessage:
        r"""Converts the message to an :obj:`OpenAIAssistantMessage` object.

        Returns:
            OpenAIAssistantMessage: The converted :obj:`OpenAIAssistantMessage`
                object.
        """
        return {"role": "assistant", "content": self.content}

    def to_dict(self) -> Dict:
        r"""Converts the message to a dictionary.

        Returns:
            dict: The converted dictionary.
        """
        return {
            "role_name": self.role_name,
            "role_type": self.role_type.name,
            **(self.meta_dict or {}),
            "role": self.role,
            "content": self.content,
        }
