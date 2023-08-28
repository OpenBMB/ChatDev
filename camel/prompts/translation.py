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


# flake8: noqa :E501
class TranslationPromptTemplateDict(TextPromptDict):
    r"""A dictionary containing :obj:`TextPrompt` used in the `Translation`
    task.

    Attributes:
        ASSISTANT_PROMPT (TextPrompt): A system prompt for the AI assistant
            that outlines the rules of the conversation and provides
            instructions for completing tasks.
    """
    ASSISTANT_PROMPT = TextPrompt(
        """You are an expert English to {language} translator.
Your sole purpose is to accurately translate any text presented to you from English to {language}.
Please provide the {language} translation for the given text.
If you are presented with an empty string, simply return an empty string as the translation.
Only text in between ```TEXT``` should not be translated.
Do not provide any explanation. Just provide a translation.""")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.update({
            RoleType.ASSISTANT: self.ASSISTANT_PROMPT,
        })
