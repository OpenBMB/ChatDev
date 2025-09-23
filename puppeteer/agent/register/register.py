from typing import Any
from agent.reasoning_agent import Reasoning_Agent
from utils.file_utils import iter_jsonl

class AgentRegister:
    def __init__(self):
        self.agents = {}
        self.unique_agents = {}

    def _register_agent(self, name, agent):
        if agent.hash in self.unique_agents:
            return 
        self.agents[name] = agent
        self.unique_agents[agent.hash] = agent
    
    def __call__(self, *args: Any, **kwds: Any):
        def decorator(cls):
            agent = cls(*args, **kwds)
            self._register_agent(agent.role, agent)
            return cls
        return decorator

    @property 
    def agent_config(self):
        return self._agent_personas
    
    @property
    def agent_num(self):
        return len(self.unique_agents)
    
    @property
    def agent_names(self):
        return self.agents.keys()
    
    @property
    def agent_identifiers(self):
        return self.unique_agents.keys()
    
    def get_agent_from_name(self, name):
        return self.agents.get(name)
    
    def get_agent_from_idx(self, idx):
        return self.unique_agents.get(idx) 

    def create_agent(self, name):
        agent = self.get_agent_from_name(name).reinitialize()
        if agent.hash in self.unique_agents:
            raise ValueError(f"Agent {name} with hash {agent.hash} already registered")
        self.unique_agents[agent.hash] = agent
        if agent is None:
            raise ValueError(f"Agent {name} not registered")
        return agent

    def register_all_agents(self, personas_path):
        self._agent_personas = list(iter_jsonl(personas_path))
        self._total_agent_num = len(self._agent_personas)
        for index in range(self._total_agent_num):
            self._initialize_agent(index)
    
    def reset_all_agents(self):
        for agent in self.unique_agents.values():
            agent.reset()
            
    def _initialize_agent(self, index):
        agent_role_name = self._agent_personas[index].get("name")
        agent_role_prompt = self._agent_personas[index].get("role_prompt")
        agent_model_type = self._agent_personas[index].get("model_type", None)
        agent_actions = self._agent_personas[index].get("actions", None)
        agent_policy = self._agent_personas[index].get("policy", None)
        if self._agent_personas[index].get("agent_type") == "reasoning":
            agent = Reasoning_Agent(role=agent_role_name, 
                          role_prompt=agent_role_prompt, 
                          index=index,
                          model=agent_model_type,
                          actions=agent_actions,
                          policy=agent_policy)
        self._register_agent(agent_role_name, agent)

    def __getattribute__(self, name: str) -> Any:
        return super().__getattribute__(name)


agent_global_registry = AgentRegister()