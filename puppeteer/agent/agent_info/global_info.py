import os
import re
import logging
from agent.agent_info.workflow import Workflow
from agent.agent_info.workflow import Action


class GlobalInfo:
    def __init__(self, path_id: int, workpath: str, task: dict, logger: logging.Logger=None, env=None, env_name=None):
        self.path_id = path_id
        self.logger = logger
        self.workpath = workpath
        self.task = task
        self.workflow = Workflow(path_id=self.path_id, workpath=self.workpath)
        self.url = self._extract_url(task.get("Question"))
        self.file_name = task.get("file_name")
        self.file_extension = self._extract_file_extension(self.file_name)
        self.answers = []

        self.code_path = ""
        self.env_exists = env is not None
        self.env_name = env_name
        self.env = env
        self.supervisor = self._extract_supervisor(env, env_name)
    
    @property
    def state_answers(self):
        """Returns the list of answers in the state
        Return: list of answers
        """
        ret = []
        for index, a in enumerate(self.answers):
            ret.append("{}".format(a))
        if len(ret) == 0:
            return []
        return ret  
            
    @property
    def total_tokens(self):
        return self.workflow.total_tokens

    @property
    def total_cost(self):
        return self.workflow.total_cost
    
    def _extract_url(self, question):
        """Extracts the URL from the task question, if any."""
        url_regex = r"(https?://[^\s]+)"
        urls = re.findall(url_regex, question or "")
        return urls[0] if urls else None

    def _extract_file_extension(self, file_name):
        """Extracts the file extension from the file name."""
        if file_name:
            return os.path.splitext(file_name)[1]
        return None

    def _extract_supervisor(self, env, env_name):
        if env_name == "appworld" and env is not None:
            return env.task.supervisor
        return None

    def update(self, action: Action):
        """Updates the workflow with the given action and logs the update."""
        self.workflow.path_id = self.path_id
        self.workflow.add_action(action)
        action.write_code()
        self.workflow.write_down()
        self.logger.info(f"Updated workflow: {self.workflow}")

    def add_answer(self, answer):
        """Adds the answers to the workflow and logs the update."""
        self.answers.append(answer)
    
    def agent_role_list(self):
        return self.workflow.get_agent_role_list()
    
    def to_dict(self):
        return {
            "task": self.task,
            "url": self.url,
            "file_name": self.file_name,
            "file_extension": self.file_extension,
            "answer": self.answer,
            "workflow": self.workflow,
            "workspace_path": self.workpath,
            "env_exists": self.env_exists,
            "env_name": self.env_name,
            "supervisor": self.supervisor
        }
    