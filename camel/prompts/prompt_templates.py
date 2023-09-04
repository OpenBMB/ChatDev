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
import warnings
from typing import Any, Optional

from camel.prompts import TaskPromptTemplateDict, TextPrompt
from camel.typing import RoleType, TaskType


class PromptTemplateGenerator:
    r"""A class for generating prompt templates for tasks.

    Args:
        task_prompt_template_dict (TaskPromptTemplateDict, optional):
            A dictionary of task prompt templates for each task type. If not
            provided, an empty dictionary is used as default.
    """

    def __init__(
        self,
        task_prompt_template_dict: Optional[TaskPromptTemplateDict] = None,
    ) -> None:
        self.task_prompt_template_dict = (task_prompt_template_dict or TaskPromptTemplateDict())

    def get_prompt_from_key(self, task_type: TaskType, key: Any) -> TextPrompt:
        r"""Generates a text prompt using the specified :obj:`task_type` and
        :obj:`key`.

        Args:
            task_type (TaskType): The type of task.
            key (Any): The key used to generate the prompt.

        Returns:
            TextPrompt: The generated text prompt.

        Raises:
            KeyError: If failed to generate prompt using the specified
                :obj:`task_type` and :obj:`key`.
        """
        try:
            print(task_type, key)
            return self.task_prompt_template_dict[task_type][key]

        except KeyError:
            raise KeyError("Failed to get generate prompt template for "
                           f"task: {task_type.value} from key: {key}.")

    def get_system_prompt(
        self,
        task_type: TaskType,
        role_type: RoleType,
    ) -> TextPrompt:
        r"""Generates a text prompt for the system role, using the specified
        :obj:`task_type` and :obj:`role_type`.

        Args:
            task_type (TaskType): The type of task.
            role_type (RoleType): The type of role, either "USER" or
                "ASSISTANT".

        Returns:
            TextPrompt: The generated text prompt.

        Raises:
            KeyError: If failed to generate prompt using the specified
                :obj:`task_type` and :obj:`role_type`.
        """
        try:
            return self.get_prompt_from_key(task_type, role_type)

        except KeyError:
            prompt = "You are a helpful assistant."

            warnings.warn("Failed to get system prompt template for "
                          f"task: {task_type.value}, role: {role_type.value}. "
                          f"Set template to: {prompt}")

        return TextPrompt(prompt)

    def get_generate_tasks_prompt(
        self,
        task_type: TaskType,
    ) -> TextPrompt:
        r"""Gets the prompt for generating tasks for a given task type.

        Args:
            task_type (TaskType): The type of the task.

        Returns:
            TextPrompt: The generated prompt for generating tasks.
        """
        return self.get_prompt_from_key(task_type, "generate_tasks")

    def get_task_specify_prompt(
        self,
        task_type: TaskType,
    ) -> TextPrompt:
        r"""Gets the prompt for specifying a task for a given task type.

        Args:
            task_type (TaskType): The type of the task.

        Returns:
            TextPrompt: The generated prompt for specifying a task.
        """
        return self.get_prompt_from_key(task_type, "task_specify_prompt")
