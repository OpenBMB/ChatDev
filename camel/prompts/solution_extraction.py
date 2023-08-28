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
from typing import Any

from camel.prompts import TextPrompt, TextPromptDict
from camel.typing import RoleType


# flake8: noqa
class SolutionExtractionPromptTemplateDict(TextPromptDict):
    r"""A dictionary containing :obj:`TextPrompt` used in the `SolutionExtraction`
    task.

    Attributes:
        ASSISTANT_PROMPT (TextPrompt): A system prompt for the AI assistant
            that outlines the rules of the conversation and provides
            instructions for completing tasks.
    """
    ASSISTANT_PROMPT = TextPrompt(
        """You are an experienced solution extracting agent. 
Your task is to extract full and complete solutions by looking at the conversation between a user and an assistant with particular specializations. 
You should present me with a final and detailed solution purely based on the conversation. 
You should present the solution as if its yours. 
Use present tense and as if you are the one presenting the solution. 
You should not miss any necessary details or examples.
Keep all provided explanations and codes provided throughout the conversation. 
Remember your task is not to summarize rather to extract the full solution.""")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.update({
            RoleType.ASSISTANT: self.ASSISTANT_PROMPT,
        })
