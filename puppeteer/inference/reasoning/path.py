from enum import Enum
import yaml
import uuid
from agent.register.register import agent_global_registry
from inference.graph.action_graph import ActionGraph
import os
import copy
from agent.agent_info.global_info import GlobalInfo
global_config = yaml.safe_load(open("./config/global.yaml", "r"))
class ReasoningState(Enum):
    INITIALIZED = 1
    SPLITING = 2
    ANSWERING = 3
    FINALIZING = 4
    DISCARDING = 5
    AGGREGATING = 6

class GraphReasoningPath:
    def __init__(self, start_agent, max_parallel_paths, global_logger, workspace_path, action_graph:ActionGraph, frontier=[], agent_sequence = [],  index = None, global_info:GlobalInfo=None, state = ReasoningState.INITIALIZED, env=None, env_name=None, policy=None):
        
        self.state = state
        self.index = index
        self.global_logger = global_logger
        self.workspace_path = workspace_path
        self.action_graph = action_graph
        self.frontier = frontier
        
        global_logger.create_logger('path{}_logger'.format(index), os.path.join(global_logger.folder_path, "path{}.log".format(index)), "INFO")
        self.logger = global_logger.get_logger('path{}_logger'.format(index))
        self.workflow_path = os.path.join(workspace_path, "path_{}.jsonl".format(index))
        self.workcode_path = os.path.join(workspace_path, "code_{}.py".format(index))

        self.start_agent = start_agent
        self.agent_sequence = agent_sequence
        if self.agent_sequence == []:
            self.agent_sequence.append(start_agent.unique_identifier)
        
        self.max_parallel_paths = max_parallel_paths
        self.max_step_num = global_config.get("graph").get("max_step_num")
        
        self.current_agent = start_agent
        self.next_agents = []
        
        self.env = env
        self.env_name = env_name

        self.policy = policy

        self.global_info = global_info
        self.global_info.logger = self.logger
        self.global_info.workpath = self.workspace_path
        self.global_info.path_id = self.index

        self.logger.info("{}[Reasoning Path{} Start]{}".format("-"*30,self.index, "-"*30))
        self.logger.info("Reasoning Path{}:{}".format(self.index, state))
        self.logger.info("Start agent: {}".format(start_agent.role))
        self.logger.info("Previous Agent sequence: {}".format(self.print_agent_sequence()))

    def update_global_info(self, current_action):
        self.global_info.update(current_action)
        self.logger.info("Updated global_info: {}".format(self.global_info.__dict__))

    def step(self):
        external_tools_enabled = global_config.get("external_tools_enabled")
        current_action, terminated = self.current_agent.take_action(self.global_info, external_tools_enabled, self.env, self.env_name)
        self.current_agent.deactivate()
        self.update_global_info(current_action)
        
        node_id = str(uuid.uuid4())
        self.action_graph.add_action(node_id, current_action.to_dict(), self.current_agent.role) 
        for successor in self.frontier:
            self.action_graph.add_dependency(successor, node_id)
        self.frontier = [node_id]

        # Deal with the case meeting the termination condition:
        # 1. The current agent is the terminator 
        # 2. The maximum number of steps is reached
        if terminated or len(self.agent_sequence) >= self.max_step_num:
            self.state = ReasoningState.FINALIZING
            self.last_agent = self.current_agent
            self.last_query_func = self.current_agent.query_func
            return self.state
        
        # Deal with the case where the current agent is the terminator
        next_agents_idx = self.policy.forward(self.global_info)
        self.next_agents = [agent_global_registry.get_agent_from_idx(idx) for idx in next_agents_idx]
        
        # Deal with the case where there is only one next agent
        if len(self.next_agents) == 1:
            self.current_agent = self.next_agents[0]
            self.current_agent.activate(global_info=self.global_info, initial_dialog_history=self.current_agent.initial_dialog_history)
            self.agent_sequence.append(self.current_agent.unique_identifier)
            self.state = ReasoningState.ANSWERING
            return self.state
        
        # Deal with the case where there are multiple next agents
        else:
            for agent in self.next_agents:
                agent.activate(global_info=self.global_info, initial_dialog_history=agent.initial_dialog_history)
            self.state = ReasoningState.SPLITING
            return self.state
        

    def split(self, current_path_num):
        split_reasoning_paths = []
        if current_path_num >= self.max_parallel_paths:
            self.current_agent = self.next_agents[0]
            self.agent_sequence.append(self.current_agent.unique_identifier)
            self.state = ReasoningState.ANSWERING
            return split_reasoning_paths
        
        for index, agent in enumerate(self.next_agents[1:self.max_parallel_paths-current_path_num+1]):
            agent_sequence = copy.deepcopy(self.agent_sequence)
            if self.env is not None:
                env = copy.deepcopy(self.env)
            else:
                env = None
            path_index = current_path_num + index
            reasoning_path = GraphReasoningPath(
                                    start_agent=agent, 
                                    max_parallel_paths=self.max_parallel_paths, 
                                    action_graph=self.action_graph,
                                    agent_sequence = agent_sequence,
                                    index=path_index,
                                    global_info=copy.deepcopy(self.global_info),
                                    state=ReasoningState.ANSWERING,
                                    global_logger=self.global_logger,
                                    workspace_path=self.workspace_path,
                                    env=env,
                                    frontier=self.frontier,
                                    policy=self.policy
                                    )
            reasoning_path.agent_sequence.append(agent.unique_identifier)
            reasoning_path.current_agent = agent
            reasoning_path.next_agents = []
            split_reasoning_paths.append(reasoning_path)
            print("\033[1;36mPath {} Initialized (split from path {})\033[0m".format(path_index,self.index))
        
        self.current_agent = self.next_agents[0]
        self.agent_sequence.append(self.current_agent.unique_identifier)
        self.state = ReasoningState.ANSWERING
        return split_reasoning_paths
    
    def print_agent_sequence(self):
        agent_sequence = "".join([agent.get("role") + "->" for agent in self.agent_sequence[:-1]] + [self.agent_sequence[-1].get("role")])
        return agent_sequence