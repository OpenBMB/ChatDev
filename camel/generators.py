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
from typing import Dict, Generator, List, Optional, Set, Tuple

from camel.messages import SystemMessage, SystemMessageType
from camel.prompts import PromptTemplateGenerator, TextPrompt
from camel.typing import RoleType, TaskType


class SystemMessageGenerator:
    r"""System message generator for agents.

    Args:
        task_type (TaskType, optional): The task type.
            (default: :obj:`TaskType.AI_SOCIETY`)
        sys_prompts (Optional[Dict[RoleType, str]], optional): The prompts of
            the system messages for each role type. (default: :obj:`None`)
        sys_msg_meta_dict_keys (Optional[Set[str]], optional): The set of keys
            of the meta dictionary used to fill the prompts.
            (default: :obj:`None`)
    """

    def __init__(
        self,
        task_type: TaskType = TaskType.AI_SOCIETY,
        sys_prompts: Optional[Dict[RoleType, str]] = None,
        sys_msg_meta_dict_keys: Optional[Set[str]] = None,
    ) -> None:
        self.sys_prompts: Dict[RoleType, str]

        if sys_prompts is not None:
            self.sys_prompts = sys_prompts
            self.sys_msg_meta_dict_keys = sys_msg_meta_dict_keys or set()
        else:
            templates = PromptTemplateGenerator()
            agenttech_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV)
            counselor_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_COUNSELOR)
            ceo_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_CEO)
            chro_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_CHRO)
            cpo_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_CPO)
            cto_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_CTO)
            programmer_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_PROGRAMMER)
            reviewer_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_REVIEWER)
            tester_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_TESTER)
            cco_prompt_template = templates.get_system_prompt(task_type, RoleType.CHATDEV_CCO)

            self.sys_prompts = dict()
            self.sys_prompts[RoleType.CHATDEV] = agenttech_prompt_template
            self.sys_prompts[RoleType.CHATDEV_COUNSELOR] = counselor_prompt_template
            self.sys_prompts[RoleType.CHATDEV_CEO] = ceo_prompt_template
            self.sys_prompts[RoleType.CHATDEV_CHRO] = chro_prompt_template
            self.sys_prompts[RoleType.CHATDEV_CPO] = cpo_prompt_template
            self.sys_prompts[RoleType.CHATDEV_CTO] = cto_prompt_template
            self.sys_prompts[RoleType.CHATDEV_PROGRAMMER] = programmer_prompt_template
            self.sys_prompts[RoleType.CHATDEV_REVIEWER] = reviewer_prompt_template
            self.sys_prompts[RoleType.CHATDEV_TESTER] = tester_prompt_template
            self.sys_prompts[RoleType.CHATDEV_CCO] = cco_prompt_template

            self.sys_msg_meta_dict_keys = (agenttech_prompt_template.key_words |
                                           counselor_prompt_template.key_words |
                                           ceo_prompt_template.key_words |
                                           chro_prompt_template.key_words |
                                           cpo_prompt_template.key_words |
                                           cto_prompt_template.key_words |
                                           programmer_prompt_template.key_words |
                                           reviewer_prompt_template.key_words |
                                           tester_prompt_template.key_words |
                                           cco_prompt_template.key_words)

        if RoleType.DEFAULT not in self.sys_prompts:
            self.sys_prompts[RoleType.DEFAULT] = "You are a helpful assistant."

    def validate_meta_dict_keys(self, meta_dict: Dict[str, str]) -> None:
        r"""Validates the keys of the meta_dict.

        Args:
            meta_dict (Dict[str, str]): The dictionary to validate.
        """
        if not set(meta_dict.keys()).issubset(self.sys_msg_meta_dict_keys):
            raise ValueError("The keys of the meta_dict should be in "
                             f"{self.sys_msg_meta_dict_keys}. "
                             f"Got {set(meta_dict.keys())} instead.")

    def from_dict(
        self,
        meta_dict: Dict[str, str],
        role_tuple: Tuple[str, RoleType] = ("", RoleType.DEFAULT),
    ) -> SystemMessageType:
        r"""Generates a system message from a dictionary.

        Args:
            meta_dict (Dict[str, str]): The dictionary containing the
                information to generate the system message.
            role_tuple (Tuple[str, RoleType], optional): The tuple containing
                the role name and role type. (default: ("", RoleType.DEFAULT))

        Returns:
            SystemMessageType: The generated system message.
        """
        self.validate_meta_dict_keys(meta_dict)
        role_name, role_type = role_tuple
        sys_prompt = self.sys_prompts[role_type]
        sys_prompt = sys_prompt.format(**meta_dict)

        return SystemMessage(role_name=role_name, role_type=RoleType.DEFAULT,
                             meta_dict=meta_dict, content=sys_prompt)

    def from_dicts(
        self,
        meta_dicts: List[Dict[str, str]],
        role_tuples: Tuple[str, str],
    ) -> List[SystemMessageType]:
        r"""Generates a list of system messages from a list of dictionaries.

        Args:
            meta_dicts (List[Dict[str, str]]): A list of dictionaries
                containing the information to generate the system messages.
            role_tuples (List[Tuple[str, RoleType]]): A list of tuples
                containing the role name and role type for each system message.

        Returns:
            List[SystemMessageType]: A list of generated system messages.

        Raises:
            ValueError: If the number of meta_dicts and role_tuples are
                different.
        """
        if len(meta_dicts) != len(role_tuples):
            raise ValueError(
                "The number of meta_dicts and role_types should be the same.")

        return [
            self.from_dict(meta_dict, role_tuple)
            for meta_dict, role_tuple in zip(meta_dicts, role_tuples)
        ]


class RoleNameGenerator:

    def __init__(self, assistant_role_names_path:
                 str = "data/ai_society/assistant_roles.txt",
                 user_role_names_path: str = "data/ai_society/user_roles.txt",
                 assistant_role_names: Optional[List[str]] = None,
                 user_role_names: Optional[List[str]] = None) -> None:

        if assistant_role_names is None:
            with open(assistant_role_names_path, "r") as f:
                assistant_role_names_: List[str] = f.read().splitlines()
                self.assistant_role_names = [
                    " ".join(name.split(" ")[1:])
                    for name in assistant_role_names_
                ]
        else:
            self.assistant_role_names = assistant_role_names

        if user_role_names is None:
            with open(user_role_names_path, "r") as f:
                user_role_names_: List[str] = f.read().splitlines()
                self.user_role_names = [
                    " ".join(name.split(" ")[1:]) for name in user_role_names_
                ]
        else:
            self.user_role_names = user_role_names

    def from_role_files(self) -> Generator[Tuple, None, None]:
        for assistant_role_name in self.assistant_role_names:
            for user_role_name in self.user_role_names:
                yield (assistant_role_name, user_role_name)


class AISocietyTaskPromptGenerator:

    def __init__(
        self,
        num_tasks: int = 10,
    ) -> None:
        self.generate_tasks_prompt = PromptTemplateGenerator(
        ).get_generate_tasks_prompt(TaskType.AI_SOCIETY)

        self.num_tasks = num_tasks

    # TODO: Return role names for user and assistant with the generator.
    def from_role_files(
        self,
        assistant_role_names_path: str = "data/ai_society/assistant_roles.txt",
        user_role_names_path: str = "data/ai_society/user_roles.txt"
    ) -> Generator[Tuple[str, Tuple[str, str]], None, None]:
        roles_generator = RoleNameGenerator(
            assistant_role_names_path, user_role_names_path).from_role_files()
        for role_1, role_2 in roles_generator:
            generate_tasks_prompt = self.generate_tasks_prompt.format(
                assistant_role=role_1, user_role=role_2,
                num_tasks=self.num_tasks)

            yield (generate_tasks_prompt, (role_1, role_2))

    def from_role_generator(
        self, role_generator: Generator[Tuple, None, None]
    ) -> Generator[Tuple[str, Tuple[str, str]], None, None]:
        for role_1, role_2 in role_generator:
            generate_tasks_prompt = self.generate_tasks_prompt.format(
                assistant_role=role_1, user_role=role_2,
                num_tasks=self.num_tasks)

            yield (generate_tasks_prompt, (role_1, role_2))


class SingleTxtGenerator:

    def __init__(
        self,
        text_file_path: str,
    ) -> None:

        with open(text_file_path, "r") as f:
            data_list: List[str] = f.read().splitlines()
            self.data_list = [
                " ".join(name.split(" ")[1:]) for name in data_list
            ]

    def from_role_files(self) -> Generator[str, None, None]:
        for data in self.data_list:
            yield data


class CodeTaskPromptGenerator:

    def __init__(
        self,
        num_tasks: int = 50,
    ) -> None:

        self.generate_tasks_prompt = PromptTemplateGenerator(
        ).get_generate_tasks_prompt(TaskType.CODE)

        self.num_tasks = num_tasks

    def from_role_files(
        self, languages_path: str = "data/code/languages.txt",
        domains_path: str = "data/code/domains.txt"
    ) -> Generator[Tuple[TextPrompt, str, str], None, None]:
        language_generator = SingleTxtGenerator(
            languages_path).from_role_files()

        for language in language_generator:
            domains_generator = SingleTxtGenerator(
                domains_path).from_role_files()
            for domain in domains_generator:
                generated_tasks_prompt = self.generate_tasks_prompt.format(
                    language=language, domain=domain, num_tasks=self.num_tasks)
                yield generated_tasks_prompt, language, domain

    def from_role_generator(
        self, role_generator: Generator[Tuple, None, None]
    ) -> Generator[str, None, None]:
        raise NotImplementedError
