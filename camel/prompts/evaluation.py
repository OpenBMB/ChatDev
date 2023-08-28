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


class EvaluationPromptTemplateDict(TextPromptDict):
    r"""A dictionary containing :obj:`TextPrompt` used in the `Evaluation`
    task.

    Attributes:
        GENERATE_QUESTIONS (TextPrompt): A prompt to generate a set of
            questions to be used for evaluating emergence of knowledge based
            on a particular field of knowledge.
    """

    GENERATE_QUESTIONS = TextPrompt(
        """Generate {num_questions} {category} diverse questions.
Here are some example questions:
{examples}

Now generate {num_questions} questions of your own. Be creative""")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.update({
            "generate_questions": self.GENERATE_QUESTIONS,
        })
