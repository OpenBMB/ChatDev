import importlib
import os
from abc import ABC, abstractmethod
from collections import defaultdict

from camel.typing import ModelType
from chatdev.chat_env import ChatEnv
from chatdev.utils import log_and_print_online


def check_bool(s):
    return s.lower() == "true"


class ComposedPhase(ABC):
    def __init__(self,
                 phase_name: str = None,
                 cycle_num: int = None,
                 composition: list = None,
                 config_phase: dict = None,
                 config_role: dict = None,
                 model_type: ModelType = ModelType.GPT_3_5_TURBO,
                 log_filepath: str = ""
                 ):
        """

        Args:
            phase_name: name of this phase
            cycle_num: loop times of this phase
            composition: list of SimplePhases in this ComposePhase
            config_phase: configuration of all SimplePhases
            config_role: configuration of all Roles
        """

        self.phase_name = phase_name
        self.cycle_num = cycle_num
        self.composition = composition
        self.model_type = model_type
        self.log_filepath = log_filepath

        self.config_phase = config_phase
        self.config_role = config_role

        self.phase_env = dict()
        self.phase_env["cycle_num"] = cycle_num

        # init chat turn
        self.chat_turn_limit_default = 10

        # init role
        self.role_prompts = dict()
        for role in self.config_role:
            self.role_prompts[role] = "\n".join(self.config_role[role])

        # init all SimplePhases instances in this ComposedPhase
        self.phases = dict()
        for phase in self.config_phase:
            assistant_role_name = self.config_phase[phase]['assistant_role_name']
            user_role_name = self.config_phase[phase]['user_role_name']
            phase_prompt = "\n".join(self.config_phase[phase]['phase_prompt'])
            phase_module = importlib.import_module("chatdev.phase")
            phase_class = getattr(phase_module, phase)
            phase_instance = phase_class(assistant_role_name=assistant_role_name,
                                         user_role_name=user_role_name,
                                         phase_prompt=phase_prompt,
                                         role_prompts=self.role_prompts,
                                         phase_name=phase,
                                         model_type=self.model_type,
                                         log_filepath=self.log_filepath)
            self.phases[phase] = phase_instance

    @abstractmethod
    def update_phase_env(self, chat_env):
        """
        update self.phase_env (if needed) using chat_env, then the chatting will use self.phase_env to follow the context and fill placeholders in phase prompt
        must be implemented in customized phase
        the usual format is just like:
        ```
            self.phase_env.update({key:chat_env[key]})
        ```
        Args:
            chat_env: global chat chain environment

        Returns: None

        """
        pass

    @abstractmethod
    def update_chat_env(self, chat_env) -> ChatEnv:
        """
        update chan_env based on the results of self.execute, which is self.seminar_conclusion
        must be implemented in customized phase
        the usual format is just like:
        ```
            chat_env.xxx = some_func_for_postprocess(self.seminar_conclusion)
        ```
        Args:
            chat_env:global chat chain environment

        Returns:
            chat_env: updated global chat chain environment

        """
        pass

    @abstractmethod
    def break_cycle(self, phase_env) -> bool:
        """
        special conditions for early break the loop in ComposedPhase
        Args:
            phase_env: phase environment

        Returns: None

        """
        pass

    def execute(self, chat_env) -> ChatEnv:
        """
        similar to Phase.execute, but add control for breaking the loop
        1. receive information from environment(ComposedPhase): update the phase environment from global environment
        2. for each SimplePhase in ComposedPhase
            a) receive information from environment(SimplePhase)
            b) check loop break
            c) execute the chatting
            d) change the environment(SimplePhase)
            e) check loop break
        3. change the environment(ComposedPhase): update the global environment using the conclusion

        Args:
            chat_env: global chat chain environment

        Returns:

        """
        self.update_phase_env(chat_env)
        for cycle_index in range(1, self.cycle_num + 1):
            for phase_item in self.composition:
                assert phase_item["phaseType"] == "SimplePhase"  # right now we do not support nested composition
                phase = phase_item['phase']
                max_turn_step = phase_item['max_turn_step']
                need_reflect = check_bool(phase_item['need_reflect'])
                self.phase_env["cycle_index"] = cycle_index
                log_and_print_online(
                    f"**[Execute Detail]**\n\nexecute SimplePhase:[{phase}] in ComposedPhase:[{self.phase_name}], cycle {cycle_index}")
                if phase in self.phases:
                    self.phases[phase].phase_env = self.phase_env
                    self.phases[phase].update_phase_env(chat_env)
                    if self.break_cycle(self.phases[phase].phase_env):
                        return chat_env
                    chat_env = self.phases[phase].execute(chat_env,
                                                          self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step,
                                                          need_reflect)
                    if self.break_cycle(self.phases[phase].phase_env):
                        return chat_env
                else:
                    print(f"Phase '{phase}' is not yet implemented. \
                            Please write its config in phaseConfig.json \
                            and implement it in chatdev.phase")
        chat_env = self.update_chat_env(chat_env)
        return chat_env


class Art(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pass

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, chat_env) -> bool:
        return False


class CodeCompleteAll(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pyfiles = [filename for filename in os.listdir(chat_env.env_dict['directory']) if filename.endswith(".py")]
        num_tried = defaultdict(int)
        num_tried.update({filename: 0 for filename in pyfiles})
        self.phase_env.update({
            "max_num_implement": 5,
            "pyfiles": pyfiles,
            "num_tried": num_tried
        })

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        if phase_env['unimplemented_file'] == "":
            return True
        else:
            return False


class CodeReview(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"modification_conclusion": ""})

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        if "<INFO> Finished".lower() in phase_env['modification_conclusion'].lower():
            return True
        else:
            return False


class HumanAgentInteraction(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"modification_conclusion": "", "comments": ""})

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        if "<INFO> Finished".lower() in phase_env['modification_conclusion'].lower() or phase_env["comments"].lower() == "exit":
            return True
        else:
            return False


class Test(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pass

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        if not phase_env['exist_bugs_flag']:
            log_and_print_online(f"**[Test Info]**\n\nAI User (Software Test Engineer):\nTest Pass!\n")
            return True
        else:
            return False
