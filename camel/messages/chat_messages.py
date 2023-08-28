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
from typing import Dict, Optional

from camel.messages import BaseMessage
from camel.typing import RoleType


@dataclass
class ChatMessage(BaseMessage):
    r"""Base class for chat messages used in CAMEL chat system.

    Args:
        role_name (str): The name of the user or assistant role.
        role_type (RoleType): The type of role, either
            :obj:`RoleType.ASSISTANT` or :obj:`RoleType.USER`.
        meta_dict (Optional[Dict[str, str]]): Additional metadata dictionary
            for the message.
        role (str): The role of the message in OpenAI chat system.
        content (str): The content of the message. (default: :obj:`""`)
    """
    role_name: str
    role_type: RoleType
    meta_dict: Optional[Dict[str, str]]
    role: str
    content: str = ""

    def set_user_role_at_backend(self: BaseMessage):
        return self.__class__(
            role_name=self.role_name,
            role_type=self.role_type,
            meta_dict=self.meta_dict,
            role="user",
            content=self.content,
        )


@dataclass
class AssistantChatMessage(ChatMessage):
    r"""Class for chat messages from the assistant role used in CAMEL chat
    system.

    Attributes:
        role_name (str): The name of the assistant role.
        role_type (RoleType): The type of role, always
            :obj:`RoleType.ASSISTANT`.
        meta_dict (Optional[Dict[str, str]]): Additional metadata dictionary
            for the message.
        role (str): The role of the message in OpenAI chat system.
            (default: :obj:`"assistant"`)
        content (str): The content of the message. (default: :obj:`""`)
    """
    role_name: str
    role_type: RoleType = RoleType.ASSISTANT
    meta_dict: Optional[Dict[str, str]] = None
    role: str = "user"
    content: str = ""


@dataclass
class UserChatMessage(ChatMessage):
    r"""Class for chat messages from the user role used in CAMEL chat system.

    Args:
        role_name (str): The name of the user role.
        role_type (RoleType): The type of role, always :obj:`RoleType.USER`.
        meta_dict (Optional[Dict[str, str]]): Additional metadata dictionary
            for the message.
        role (str): The role of the message in OpenAI chat system.
            (default: :obj:`"user"`)
        content (str): The content of the message. (default: :obj:`""`)
    """
    role_name: str
    role_type: RoleType = RoleType.USER
    meta_dict: Optional[Dict[str, str]] = None
    role: str = "user"
    content: str = ""
