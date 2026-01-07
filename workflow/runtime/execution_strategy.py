"""Execution strategies for different graph topologies."""

from collections import Counter
from typing import Callable, Dict, List, Sequence

from entity.configs import Node
from entity.messages import Message
from utils.log_manager import LogManager
from workflow.executor.dag_executor import DAGExecutor
from workflow.executor.cycle_executor import CycleExecutor
from workflow.executor.parallel_executor import ParallelExecutor


class DagExecutionStrategy:
    """Executes acyclic graphs using the DAGExecutor."""

    def __init__(
        self,
        log_manager: LogManager,
        nodes: Dict[str, Node],
        layers: List[List[str]],
        execute_node_func: Callable[[Node], None],
    ) -> None:
        self.log_manager = log_manager
        self.nodes = nodes
        self.layers = layers
        self.execute_node_func = execute_node_func

    def run(self) -> None:
        dag_executor = DAGExecutor(
            log_manager=self.log_manager,
            nodes=self.nodes,
            layers=self.layers,
            execute_node_func=self.execute_node_func,
        )
        dag_executor.execute()


class CycleExecutionStrategy:
    """Executes graphs containing cycles via CycleExecutor."""

    def __init__(
        self,
        log_manager: LogManager,
        nodes: Dict[str, Node],
        cycle_execution_order: List[Dict[str, str]],
        cycle_manager,
        execute_node_func: Callable[[Node], None],
    ) -> None:
        self.log_manager = log_manager
        self.nodes = nodes
        self.cycle_execution_order = cycle_execution_order
        self.cycle_manager = cycle_manager
        self.execute_node_func = execute_node_func

    def run(self) -> None:
        cycle_executor = CycleExecutor(
            log_manager=self.log_manager,
            nodes=self.nodes,
            cycle_execution_order=self.cycle_execution_order,
            cycle_manager=self.cycle_manager,
            execute_node_func=self.execute_node_func,
        )
        cycle_executor.execute()


class MajorityVoteStrategy:
    """Executes graphs configured for majority voting (no edges)."""

    def __init__(
        self,
        log_manager: LogManager,
        nodes: Dict[str, Node],
        initial_messages: Sequence[Message],
        execute_node_func: Callable[[Node], None],
        payload_to_text_func: Callable[[object], str],
    ) -> None:
        self.log_manager = log_manager
        self.nodes = nodes
        self.initial_messages = initial_messages
        self.execute_node_func = execute_node_func
        self.payload_to_text = payload_to_text_func

    def run(self) -> str:
        self.log_manager.info("Executing graph with majority voting approach")
        all_nodes = list(self.nodes.values())
        if not all_nodes:
            self.log_manager.error("No nodes to execute in majority voting mode")
            return ""

        for node in all_nodes:
            node.clear_input()
            for message in self.initial_messages:
                node.append_input(message.clone())

        node_ids = [node.id for node in all_nodes]

        def _execute(node_id: str) -> None:
            self.execute_node_func(self.nodes[node_id])

        parallel_executor = ParallelExecutor(self.log_manager, self.nodes)
        parallel_executor.execute_nodes_parallel(node_ids, _execute)

        return self._collect_majority_result()

    def _collect_majority_result(self) -> str:
        node_outputs: List[Dict[str, str]] = []
        for node_id, node in self.nodes.items():
            if node.output:
                output_text = self.payload_to_text(node.output[-1])
            else:
                output_text = ""
            node_outputs.append(
                {
                    "node_id": node_id,
                    "node_type": node.node_type,
                    "output": output_text,
                }
            )

        output_values = [item["output"] for item in node_outputs]
        output_counts = Counter(output_values)

        non_empty_outputs = [value for value in output_values if value.strip()]
        if non_empty_outputs:
            output_counts = Counter(non_empty_outputs)

        if not output_counts:
            self.log_manager.warning("No outputs available for majority voting")
            return ""

        majority_output, count = output_counts.most_common(1)[0]
        self.log_manager.info(
            "Majority output determined",
            details={"result": majority_output, "votes": count},
        )
        self.log_manager.info(
            "All node outputs",
            details={
                "outputs": [
                    (
                        item["node_id"],
                        item["output"][:50] + "..." if len(item["output"]) > 50 else item["output"],
                    )
                    for item in node_outputs
                ]
            },
        )
        return majority_output
