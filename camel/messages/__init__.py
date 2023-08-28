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
from typing import Dict, Union

OpenAISystemMessage = Dict[str, str]
OpenAIAssistantMessage = Dict[str, str]
OpenAIUserMessage = Dict[str, str]
OpenAIChatMessage = Union[OpenAIUserMessage, OpenAIAssistantMessage]
OpenAIMessage = Union[OpenAISystemMessage, OpenAIChatMessage]

from .base import BaseMessage  # noqa: E402
from .system_messages import (  # noqa: E402
    SystemMessage, AssistantSystemMessage, UserSystemMessage,
)
from .chat_messages import (  # noqa: E402
    ChatMessage, AssistantChatMessage, UserChatMessage,
)

MessageType = Union[BaseMessage, SystemMessage, AssistantSystemMessage,
                    UserSystemMessage, ChatMessage, AssistantChatMessage,
                    UserChatMessage]
SystemMessageType = Union[SystemMessage, AssistantSystemMessage,
                          UserSystemMessage]
ChatMessageType = Union[ChatMessage, AssistantChatMessage, UserChatMessage]

__all__ = [
    'OpenAISystemMessage',
    'OpenAIAssistantMessage',
    'OpenAIUserMessage',
    'OpenAIChatMessage',
    'OpenAIMessage',
    'BaseMessage',
    'SystemMessage',
    'AssistantSystemMessage',
    'UserSystemMessage',
    'ChatMessage',
    'AssistantChatMessage',
    'UserChatMessage',
    'MessageType',
    'SystemMessageType',
    'ChatMessageType',
]
