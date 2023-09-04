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
from .base import BaseAgent
from .chat_agent import ChatAgent
from .task_agent import TaskPlannerAgent, TaskSpecifyAgent
from .critic_agent import CriticAgent
from .tool_agents.base import BaseToolAgent
from .tool_agents.hugging_face_tool_agent import HuggingFaceToolAgent
from .embodied_agent import EmbodiedAgent
from .role_playing import RolePlaying

__all__ = [
    'BaseAgent',
    'ChatAgent',
    'TaskSpecifyAgent',
    'TaskPlannerAgent',
    'CriticAgent',
    'BaseToolAgent',
    'HuggingFaceToolAgent',
    'EmbodiedAgent',
    'RolePlaying',
]
