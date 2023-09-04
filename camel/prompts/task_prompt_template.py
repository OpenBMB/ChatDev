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
from typing import Any, Dict

from camel.prompts import (
    TextPromptDict,
)
from camel.typing import TaskType


class TaskPromptTemplateDict(Dict[Any, TextPromptDict]):
    r"""A dictionary (:obj:`Dict[Any, TextPromptDict]`) of task prompt
    templates keyed by task type. This dictionary is used to map from
    a task type to its corresponding prompt template dictionary.

    Args:
        *args: Positional arguments passed to the :obj:`dict` constructor.
        **kwargs: Keyword arguments passed to the :obj:`dict` constructor.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.update({
            TaskType.AI_SOCIETY: AISocietyPromptTemplateDict(),
            TaskType.CODE: CodePromptTemplateDict(),
            TaskType.MISALIGNMENT: MisalignmentPromptTemplateDict(),
            TaskType.TRANSLATION: TranslationPromptTemplateDict(),
            TaskType.EVALUATION: EvaluationPromptTemplateDict(),
            TaskType.SOLUTION_EXTRACTION: SolutionExtractionPromptTemplateDict(),
        })
