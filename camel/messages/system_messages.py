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
class SystemMessage(BaseMessage):
    r"""Class for system messages used in CAMEL chat system.

    Args:
        role_name (str): The name of the user or assistant role.
        role_type (RoleType): The type of role, either
            :obj:`RoleType.ASSISTANT` or :obj:`RoleType.USER`.
        meta_dict (Optional[Dict[str, str]]): Additional metadata dictionary
            for the message.
        role (str): The role of the message in OpenAI chat system.
            (default: :obj:`"system"`)
        content (str): The content of the message. (default: :obj:`""`)
    """
    role_name: str
    role_type: RoleType
    meta_dict: Optional[Dict[str, str]] = None
    role: str = "system"
    content: str = ""


@dataclass
class AssistantSystemMessage(SystemMessage):
    r"""Class for system messages from the assistant used in the CAMEL chat
    system.

    Args:
        role_name (str): The name of the assistant role.
        role_type (RoleType): The type of role, always
            :obj:`RoleType.ASSISTANT`.
        meta_dict (Optional[Dict[str, str]]): Additional metadata dictionary
            for the message.
        role (str): The role of the message in OpenAI chat system.
            (default: :obj:`"system"`)
        content (str): The content of the message. (default: :obj:`""`)
    """
    role_name: str
    role_type: RoleType = RoleType.ASSISTANT
    meta_dict: Optional[Dict[str, str]] = None
    role: str = "system"
    content: str = ""


@dataclass
class UserSystemMessage(SystemMessage):
    r"""Class for system messages from the user used in the CAMEL chat system.

    Args:
        role_name (str): The name of the user role.
        role_type (RoleType): The type of role, always :obj:`RoleType.USER`.
        meta_dict (Optional[Dict[str, str]]): Additional metadata dictionary
            for the message.
        role (str): The role of the message in OpenAI chat system.
            (default: :obj:`"system"`)
        content (str): The content of the message. (default: :obj:`""`)
    """
    role_name: str
    role_type: RoleType = RoleType.USER
    meta_dict: Optional[Dict[str, str]] = None
    role: str = "system"
    content: str = ""
