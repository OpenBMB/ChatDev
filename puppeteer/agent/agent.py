import json
import yaml
import hashlib
import re
import time
from utils.other_utils import JsonFormat
from copy import deepcopy
from abc import ABC, abstractmethod
from model.query_manager import query_manager
from agent.agent_info.global_info import GlobalInfo

global_config = yaml.safe_load(open("./config/global.yaml", "r"))

class Agent(ABC):
    def __init__(self, role, role_prompt, index, model="gpt",  actions=[], policy=None, global_info:GlobalInfo =None, initial_dialog_history=None) -> None:
        """
        Initialize the Agent object.
        :param role: The name of the agent's role
        :param role_prompt: The role prompt information
        :param index: The index to distinguish different agent instances
        :param global_info: Global configuration info, default is None
        :param model: The model to be used (either 'gpt' or 'gpt4'), default is 'gpt'
        :param actions: List of actions available to the agent, default is empty
        :param initial_dialog_history: Initial dialog history, default is None
        """
        super().__init__()

        # Initialize model query function
        self.model = model
        self.query_func = None
        self.query_func = self._get_query_function()
        
        if not self.query_func:
            raise ValueError(f"Model '{model}' not implemented")
        
        # Other basic settings
        self.json_format = JsonFormat(query_func=self.query_func)
        self.role = role
        self.role_prompt = role_prompt
        self.system_prompt = self.role_prompt  # Initial system prompt
        self.policy = policy
        self.index = index
        self.hash = hashlib.md5(f"{index}{role}{role_prompt}{model}{time.ctime()}".encode()).hexdigest()

        # Tools and file path settings
        self.actions = actions
        self.root_file_path = global_config["file_path"]["root_file_path"]
        if global_info:
            self.workspace_path = global_info.workpath
        
        # Activation state and dialog history
        self._activated = False
        self.initial_dialog_history = initial_dialog_history or []
        self.dialog_history = deepcopy(self.initial_dialog_history)
    
    @property
    def simplified_dialog_history(self):
        self._simplified_dialog_history = []
        for h in self.dialog_history:
            if h.get("role") == "user":
                # Mask user input 
                # "*Your previous reasoning was {}*”
                masked_text = re.sub(r'\*.*?\*', '', h["content"])
                self._simplified_dialog_history.append({"role": h["role"], "content": masked_text})
            else:
                self._simplified_dialog_history.append(h)
        return self._simplified_dialog_history

    @property
    def unique_identifier(self):
        """Return a unique identifier for the Agent instance."""
        return {
            "index": self.index,
            "role": self.role,
            "hash": self.hash
        }
    def _get_query_function(self):
        def query_func(messages, system_prompt=None):
            return query_manager.query(self.model, messages, system_prompt)
        return query_func
    
    @abstractmethod
    def activate(self, global_info, initial_dialog_history=None):
        """Activate the agent, enabling it to perform actions."""
        pass

    @abstractmethod
    def deactivate(self):
        """Deactivate the agent."""
        self._activated = False

    def reset(self):
        """Reset the agent's state, clearing dialog history and deactivating it."""
        self.dialog_history = []
        self.initial_dialog_history = []
        self.deactivate()


    @abstractmethod
    def _build_current_action(self, format_action, flag, answer, step_data):
        """Build the current workflow guiding the agent's actions."""
        pass

    @abstractmethod
    def take_action(self, global_info, external_tools_enabled=True):
        """Let the agent take an action based on the current state."""
        pass
    
    @abstractmethod
    def _execute_action(self, action, global_info):
        """Execute a specific action."""
        pass
    
    @abstractmethod
    def _reasoning_operation(self, action, global_info) -> str:
        """Perform a reasoning operation."""
        pass

    @abstractmethod
    def _answer_operation(self, global_info) -> str:
        """Generate an answer based on the current state."""
        pass

    @abstractmethod
    def _tool_operation(self, action: json, global_info) -> str:
        """Perform an operation involving external tools."""
        pass

    @abstractmethod
    def _interaction_operation(self, code, env, global_info) -> str:
        """Handle operations related to agent interaction."""
        pass
