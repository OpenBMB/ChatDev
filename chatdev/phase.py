import os
import re
import time
import shutil
from abc import ABC, abstractmethod

from camel.agents import RolePlaying
from camel.messages import ChatMessage
from camel.typing import TaskType, ModelType
from chatdev.chat_env import ChatEnv
from chatdev.statistics import get_info
from chatdev.utils import log_macnet, log_arguments
import hashlib
from chatdev.waiting import Pool
from chatdev.test_unfinished_function import FunctionTest
from chatdev.codes import Codes


class Phase(ABC):

    def __init__(self,
                 assistant_role_name,
                 user_role_name,
                 phase_prompt,
                 role_prompts,
                 phase_name,
                 model_type,
                 log_filepath):
        """

        Args:
            assistant_role_name: who receives chat in a phase
            user_role_name: who starts the chat in a phase
            phase_prompt: prompt of this phase
            role_prompts: prompts of all roles
            phase_name: name of this phase
        """
        self.pool_response = None
        self.pool = None
        self.seminar_conclusion = None
        self.assistant_role_name = assistant_role_name
        self.user_role_name = user_role_name
        self.phase_prompt = phase_prompt
        self.phase_env = dict()
        self.phase_name = phase_name
        self.assistant_role_prompt = role_prompts[assistant_role_name]
        self.user_role_prompt = role_prompts[user_role_name]
        self.ceo_prompt = role_prompts["Chief Executive Officer"]
        self.counselor_prompt = role_prompts["Counselor"]
        self.timeout_seconds = 1.0
        self.max_retries = 3
        self.reflection_prompt = """Here is a conversation between two roles: {conversations} {question}"""
        self.model_type = model_type
        self.log_filepath = log_filepath

    @log_arguments
    def chatting(
            self,
            chat_env,
            task_prompt: str,
            assistant_role_name: str,
            user_role_name: str,
            phase_prompt: str,
            phase_name: str,
            assistant_role_prompt: str,
            user_role_prompt: str,
            task_type=TaskType.CHATDEV,
            need_reflect=False,
            with_task_specify=False,
            memory=None,
            model_type=ModelType.GPT_3_5_TURBO,
            placeholders=None,
            chat_turn_limit=10
    ) -> str:
        """

        Args:
            chat_env: global chatchain environment TODO: only for employee detection, can be deleted
            task_prompt: user query prompt for building the software
            assistant_role_name: who receives the chat
            user_role_name: who starts the chat
            phase_prompt: prompt of the phase
            phase_name: name of the phase
            assistant_role_prompt: prompt of assistant role
            user_role_prompt: prompt of user role
            task_type: task type
            need_reflect: flag for checking reflection
            with_task_specify: with task specify
            model_type: model type
            placeholders: placeholders for phase environment to generate phase prompt
            chat_turn_limit: turn limits in each chat

        Returns:

        """

        if placeholders is None:
            placeholders = {}
        assert 1 <= chat_turn_limit <= 100

        if not chat_env.exist_employee(assistant_role_name):
            raise ValueError(f"{assistant_role_name} not recruited in ChatEnv.")
        if not chat_env.exist_employee(user_role_name):
            raise ValueError(f"{user_role_name} not recruited in ChatEnv.")

        # init role play
        role_play_session = RolePlaying(
            assistant_role_name=assistant_role_name,
            user_role_name=user_role_name,
            assistant_role_prompt=assistant_role_prompt,
            user_role_prompt=user_role_prompt,
            task_prompt=task_prompt,
            task_type=task_type,
            with_task_specify=with_task_specify,
            memory=memory,
            model_type=model_type,
            placeholders=placeholders
        )

        # log_macnet("System", role_play_session.assistant_sys_msg)
        # log_macnet("System", role_play_session.user_sys_msg)

        # start the chat
        _, input_user_msg = role_play_session.init_chat(None, placeholders, phase_prompt)
        # _, input_user_msg = role_play_session.init_chat(None, placeholders, phase_prompt, phase_name)
        seminar_conclusion = None

        # handle chats
        # the purpose of the chatting in one phase is to get a seminar conclusion
        # there are two types of conclusion
        # 1. with "<INFO>" mark
        # 1.1 get seminar conclusion flag (ChatAgent.info) from assistant or user role, which means there exist special "<INFO>" mark in the conversation
        # 1.2 add "<INFO>" to the reflected content of the chat (which may be terminated chat without "<INFO>" mark)
        # 2. without "<INFO>" mark, which means the chat is terminated or normally ended without generating a marked conclusion, and there is no need to reflect
        for i in range(chat_turn_limit):
            # start the chat, we represent the user and send msg to assistant
            # 1. so the input_user_msg should be assistant_role_prompt + phase_prompt
            # 2. then input_user_msg send to LLM and get assistant_response
            # 3. now we represent the assistant and send msg to user, so the input_assistant_msg is user_role_prompt + assistant_response
            # 4. then input_assistant_msg send to LLM and get user_response
            # all above are done in role_play_session.step, which contains two interactions with LLM
            # the first interaction is logged in role_play_session.init_chat
            assistant_response, user_response = role_play_session.step(input_user_msg, chat_turn_limit == 1)

            # conversation_meta = "**" + assistant_role_name + "<->" + user_role_name + " on : " + str(
            #     phase_name) + ", turn " + str(i) + "**\n\n"

            # TODO: max_tokens_exceeded errors here
            if isinstance(assistant_response.msg, ChatMessage):
                # we log the second interaction here
                # log_macnet(role_play_session.assistant_agent.role_name,
                #                      conversation_meta + "[" + role_play_session.user_agent.system_message.content + "]\n\n" + assistant_response.msg.content)
                if role_play_session.assistant_agent.info:
                    seminar_conclusion = assistant_response.msg.content
                    break
                if assistant_response.terminated:
                    break

            if isinstance(user_response.msg, ChatMessage):
                # here is the result of the second interaction, which may be used to start the next chat turn
                # log_macnet(role_play_session.user_agent.role_name,
                #                      conversation_meta + "[" + role_play_session.assistant_agent.system_message.content + "]\n\n" + user_response.msg.content)
                if role_play_session.user_agent.info:
                    seminar_conclusion = user_response.msg.content
                    break
                if user_response.terminated:
                    break

            # continue the chat
            if chat_turn_limit > 1 and isinstance(user_response.msg, ChatMessage):
                input_user_msg = user_response.msg
            else:
                break

        # conduct self reflection
        if need_reflect:
            if seminar_conclusion in [None, ""]:
                seminar_conclusion = "<INFO> " + self.self_reflection(task_prompt, role_play_session, phase_name,
                                                                      chat_env)
            if "recruiting" in phase_name:
                if "Yes".lower() not in seminar_conclusion.lower() and "No".lower() not in seminar_conclusion.lower():
                    seminar_conclusion = "<INFO> " + self.self_reflection(task_prompt, role_play_session,
                                                                          phase_name,
                                                                          chat_env)
            elif seminar_conclusion in [None, ""]:
                seminar_conclusion = "<INFO> " + self.self_reflection(task_prompt, role_play_session, phase_name,
                                                                      chat_env)
        else:
            seminar_conclusion = assistant_response.msg.content

        log_macnet("**[Seminar Conclusion]**:\n\n {}".format(seminar_conclusion))
        seminar_conclusion = seminar_conclusion.split("<INFO>")[-1]
        return seminar_conclusion

    def self_retrieval(self, target_memory, chat_env):
        pass

    def self_reflection(self,
                        task_prompt: str,
                        role_play_session: RolePlaying,
                        phase_name: str,
                        chat_env: ChatEnv) -> str:
        """

        Args:
            task_prompt: user query prompt for building the software
            role_play_session: role play session from the chat phase which needs reflection
            phase_name: name of the chat phase which needs reflection
            chat_env: global chatchain environment

        Returns:
            reflected_content: str, reflected results

        """
        messages = role_play_session.assistant_agent.stored_messages if len(
            role_play_session.assistant_agent.stored_messages) >= len(
            role_play_session.user_agent.stored_messages) else role_play_session.user_agent.stored_messages
        messages = ["{}: {}".format(message.role_name, message.content.replace("\n\n", "\n")) for message in messages]
        messages = "\n\n".join(messages)

        if "recruiting" in phase_name:
            question = """Answer their final discussed conclusion (Yes or No) in the discussion without any other words, e.g., "Yes" """
        elif phase_name == "DemandAnalysis":
            question = """Answer their final product modality in the discussion without any other words, e.g., "PowerPoint" """
        # elif phase_name in [PhaseType.BRAINSTORMING]:
        #     question = """Conclude three most creative and imaginative brainstorm ideas from the whole discussion, in the format: "1) *; 2) *; 3) *; where '*' represents a suggestion." """
        elif phase_name == "LanguageChoose":
            question = """Conclude the programming language being discussed for software development, in the format: "*" where '*' represents a programming language." """
        elif phase_name == "EnvironmentDoc":
            question = """According to the codes and file format listed above, write a requirements.txt file to specify the dependencies or packages required for the project to run properly." """
        else:
            raise ValueError(f"Reflection of phase {phase_name}: Not Assigned.")

        # Reflections actually is a special phase between CEO and counselor
        # They read the whole chatting history of this phase and give refined conclusion of this phase
        reflected_content = \
            self.chatting(chat_env=chat_env,
                          task_prompt=task_prompt,
                          assistant_role_name="Chief Executive Officer",
                          user_role_name="Counselor",
                          phase_prompt=self.reflection_prompt,
                          phase_name="Reflection",
                          assistant_role_prompt=self.ceo_prompt,
                          user_role_prompt=self.counselor_prompt,
                          placeholders={"conversations": messages, "question": question},
                          need_reflect=False,
                          memory=chat_env.memory,
                          chat_turn_limit=1,
                          model_type=self.model_type)

        if "recruiting" in phase_name:
            if "Yes".lower() in reflected_content.lower():
                return "Yes"
            return "No"
        else:
            return reflected_content

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

    def execute(self, chat_env, chat_turn_limit, need_reflect) -> ChatEnv:
        """
        execute the chatting in this phase
        1. receive information from environment: update the phase environment from global environment
        2. execute the chatting
        3. change the environment: update the global environment using the conclusion
        Args:
            chat_env: global chat chain environment
            chat_turn_limit: turn limit in each chat
            need_reflect: flag for reflection

        Returns:
            chat_env: updated global chat chain environment using the conclusion from this phase execution

        """
        self.update_phase_env(chat_env)
        self.seminar_conclusion = \
            self.chatting(chat_env=chat_env,
                          task_prompt=chat_env.env_dict['task_prompt'],
                          need_reflect=need_reflect,
                          assistant_role_name=self.assistant_role_name,
                          user_role_name=self.user_role_name,
                          phase_prompt=self.phase_prompt,
                          phase_name=self.phase_name,
                          assistant_role_prompt=self.assistant_role_prompt,
                          user_role_prompt=self.user_role_prompt,
                          chat_turn_limit=chat_turn_limit,
                          placeholders=self.phase_env,
                          memory=chat_env.memory,
                          model_type=self.model_type)
        chat_env = self.update_chat_env(chat_env)
        if self.phase_name == 'Coding' and chat_env.env_dict['cc'] == 'on':
            index = 0
            file = 'A.txt'
            file_path = './Coding'
            while os.path.exists(os.path.join(file_path, file)):
                index += 1
                file = '{}.txt'.format(chr(ord('A') + index))
            file_name = os.path.splitext(file)[0]
            with open(os.path.join(file_path, file), "a") as f:
                for key in chat_env.codes.codebooks.keys():
                    f.write(str(key) + '\n\n' + chat_env.codes.codebooks[key] + '\n\n')
            with open(os.path.join(chat_env.env_dict['directory'], 'team_name.txt'), 'w') as f:
                f.write(file_name)
        return chat_env


class DemandAnalysis(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pass

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0:
            chat_env.env_dict['modality'] = self.seminar_conclusion.split("<INFO>")[-1].lower().replace(".", "").strip()
        return chat_env


class LanguageChoose(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "description": "chat_env.env_dict['task_description']",
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0 and "<INFO>" in self.seminar_conclusion:
            chat_env.env_dict['language'] = self.seminar_conclusion.split("<INFO>")[-1].lower().replace(".", "").strip()
        elif len(self.seminar_conclusion) > 0:
            chat_env.env_dict['language'] = self.seminar_conclusion
        else:
            chat_env.env_dict['language'] = "Python"
        return chat_env


class Coding(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        gui = "" if not chat_env.config.gui_design \
            else "The software should be equipped with graphical user interface (GUI) so that user can visually and graphically use it; so you must choose a GUI framework (e.g., in Python, you can implement GUI via tkinter, Pygame, Flexx, PyGUI, etc,)."
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "description": "chat_env.env_dict['task_description']",
                               "language": chat_env.env_dict['language'],
                               "gui": gui})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.update_codes(self.seminar_conclusion)
        if len(chat_env.codes.codebooks.keys()) == 0:
            raise ValueError("No Valid Codes.")
        chat_env.rewrite_codes()
        log_macnet(
            "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env


class Coding_wait(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        gui = "" if not chat_env.config.gui_design \
            else ("The software should be equipped with graphical user interface (GUI) so that user can visually and "
                  "graphically use it; so you must choose a GUI framework (e.g., in Python, you can implement GUI via "
                  "tkinter, Pygame, Flexx, PyGUI, etc,).")
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "description": "chat_env.env_dict['task_description']",
                               "language": chat_env.env_dict['language'],
                               "gui": gui})

    def update_chat_env(self, chat_env) -> ChatEnv:
        team_number = chat_env.env_dict['t_num']
        unit_number = chat_env.env_dict['unit_num']
        directory = chat_env.env_dict['directory']
        start_time = time.time()
        max_duration = chat_env.env_dict['time']
        task_prompt = chat_env.env_dict['task_prompt']
        wait_time = chat_env.env_dict['time']
        self.pool = Pool(team_number, unit_number, directory, self.model_type)
        while True:
            new_codes = self.pool.state_pool_add(self.phase_name, self.phase_prompt, wait_time, task_prompt,
                                                 chat_env.codes)
            if new_codes is not None:
                if chat_env.codes.codebooks != {} and len(new_codes.codebooks.keys()) != 0:
                    chat_env.codes.codebooks = new_codes.codebooks
                    print('replacement succeed.')
                else:
                    print('Codebook is empty.')
                break
            else:
                time.sleep(1)
                current_time = time.time()
                elapsed_time = current_time - start_time
                print("I have slept at Coding_wait for {:.2f} seconds, continue.".format(elapsed_time),
                      end='\r')
                if elapsed_time >= max_duration:
                    print("{} phase has waited more than a minute, continue.".format('Coding'))
                    break
                continue

        if len(chat_env.codes.codebooks.keys()) == 0:
            raise ValueError("No Valid Codes.")
        chat_env.rewrite_codes()
        log_macnet(
            "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env


class ArtDesign(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = {"task": chat_env.env_dict['task_prompt'],
                          "description": chat_env.env_dict['task_description'],
                          "language": chat_env.env_dict['language'],
                          "codes": chat_env.get_codes()}

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.proposed_images = chat_env.get_proposed_images_from_message(self.seminar_conclusion)
        log_macnet(
            "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env


class ArtIntegration(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = {"task": chat_env.env_dict['task_prompt'],
                          "language": chat_env.env_dict['language'],
                          "codes": chat_env.get_codes(),
                          "images": "\n".join(
                              ["{}: {}".format(filename, chat_env.proposed_images[filename]) for
                               filename in sorted(list(chat_env.proposed_images.keys()))])}

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.update_codes(self.seminar_conclusion)
        chat_env.rewrite_codes()
        # chat_env.generate_images_from_codes()
        log_macnet(
            "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env


class CodeComplete(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                               "unimplemented_file": ""})

        if "code_fingerprint_list" not in self.phase_env.keys():
            self.phase_env["code_fingerprint_list"] = []
        self.phase_env["code_fingerprint_list"].append(
            hashlib.md5(chat_env.get_codes().encode(encoding='UTF-8')).hexdigest())

        unimplemented_file = ""
        pyfiles_list = []
        for key in chat_env.codes.codebooks.keys():
            pyfiles_list.append(key)
        self.phase_env['pyfiles'] = pyfiles_list.copy()
        folder_path = chat_env.env_dict['directory']
        all_files = os.listdir(folder_path)
        for file_name in all_files:
            file_path = os.path.join(folder_path, file_name)
            if file_name.endswith('.py') and file_name not in pyfiles_list:
                os.remove(file_path)

        function_test = FunctionTest(chat_env.env_dict['directory'])
        need_complete = function_test.extract_function_name()
        if len(need_complete) > 0:
            for filename, function in need_complete.items():
                unimplemented_file = filename
                unfinished_function = '\n'
                index = 0
                for per_function in need_complete[filename]:
                    unfinished_function += str(index) + ': def ' + per_function + '\n'
                    index += 1
                self.phase_env['unimplemented_functions'] = unfinished_function
                self.phase_env['num_tried'][unimplemented_file] += 1
                self.phase_env['unimplemented_file'] = unimplemented_file
                break

        if len(need_complete) == 0 and chat_env.env_dict['cc'] == 'on' and self.phase_env['cycle_index'] == 0:
            CodeComplete_path = os.path.dirname(os.path.dirname(chat_env.env_dict['directory']))
            with open(os.path.join(chat_env.env_dict['directory'], 'team_name.txt'), 'r') as f:
                file_name = f.read()
            empty_txt_path = CodeComplete_path + '/CodeComplete/{}.txt'.format(file_name)
            with open(empty_txt_path, 'w') as f:
                pass
            chat_env.env_dict['wait_flag'] = False

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.update_codes(self.seminar_conclusion)
        if len(chat_env.codes.codebooks.keys()) == 0:
            raise ValueError("No Valid Codes.")
        chat_env.rewrite_codes()
        log_macnet(
            "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env


class CodeComplete_wait(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                               "unimplemented_file": ""})

    def update_chat_env(self, chat_env) -> ChatEnv:
        team_number = chat_env.env_dict['t_num']
        unit_number = chat_env.env_dict['unit_num']
        directory = chat_env.env_dict['directory']
        self.pool = Pool(team_number, unit_number, directory, self.model_type)
        start_time = time.time()
        max_duration = chat_env.env_dict['time']
        while True:
            folder_path = './CodeComplete'
            all_files = os.listdir(folder_path)
            txt_files = [file for file in all_files if file.endswith('.txt')]
            txt_files_count = len(txt_files)
            if txt_files_count == chat_env.env_dict['t_num']:
                improved_path = './tmp/improved_codes'
                files = os.listdir(improved_path)
                for file in files:
                    file_path = os.path.join(improved_path, file)
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"Failed to delete file: {e}")
                break
            else:
                time.sleep(1)
                current_time = time.time()
                elapsed_time = current_time - start_time
                print("I have slept at CodeComplete_wait for {:.2f} seconds, continue.".format(elapsed_time),
                      end='\r')
                if elapsed_time >= max_duration:
                    print("{} phase has waited more than a minute, continue.".format('Coding'))
                    break
        start_time = time.time()
        max_duration = chat_env.env_dict['time']
        task_prompt = chat_env.env_dict['task_prompt']
        wait_time = chat_env.env_dict['time']
        while True:
            new_codes = self.pool.state_pool_add(self.phase_name, self.phase_prompt, wait_time, task_prompt,
                                                 chat_env.codes)
            if new_codes is not None:
                if chat_env.codes.codebooks != {} and len(new_codes.codebooks.keys()) != 0:
                    chat_env.codes.codebooks = new_codes.codebooks
                    print('replacement succeed.')
                else:
                    print('Codebook is empty.')
                break
            else:
                time.sleep(1)
                print("I have slept at CodeComplete_wait for {:.2f} seconds, continue.".format(elapsed_time),
                      end='\r')
                current_time = time.time()
                elapsed_time = current_time - start_time
                if elapsed_time >= max_duration:
                    print("{} phase has waited more than a minute, continue.".format('Coding'))
                    break
                continue

        # chat_env.update_codes(self.seminar_conclusion)
        if len(chat_env.codes.codebooks.keys()) == 0:
            raise ValueError("No Valid Codes.")
        chat_env.rewrite_codes()
        log_macnet(
            "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env


class CodeReviewComment(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update(
            {"task": chat_env.env_dict['task_prompt'],
             "modality": chat_env.env_dict['modality'],
             "ideas": chat_env.env_dict['ideas'],
             "language": chat_env.env_dict['language'],
             "codes": chat_env.get_codes(),
             "images": ", ".join(chat_env.incorporated_images)})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['review_comments'] = self.seminar_conclusion
        return chat_env


class CodeReviewModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                               "comments": chat_env.env_dict['review_comments']})

        if "code_fingerprint_list" not in self.phase_env.keys():
            self.phase_env["code_fingerprint_list"] = []
        self.phase_env["code_fingerprint_list"].append(
            hashlib.md5(chat_env.get_codes().encode(encoding='UTF-8')).hexdigest())

    def update_chat_env(self, chat_env) -> ChatEnv:
        if "```".lower() in self.seminar_conclusion.lower():
            chat_env.update_codes(self.seminar_conclusion)
            chat_env.rewrite_codes()
            log_macnet(
                "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        self.phase_env['modification_conclusion'] = self.seminar_conclusion
        return chat_env


class CodeReviewHuman(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes()})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if "```".lower() in self.seminar_conclusion.lower():
            chat_env.update_codes(self.seminar_conclusion)
            chat_env.rewrite_codes()
            log_macnet(
                "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env

    def execute(self, chat_env, chat_turn_limit, need_reflect) -> ChatEnv:
        self.update_phase_env(chat_env)
        log_macnet(
            f"**[Human-Agent-Interaction]**\n\n"
            f"Now you can participate in the development of the software!\n"
            f"The task is:  {chat_env.env_dict['task_prompt']}\n"
            f"Please input your feedback (in one line). It can be bug report or new feature requirement.\n"
            f"You are currently in the #{self.phase_env['cycle_index'] + 1} human feedback with a total of {self.phase_env['cycle_num']} feedbacks\n"
            f"Press [Enter] to submit.\n"
            f"You can type \"End\" to quit this mode at any time.\n"
        )
        provided_comments = input(">>> ")
        self.phase_env["comments"] = provided_comments
        log_macnet(
            f"**[User Provided Comments]**\n\n In the #{self.phase_env['cycle_index'] + 1} of total {self.phase_env['cycle_num']} comments: \n\n" + provided_comments)
        if provided_comments.lower() == "end":
            return chat_env

        self.seminar_conclusion = \
            self.chatting(chat_env=chat_env,
                          task_prompt=chat_env.env_dict['task_prompt'],
                          need_reflect=need_reflect,
                          assistant_role_name=self.assistant_role_name,
                          user_role_name=self.user_role_name,
                          phase_prompt=self.phase_prompt,
                          phase_name=self.phase_name,
                          assistant_role_prompt=self.assistant_role_prompt,
                          user_role_prompt=self.user_role_prompt,
                          chat_turn_limit=chat_turn_limit,
                          placeholders=self.phase_env,
                          memory=chat_env.memory,
                          model_type=self.model_type)
        chat_env = self.update_chat_env(chat_env)
        return chat_env


class TestErrorSummary(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        chat_env.generate_images_from_codes()
        (exist_bugs_flag, test_reports) = chat_env.exist_bugs()
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                               "test_reports": test_reports,
                               "exist_bugs_flag": exist_bugs_flag})
        log_macnet("**[Test Reports]**:\n\n{}".format(test_reports))

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['error_summary'] = self.seminar_conclusion
        chat_env.env_dict['test_reports'] = self.phase_env['test_reports']

        return chat_env

    def execute(self, chat_env, chat_turn_limit, need_reflect) -> ChatEnv:
        self.update_phase_env(chat_env)
        if "ModuleNotFoundError" in self.phase_env['test_reports']:
            chat_env.fix_module_not_found_error(self.phase_env['test_reports'])
            log_macnet(
                f"Software Test Engineer found ModuleNotFoundError:\n{self.phase_env['test_reports']}\n")
            pip_install_content = ""
            for match in re.finditer(r"No module named '(\S+)'", self.phase_env['test_reports'], re.DOTALL):
                module = match.group(1)
                pip_install_content += "{}\n```{}\n{}\n```\n".format("cmd", "bash", f"pip install {module}")
                log_macnet(f"Programmer resolve ModuleNotFoundError by:\n{pip_install_content}\n")
            self.seminar_conclusion = "nothing need to do"
        else:
            self.seminar_conclusion = \
                self.chatting(chat_env=chat_env,
                              task_prompt=chat_env.env_dict['task_prompt'],
                              need_reflect=need_reflect,
                              assistant_role_name=self.assistant_role_name,
                              user_role_name=self.user_role_name,
                              phase_prompt=self.phase_prompt,
                              phase_name=self.phase_name,
                              assistant_role_prompt=self.assistant_role_prompt,
                              user_role_prompt=self.user_role_prompt,
                              chat_turn_limit=chat_turn_limit,
                              memory=chat_env.memory,
                              placeholders=self.phase_env)
        chat_env = self.update_chat_env(chat_env)
        return chat_env


class TestModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "test_reports": chat_env.env_dict['test_reports'],
                               "error_summary": chat_env.env_dict['error_summary'],
                               "codes": chat_env.get_codes()
                               })

        if "code_fingerprint_list" not in self.phase_env.keys():
            self.phase_env["code_fingerprint_list"] = []
        self.phase_env["code_fingerprint_list"].append(
            hashlib.md5(chat_env.get_codes().encode(encoding='UTF-8')).hexdigest())

    def update_chat_env(self, chat_env) -> ChatEnv:
        if "```".lower() in self.seminar_conclusion.lower():
            chat_env.update_codes(self.seminar_conclusion)
            chat_env.rewrite_codes()
            log_macnet(
                "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env


class EnvironmentDoc(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes()})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env._update_requirements(self.seminar_conclusion)
        chat_env.rewrite_requirements()
        log_macnet(
            "**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'], self.log_filepath)))
        return chat_env


class Manual(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                               "requirements": chat_env.get_requirements()})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env._update_manuals(self.seminar_conclusion)
        chat_env.rewrite_manuals()
        return chat_env
