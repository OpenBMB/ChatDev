import os
import json
import networkx as nx
import matplotlib.pyplot as plt
from agent.agent_info.actions import REASONING_ACTION_LIST, TOOL_ACTION_LIST, TERMINATION_ACTION_LIST
from model.model_config import model_registry

class Action:
    def __init__(self, action:dict, result:dict, success:str, agent_role:str, agent_model:str):
        self.action = action  # format action, e.g., {"action": "", "parameters": ""}
        self.result = result  # action result, e.g., {"step_data": "", "answer": ""}
        self.success = success  # Success or Failure of the action
        self.agent_role = agent_role  # Role of the agent
        self.agent_model = agent_model  # Model of the agent
        self.model_parameter = model_registry.get_model_size(agent_model) if model_registry.get_model_size(agent_model) else 0
        self.cost = 0
        self.tokens = 0

    def to_dict(self):
        return {
            "agent": self.agent_role,
            "action": self.action,
            "cost": self.cost,
            "tokens": self.tokens,
            "model_size": self.model_parameter,
            "result": self.result,
            "success": self.success
        }
    
    def to_str(self):
        return "Agent: {}\nAction: {}\nResult: {}\nSuccess: {}".format(self.agent_role, self.action, self.result, self.success)
    
    def set_workpath(self, workpath:str):
        self.workpath = workpath

    def write_code(self):
        if self.result.get("code") is None:
            return 
        else:
            path = os.path.join(self.workpath, "code_{}.py".format(self.path_id))
            with open(path, 'w', encoding='utf-8') as file:
                json.dump(self.workflow, file, ensure_ascii=False, indent=4)
            file.close()

    def set_cost(self, tokens:int):
        self.cost = 2 * self.model_parameter * tokens
        self.tokens = tokens
        print("[Action Cost]: {}".format(self.cost))

class Workflow:
    def __init__(self, path_id:int, workpath:str):
        self.path_id: int = path_id
        self.workpath: str = workpath
        self.workflow: list = []
    
    @property
    def total_cost(self):
        cost = 0
        for a in self.workflow:
            cost += a.cost
        return cost

    @property
    def total_tokens(self):
        tokens = 0
        for a in self.workflow:
            tokens += a.tokens
        return tokens
    
    def to_dict(self):
        return [action.to_dict() for action in self.workflow]
    
    def write_down(self):
        path = os.path.join(self.workpath, "path_{}.jsonl".format(self.path_id))
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(self.to_dict(), file, ensure_ascii=False, indent=4)
        file.close()
    
    def add_action(self, action:Action):
        action.set_workpath(self.workpath)
        self.workflow.append(action)
    
    def get_agent_role_list(self):
        agent_role_list = []
        for action in self.workflow:
            role = action.agent_role
            agent_role_list.append(role)
        return agent_role_list

    @property
    def language_state(self):
        state = []
        for index, action in enumerate(self.workflow):
            step_str = "{}({}) - {} - {}".format(
                action.action.get("action"),
                action.action.get("parameter"),
                action.result.get("step_data"),
                action.result.get("answer")
            )
            state.append(step_str)
        if len(state) == 0:
            return "None"
        return "\n".join(state)
    
    @property
    def state(self):
        state = []
        for action in self.workflow:
            flag = 1 if action.success == "Success" else 0  
            state.append((action.agent_role, action.action.get("action"), flag))
        if len(state) == 0:
            return tuple([(None, None, -1)])
        return tuple(state)
    
    @property
    def valid_code(self):
        data = []
        for action in self.workflow:
            if action.success == "Success":
                data.append(action.result.get("code"))
        return data
    @property
    def all_actions(self):
        data = []
        for action in self.workflow:
            data.append(action.action.get("action"))
        return data
    
    @property
    def valid_actions(self):
        data = []
        for action in self.workflow:
            if action.success == "Success":
                data.append(action.action.get("action"))
        return data
    
    @property
    def valid_results(self):
        data = []
        for action in self.workflow:
            if action.success == "Success":
                data.append("Result: {}".format(action.result.get("step_data")))
        return data
    
    @property
    def valid_reasoning_results(self):
        data = []
        for action in self.workflow:
            if action.action.get("action") in REASONING_ACTION_LIST and action.success == "Success":
                data.append("Successful Action: {}\nResult: {}".format(action.action.get("action"), action.result.get("step_data")))

        return data

    @property
    def valid_tool_results(self):
        data = []
        for action in self.workflow:
            if action.action.get("action") not in REASONING_ACTION_LIST and action.success == "Success":
                data.append("Successful Action: {}\nResult: {}".format(action.action.get("action"), action.result.get("step_data")))

        return data
    
    @property
    def unvalid_tool_results(self):
        data = []
        for action in self.workflow:
            if action.action.get("action") not in REASONING_ACTION_LIST and action.success == "Failure":
                data.append("Successful Action: {}\nResult: {}".format(action.action.get("action"), action.result.get("step_data")))

        return data
    

    def visualize(self):
        G = nx.MultiDiGraph()
        node_colors = []
        for i, w in enumerate(self.workflow):
            G.add_node(i, label=w.action.get("action"), result=w.result, status=w.success)
            node_colors.append("green" if w.success == "Success" else "red")
            if i > 0:
                G.add_edge(i-1, i)
        pos = nx.kamada_kawai_layout(G)
        labels = nx.get_node_attributes(G, 'label')
        nx.draw(G, pos, with_labels=True, labels=labels, node_size=3000, font_size=10, arrows=True, node_color=node_colors)
        
        path = os.path.join(self.workpath, "workflow_path_{}.png".format(self.path_id))
        plt.savefig(path)
        plt.clf()