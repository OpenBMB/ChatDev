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
from camel.agents import BaseAgent


class BaseToolAgent(BaseAgent):
    r"""Creates a :obj:`BaseToolAgent` object with the specified name and
        description.

    Args:
        name (str): The name of the tool agent.
        description (str): The description of the tool agent.
    """

    def __init__(self, name: str, description: str) -> None:

        self.name = name
        self.description = description

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"
