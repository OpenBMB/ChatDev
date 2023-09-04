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
from typing import Any, Dict, Optional, Union

from camel.agents import ChatAgent
from camel.configs import ChatGPTConfig
from camel.messages import SystemMessage, UserChatMessage
from camel.prompts import PromptTemplateGenerator, TextPrompt
from camel.typing import ModelType, RoleType, TaskType


class TaskSpecifyAgent(ChatAgent):
    r"""An agent that Specifies a given task prompt by prompting the user to
    provide more details.

    Attributes:
        DEFAULT_WORD_LIMIT (int): The default word limit for the task prompt.
        task_specify_prompt (TextPrompt): The prompt for specifying the task.

    Args:
        model (ModelType): The type of model to use for the agent.
            (default: :obj:`ModelType.GPT_3_5_TURBO`)
        task_type (TaskType): The type of task for which to generate a prompt.
            (default: :obj:`TaskType.AI_SOCIETY`)
        model_config (Any): The configuration for the model.
            (default: :obj:`None`)
        task_specify_prompt (Optional[TextPrompt]): The prompt for specifying
            the task. (default: :obj:`None`)
        word_limit (int): The word limit for the task prompt.
            (default: :obj:`50`)
    """
    DEFAULT_WORD_LIMIT = 50

    def __init__(
        self,
        model: Optional[ModelType] = None,
        task_type: TaskType = TaskType.AI_SOCIETY,
        model_config: Optional[Any] = None,
        task_specify_prompt: Optional[Union[str, TextPrompt]] = None,
        word_limit: int = DEFAULT_WORD_LIMIT,
    ) -> None:

        if task_specify_prompt is None:
            task_specify_prompt_template = PromptTemplateGenerator(
            ).get_task_specify_prompt(task_type)

            self.task_specify_prompt = task_specify_prompt_template.format(
                word_limit=word_limit)
        else:
            self.task_specify_prompt = task_specify_prompt

        model_config = model_config or ChatGPTConfig(temperature=1.0)

        system_message = SystemMessage(
            role_name="Task Specifier",
            role_type=RoleType.ASSISTANT,
            content="You can make a task more specific.",
        )
        super().__init__(system_message, model, model_config)

    def step(
        self,
        original_task_prompt: Union[str, TextPrompt],
        meta_dict: Optional[Dict[str, Any]] = None,
    ) -> TextPrompt:
        r"""Specify the given task prompt by providing more details.

        Args:
            original_task_prompt (Union[str, TextPrompt]): The original task
                prompt.
            meta_dict (Optional[Dict[str, Any]]): A dictionary containing
                additional information to include in the prompt.
                (default: :obj:`None`)

        Returns:
            TextPrompt: The specified task prompt.
        """
        self.reset()
        self.task_specify_prompt = self.task_specify_prompt.format(
            task=original_task_prompt)

        if meta_dict is not None:
            self.task_specify_prompt = (self.task_specify_prompt.format(
                **meta_dict))

        task_msg = UserChatMessage(role_name="Task Specifier",
                                   content=self.task_specify_prompt)
        specifier_response = super().step(task_msg)
        if (specifier_response.msgs is None
                or len(specifier_response.msgs) == 0):
            raise RuntimeError("Task specification failed.")
        specified_task_msg = specifier_response.msgs[0]

        if specifier_response.terminated:
            raise RuntimeError("Task specification failed.")

        return TextPrompt(specified_task_msg.content)


class TaskPlannerAgent(ChatAgent):
    r"""An agent that helps divide a task into subtasks based on the input
    task prompt.

    Attributes:
        task_planner_prompt (TextPrompt): A prompt for the agent to divide
            the task into subtasks.

    Args:
        model (ModelType): The type of model to use for the agent.
            (default: :obj:`ModelType.GPT_3_5_TURBO`)
        model_config (Any): The configuration for the model.
            (default: :obj:`None`)
    """

    def __init__(
        self,
        model: Optional[ModelType] = None,
        model_config: Any = None,
    ) -> None:

        self.task_planner_prompt = TextPrompt(
            "Divide this task into subtasks: {task}. Be concise.")

        system_message = SystemMessage(
            role_name="Task Planner",
            role_type=RoleType.ASSISTANT,
            content="You are a helpful task planner.",
        )
        super().__init__(system_message, model, model_config)

    def step(
        self,
        task_prompt: Union[str, TextPrompt],
    ) -> TextPrompt:
        r"""Generate subtasks based on the input task prompt.

        Args:
            task_prompt (Union[str, TextPrompt]): The prompt for the task to
                be divided into subtasks.

        Returns:
            TextPrompt: A prompt for the subtasks generated by the agent.
        """
        # TODO: Maybe include roles information.
        self.reset()
        self.task_planner_prompt = self.task_planner_prompt.format(
            task=task_prompt)

        task_msg = UserChatMessage(role_name="Task Planner",
                                   content=self.task_planner_prompt)
        # sub_tasks_msgs, terminated, _
        task_tesponse = super().step(task_msg)

        if task_tesponse.msgs is None:
            raise RuntimeError("Got None Subtasks messages.")
        if task_tesponse.terminated:
            raise RuntimeError("Task planning failed.")

        sub_tasks_msg = task_tesponse.msgs[0]
        return TextPrompt(sub_tasks_msg.content)
