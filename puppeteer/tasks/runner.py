from agent.register.register import agent_global_registry
from inference.reasoning.reasoning import GraphReasoning
from inference.graph.agent_graph import AgentGraph

class BenchmarkRunner:
    def __init__(self, personas_path, global_config):
        self.personas_path = personas_path
        self.global_config = global_config
        self.max_step_num = self.global_config.get('graph').get('max_step_num')
        self.save_state = False

    def setup_reasoning(self, data_item):
        agent_global_registry.register_all_agents(self.personas_path)
        agent_global_registry.reset_all_agents()
        graph = AgentGraph()
        return GraphReasoning(data_item, graph), graph

    def run_reasoning(self, data_item):
        reasoning, _ = self.setup_reasoning(data_item)
        reasoning.start(self.save_state if self.save_state else None)
        self.save_state = False
        
        final_ans, _ = reasoning.n_step(self.max_step_num)

        reasoning.visualize_path()
        reasoning.visualize_graph()

        return final_ans