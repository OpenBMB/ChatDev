import importlib
import json
import logging
import os
import shutil
import time
from datetime import datetime

from camel.agents import RolePlaying
from camel.configs import ChatGPTConfig
from camel.typing import TaskType
from chatdev.chat_env import ChatEnv, ChatEnvConfig
from chatdev.statistics import get_info
from camel.web_spider import modal_trans
from chatdev.utils import log_visualize, now


def check_bool(s):
    """
    This function checks if the input string is 'true', ignoring case.
    It returns True if the input is 'true' and False otherwise.
    Raises a TypeError if the input is not a string.
    """
    
    # Check if the input is a string; if not, raise a TypeError
    if not isinstance(s, str):
        raise TypeError(f"Expected a string, but got {type(s).__name__} instead.")
    
    # Convert the input string to lowercase using casefold and compare it to "true"
    return s.casefold() == "true"



class ChatChain:
    def __init__(self, **kwargs) -> None:
        """
        Initialize the ChatChain with various settings.

        This class manages configuration paths and user inputs needed for the chat software.

        Args (Keyword Arguments):
            config_path (str): Path to the main configuration file (ChatChainConfig.json).
            config_phase_path (str): Path to the phase configuration file (PhaseConfig.json).
            config_role_path (str): Path to the role configuration file (RoleConfig.json).
            task_prompt (str): The user input prompt for the software.
            project_name (str): The name of the project provided by the user.
            org_name (str): The organization name of the user.
            model_type (ModelType): The type of model to use (default: GPT-3.5 Turbo).
            code_path (str): Path to the code used by the software.
            use_ollama (bool): Whether to use the Ollama service (default: False).
        """

        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            setattr(
                self, key, value
            )  # Create an instance variable for each key and assign its value

        self.load_json_configs()

        # print dir of self exclusive of __ locals __ and 'self' and ''
        print(
            [
                attr
                for attr in dir(self)
                if not attr.startswith("__") and attr != "self" and attr != ""
            ]
        )

        # init chatchain config and recruits
        self.chain = self.config["chain"]
        self.recruits = self.config["recruits"]
        self.web_spider = self.config["web_spider"]

        # init default max chat turn
        self.chat_turn_limit_default = 10

        # init ChatEnv
        self.chat_env_config = ChatEnvConfig(
            clear_structure=check_bool(self.config["clear_structure"]),
            gui_design=check_bool(self.config["gui_design"]),
            git_management=check_bool(self.config["git_management"]),
            incremental_develop=check_bool(self.config["incremental_develop"]),
            background_prompt=self.config["background_prompt"],
            with_memory=check_bool(self.config["with_memory"]),
        )

        self.chat_env = ChatEnv(self.chat_env_config)

        # the user input prompt will be self-improved (if set "self_improve": "True" in ChatChainConfig.json)
        # the self-improvement is done in self.preprocess

        # init task prompt if task_prompt is not empty
        task_prompt = self.task_prompt
        self.task_prompt_raw = task_prompt
        self.task_prompt = ""

        # Initialize role prompts by joining lines for each role into a single string
        self.role_prompts = {}
        for role, lines in self.config_role.items():
            self.role_prompts[role] = "\n".join(lines)

        # Initialize logging and get the start time and log file path
        self.start_time, self.log_filepath = self.get_log_filepath()

        # Import the phase modules
        # SimplePhases are defined in PhaseConfig.json and imported from chatdev.phase
        # ComposedPhases are defined in ChatChainConfig.json and will be imported when needed
        self.phase_module = importlib.import_module("chatdev.phase")
        self.compose_phase_module = importlib.import_module("chatdev.composed_phase")

        # Prepare a dictionary to store phase instances
        self.phases = {}

        # Iterate over each phase in the configuration
        for phase_name, phase_config in self.config_phase.items():
            # Retrieve role names for the assistant and user
            assistant_role_name = phase_config["assistant_role_name"]
            user_role_name = phase_config["user_role_name"]

            # Retrieve and combine prompts for the current phase into one string
            prompts = phase_config["phase_prompt"]
            phase_prompt = "\n\n".join(
                prompts
            )  # Join prompts with two newlines to separate them

            # Dynamically get the class associated with the current phase
            phase_class = getattr(self.phase_module, phase_name)

            # Create an instance of the phase class with the appropriate parameters
            phase_instance = phase_class(
                assistant_role_name=assistant_role_name,
                user_role_name=user_role_name,
                phase_prompt=phase_prompt,
                role_prompts=self.role_prompts,
                phase_name=phase_name,
                model_type=self.model_type,
                log_filepath=self.log_filepath,
            )

            # Store the phase instance in the phases dictionary
            self.phases[phase_name] = phase_instance

    def load_json_configs(self):
        """
        Load JSON data from files into instance variables.
        Finds attributes that start with 'config_' and end with '_path'.
        """
        print("Loading JSON configuration files...")
        for attr in dir(self):
            if attr.startswith("config_") and attr.endswith("_path"):
                print(f"Loading {attr}...")
                # Remove '_path' from the attribute name and strip trailing underscore if present
                config_attr = attr.replace("_path", "").rstrip("_")

                # Load the JSON data from the file and set it to the instance variable
                with open(getattr(self, attr), "r", encoding="utf8") as file:
                    print(f"Setting {config_attr}...")
                    setattr(
                        self, config_attr, json.load(file)
                    )  # Store JSON data in the instance variable

    def recruit_team(self):
        """
        Recruit all employees listed in 'self.recruits' into the chat environment.

        This method recruits each employee in the 'self.recruits' list by calling
        the 'recruit' method on the 'chat_env' to add them to the chat environment.

        Returns:
            None
        """
        # Loop through each employee in the recruits list
        for employee in self.recruits:
            # Recruit the employee into the chat environment
            self.chat_env.recruit(agent_name=employee)

    def execute_step(self, phase_item: dict):
        """
        Execute a single phase in the chain.

        Args:
            phase_item: A dictionary containing the configuration for one phase 
                        from the ChatChainConfig.json file.

        Returns:
            None
        """

        # Extract the phase name and type from the phase_item dictionary
        phase = phase_item["phase"]
        phase_type = phase_item["phaseType"]

        # Handle SimplePhase execution
        if phase_type == "SimplePhase":
            self._execute_phase(
                phase, 
                phase_item["max_turn_step"], 
                check_bool(phase_item["need_reflect"])
            )
        
        # Handle ComposedPhase execution
        elif phase_type == "ComposedPhase":
            self._execute_composed_phase(
                phase, 
                phase_item["cycleNum"], 
                phase_item["Composition"]
            )
        
        # If the phase type is not recognized, raise an error
        else:
            self._raise_not_implemented_error(f"PhaseType '{phase_type}'")

    def _execute_phase(self, phase, max_turn_step, need_reflect):
        """
        Execute a SimplePhase using the provided parameters.

        Args:
            phase: The name of the phase to execute.
            max_turn_step: The maximum number of turns for this phase.
            need_reflect: A boolean indicating whether reflection is needed.

        Returns:
            None
        """
        if phase in self.phases:
            self.chat_env = self.phases[phase].execute(
                self.chat_env,
                self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step,
                need_reflect,
            )
        else:
            self._raise_not_implemented_error(f"Phase '{phase}' in chatdev.phase")

    def _execute_composed_phase(self, phase, cycle_num, composition):
        """
        Execute a ComposedPhase using the provided parameters.

        Args:
            phase: The name of the composed phase to execute.
            cycle_num: The number of cycles for the composed phase.
            composition: The composition details for the composed phase.

        Returns:
            None
        """
        compose_phase_class = getattr(self.compose_phase_module, phase, None)
        if not compose_phase_class:
            self._raise_not_implemented_error(f"Phase '{phase}' in chatdev.compose_phase")

        compose_phase_instance = compose_phase_class(
            phase_name=phase,
            cycle_num=cycle_num,
            composition=composition,
            config_phase=self.config_phase,
            config_role=self.config_role,
            model_type=self.model_type,
            log_filepath=self.log_filepath,
        )
        self.chat_env = compose_phase_instance.execute(self.chat_env)

    def _raise_not_implemented_error(self, message):
        """
        Raise a RuntimeError indicating a phase or phase type is not implemented.

        Args:
            message: The error message to include in the RuntimeError.

        Returns:
            None
        """
        raise RuntimeError(message)


    def execute_chain(self):
        """
        Execute the entire chain based on the 
        configuration specified in ChatChainConfig.json.

        This method applies the 'execute_step' function to each item
        in the 'self.chain' list using the 'map()' function.

        The 'list()' function is used to ensure that all steps are executed immediately.
        """
        list(map(self.execute_step, self.chain))

    def get_log_filepath(self):
        """
        Get the log file path under the software's main directory.

        Returns:
            start_time (str): The time when the software started, formatted as 'YYYYMMDDHHMMSS'.
            log_filepath (str): The full path to the log file.
        """
        # Capture the current time as a formatted string (e.g., '20230811142300')
        start_time = now()

        # Get the directory of the current file and move up one level to the root directory
        root = os.path.dirname(os.path.dirname(__file__))

        # Define the path to the 'WareHouse' directory within the root directory
        directory = os.path.join(root, "WareHouse")

        # Create the full path to the log file using the project name, organization name, and start time
        log_filepath = os.path.join(
            directory, f"{self.project_name}_{self.org_name}_{start_time}.log"
        )

        return start_time, log_filepath

    def pre_processing(self):
        """
        Preprocess the environment by removing unnecessary files,
        setting up directories, and copying configuration files.
        Returns: None
        """
        # Get the root directory of the software
        root = os.path.dirname(os.path.dirname(__file__))
        directory = os.path.join(root, "WareHouse")

        # Clear out unnecessary files from the WareHouse directory
        if self.chat_env.config.clear_structure:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path) and not filename.endswith((".py", ".log")):
                    os.remove(file_path)
                    print(f"{file_path} Removed.")

        # Set up the directory for storing software-related files
        software_path = os.path.join(
            directory, f"{self.project_name}_{self.org_name}_{self.start_time}"
        )
        self.chat_env.set_directory(software_path)

        # Initialize memory if the configuration requires it
        if self.chat_env.config.with_memory:
            self.chat_env.init_memory()

        # Copy essential configuration files to the software directory
        for config_file in [
            self.config_path,
            self.config_phase_path,
            self.config_role_path,
        ]:
            shutil.copy(config_file, software_path)

        # If incremental development is enabled, copy code files to the software directory
        if check_bool(self.config["incremental_develop"]):
            for root_dir, dirs, files in os.walk(self.code_path):
                relative_path = os.path.relpath(root_dir, self.code_path)
                target_dir = os.path.join(software_path, "base", relative_path)
                os.makedirs(target_dir, exist_ok=True)
                for file in files:
                    shutil.copy2(
                        os.path.join(root_dir, file), os.path.join(target_dir, file)
                    )
            self.chat_env._load_from_hardware(os.path.join(software_path, "base"))

        # Write the task prompt to a file in the software directory
        with open(os.path.join(software_path, f"{self.project_name}.prompt"), "w") as f:
            f.write(self.task_prompt_raw)

        # Prepare a message summarizing the preprocessing steps and log it
        preprocess_msg = f"""
        **[Preprocessing]**

        **Startr.Team Starts** ({self.start_time})

        **Timestamp**: {self.start_time}

        **config_path**: {self.config_path}

        **config_phase_path**: {self.config_phase_path}

        **config_role_path**: {self.config_role_path}

        **task_prompt**: {self.task_prompt_raw}

        **project_name**: {self.project_name}

        **Log File**: {self.log_filepath}

        **Startr.Team Config**:
        {self.chat_env.config}

        **ChatGPTConfig**:
        {ChatGPTConfig()}
        """
        # clean preprocess_msg of preceding whitespace
        preprocess_msg = "\n".join(
            [line.strip() for line in preprocess_msg.split("\n")]
        )

        log_visualize(preprocess_msg)

        # Initialize task prompt based on configuration settings
        self.chat_env.env_dict["task_prompt"] = (
            self.self_task_improve(self.task_prompt_raw)
            if check_bool(self.config["self_improve"])
            else self.task_prompt_raw
        )

        # If web spidering is enabled, convert the task prompt for web interaction
        if check_bool(self.web_spider):
            self.chat_env.env_dict["task_description"] = modal_trans(
                self.task_prompt_raw
            )

    def post_processing(self):
        """
        summarize the production and move log files to the software directory
        Returns: None

        """

        self.chat_env.write_meta()
        filepath = os.path.dirname(__file__)
        root = os.path.dirname(filepath)

        if self.chat_env_config.git_management:
            log_git_info = "**[Git Information]**\n\n"

            self.chat_env.codes.version += 1
            os.system("cd {}; git add .".format(self.chat_env.env_dict["directory"]))
            log_git_info += "cd {}; git add .\n".format(
                self.chat_env.env_dict["directory"]
            )
            os.system(
                'cd {}; git commit -m "v{} Final Version"'.format(
                    self.chat_env.env_dict["directory"], self.chat_env.codes.version
                )
            )
            log_git_info += 'cd {}; git commit -m "v{} Final Version"\n'.format(
                self.chat_env.env_dict["directory"], self.chat_env.codes.version
            )
            log_visualize(log_git_info)

            git_info = "**[Git Log]**\n\n"
            import subprocess

            # execute git log
            command = "cd {}; git log".format(self.chat_env.env_dict["directory"])
            completed_process = subprocess.run(
                command, shell=True, text=True, stdout=subprocess.PIPE
            )

            if completed_process.returncode == 0:
                log_output = completed_process.stdout
            else:
                log_output = "Error when executing " + command

            git_info += log_output
            log_visualize(git_info)

        post_info = "**[Post Info]**\n\n"
        now_time = now()
        time_format = "%Y%m%d%H%M%S"
        datetime1 = datetime.strptime(self.start_time, time_format)
        datetime2 = datetime.strptime(now_time, time_format)
        duration = (datetime2 - datetime1).total_seconds()

        post_info += "Software Info: {}".format(
            get_info(self.chat_env.env_dict["directory"], self.log_filepath)
            + "\n\n🕑**duration**={:.2f}s\n\n".format(duration)
        )

        post_info += "Startr.Team Starts ({})".format(self.start_time) + "\n\n"
        post_info += "Startr.Team Ends ({})".format(now_time) + "\n\n"

        directory = self.chat_env.env_dict["directory"]
        if self.chat_env.config.clear_structure:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isdir(file_path) and file_path.endswith("__pycache__"):
                    shutil.rmtree(file_path, ignore_errors=True)
                    post_info += "{} Removed.".format(file_path) + "\n\n"

        log_visualize(post_info)

        logging.shutdown()
        time.sleep(1)

        shutil.move(
            self.log_filepath,
            os.path.join(
                root + "/WareHouse",
                "_".join([self.project_name, self.org_name, self.start_time]),
                os.path.basename(self.log_filepath),
            ),
        )

    # @staticmethod
    def self_task_improve(self, task_prompt):
        """
        ask agent to improve the user query prompt
        Args:
            task_prompt: original user query prompt

        Returns:
            revised_task_prompt: revised prompt from the prompt engineer agent

        """
        self_task_improve_prompt = """I will give you a short description of a software design requirement, 
please rewrite it into a detailed prompt that can make large language model know how to make this software better based this prompt,
the prompt should ensure LLMs build a software that can be run correctly, which is the most import part you need to consider.
remember that the revised prompt should not contain more than 200 words, 
here is the short description:\"{}\". 
If the revised prompt is revised_version_of_the_description, 
then you should return a message in a format like \"<INFO> revised_version_of_the_description\", do not return messages in other formats.""".format(
            task_prompt
        )

        role_play_session = RolePlaying(
            assistant_role_name="Prompt Engineer",
            assistant_role_prompt="You are an professional prompt engineer that can improve user input prompt to make LLM better understand these prompts.",
            user_role_prompt="You are an user that want to use LLM to build software.",
            user_role_name="User",
            task_type=TaskType.STARTR_TEAM,
            task_prompt="Do prompt engineering on user query",
            with_task_specify=False,
            model_type=self.model_type,
        )

        # log_visualize("System", role_play_session.assistant_sys_msg)
        # log_visualize("System", role_play_session.user_sys_msg)

        _, input_user_msg = role_play_session.init_chat(
            None, None, self_task_improve_prompt
        )
        assistant_response, user_response = role_play_session.step(input_user_msg, True)
        revised_task_prompt = (
            assistant_response.msg.content.split("<INFO>")[-1].lower().strip()
        )
        log_visualize(
            role_play_session.assistant_agent.role_name, assistant_response.msg.content
        )
        log_visualize(
            "**[Task Prompt Self Improvement]**\n**Original Task Prompt**: {}\n**Improved Task Prompt**: {}".format(
                task_prompt, revised_task_prompt
            )
        )
        return revised_task_prompt
