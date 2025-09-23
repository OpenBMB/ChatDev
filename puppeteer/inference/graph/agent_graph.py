import networkx as nx
from pyvis.network import Network
import seaborn as sns
import yaml
from inference.base.graph import Graph
from agent.register.register import agent_global_registry
import logging
main_logger = logging.getLogger('global') 

class AgentGraph(Graph):
    def __init__(self):
        super().__init__()     
        self._nodes_num = agent_global_registry.agent_num
        self._edges_num = 0
        for agent in agent_global_registry.unique_agents.values():
            self._add_node(agent)
        print("-"*10+"\033[31mAgent Graph Initialized\033[0m"+"-"*10)

    @property
    def hash_nodes(self):
        return [node.hash for node in self._nodes]
    
    @property
    def role_nodes(self):
        return [node.role for node in self._nodes]
    
    def get_agent_from_index(self, index):
        return self._nodes[index]
    
    def get_agent_from_role(self, role):
        for agent in self._nodes:
            if agent.role == role:
                return agent
        return None
    
    def get_agent_from_hash(self, hash):
        for agent in self._nodes:
            if agent.hash == hash:
                return agent
        return None
    
    def get_agent_dialog_history(self, agent_role_list: list, **kwargs):
        """get agent dialog history
        
        Keyword arguments:
        idx -- agent idx
        Return: corresponding agent dialog history. If idx is illegal, return []
        """
        question = kwargs.get("question", None)
        history = []
        for role in agent_role_list:
            agent = self.get_agent_from_role(role)
            for h in agent.simplified_dialog_history:
                history.append(h)
        if len(agent_role_list) == 0 and question is not None:
            history = [{'role': 'system', 'content': 'You are an assistant. Your task is to {}'.format(question)}]
        assert len(history)!=0, "Dialog history can not be empty"
        return history    
    
    @property
    def agent_prompt(self):
        agent_prompt = []
        for agent in self._nodes:
            if agent.role != "TerminatorAgent":
                agent_prompt.append(f"Agent {agent.role} using model {agent.model}' hash: {agent.hash}")
        agent_prompt = "\n".join(agent_prompt)
        return agent_prompt
    
    @property
    def terminator_agent_index(self):
        for agent in self._nodes:
            if agent.role == "TerminatorAgent":
                return agent.index
        return None
    
    @property
    def search_agent_indices(self):
        indices = []
        for agent in self._nodes:
            if agent.role == "WebsiteAgent" or agent.role == "BingAgent" or agent.role == "ArxivAgent":
                indices.append(agent.index)
        return indices
    
    def agent_list(self):
        agent_info_list = [
            f"index:{agent.index}, role:{agent.role}, model:{agent.model}, hash:{agent.hash}, tool:{agent.tools}"
            for agent in self._nodes
        ]
        return '\n'.join(agent_info_list)
    
    def visualize(self, path="agent_graph.html"):
        def generate_color_map(node_ids):
            color_palette = sns.color_palette("husl", len(node_ids)).as_hex()
            color_map = {node_id: color_palette[i % len(color_palette)] for i, node_id in enumerate(node_ids)}
            return color_map
        node_color_map = generate_color_map(self.hash_nodes)
        edge_color_map = generate_color_map([edge.index for edge in self._edges])
        
        G = nx.MultiDiGraph()
        edge_labels = {}
        for node in self._nodes:
            G.add_node(node.index, label=f"{node.role}\nbase model: {node.model}\nindex: {node.index}",color = node_color_map[node.hash])
        
        for edge in self._edges:
            G.add_edge(edge.v.index, edge.u.index, color = edge_color_map[edge.index])
            edge_labels[(edge.v.index, edge.u.index)] = f"Reasoning..."
        
        net = Network(notebook=True, height="750px", width="100%", bgcolor="#FFFFFF", font_color="black", directed=True)
        net.from_nx(G)
        net.show(path)
    
    @property
    def num(self):
        return self._nodes_num
    
    def add_agent(self):
        pass
    def delete_agent(self):
        pass