import torch
import json
from model import query_gpt
import re
from abc import ABC
from tenacity import retry, stop_after_attempt, wait_exponential

class Policy(ABC):
    def __init__(self, agent_graph, action_graph) -> None:
        super().__init__()
        self.agent_graph = agent_graph
        self.action_graph = action_graph
        self.actions_dim = agent_graph.num
    
class LearningPolicy(Policy):
    def __init__(self, agent_graph, action_graph):
        super().__init__(agent_graph, action_graph)
        self.actions_dim = agent_graph.num
        self.agent_hash_list = agent_graph.hash_nodes
        self.training = True  
        
    def train(self):
        self.training = True
        
    def eval(self):
        self.training = False
    
    def update(self):
        pass
    
    def save_model(self, path):
        raise NotImplementedError
    
    def load_model(self, path):
        raise NotImplementedError
    
    def finalize_task(self, transition, global_info):
        raise NotImplementedError
    
class LLMPolicy(Policy):
    def __init__(self, agent_graph, action_graph) -> None:
        super().__init__(agent_graph, action_graph)
        self.agent_hash_list = agent_graph.hash_nodes
        self.agent_role_list = agent_graph.role_nodes
    
    @retry(wait=wait_exponential(min=5, max=300), stop=stop_after_attempt(10))
    def forward(self, global_info, max_num:int =1) -> list:
        system_prompt_filepath = "prompts/general/agent_selection.json"
        with open(system_prompt_filepath, "r") as f:
            select_prompt = json.load(f)
        select_prompt = "\n".join(select_prompt['simple_select']).format(global_info.task.get("Question"), 
                                                                         global_info.workflow.all_actions, 
                                                                         self.agent_graph.agent_prompt, 
                                                                         max_num, 
                                                                         max_num,
                                                                         self.agent_hash_list[0])           
        response, _ = query_gpt(select_prompt)
        regex = r"\b(\w{32})\b"
        matches = re.findall(regex, response)
        if len(matches) <= 0:
            raise Exception("No agent found")
        if len(matches) > max_num:
            matches = matches[:max_num]
        elif len(matches) < max_num:
            matches += [matches[-1]]*(max_num-len(matches))
        for index, m in enumerate(matches[1:]):
            if  m is None:
                matches[index]  = matches[index-1]
        for m in matches:
            assert m in self.agent_hash_list
        return matches
    
    def forward_prior(self, global_info, max_num:int = 1) -> list:
        matches = self.forward(global_info, max_num)
        probs = [0.0] * self.actions_dim
    
        if matches:
            prob_per_agent = 1.0 
            for agent_hash in matches:
                idx = self.agent_hash_list.index(agent_hash)
                probs[idx] = prob_per_agent
        temprature = 0.1
        probs = torch.softmax(torch.tensor(probs)/temprature, dim=0,)
        return probs