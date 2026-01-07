"""Register built-in workflow node types."""

from entity.configs.node.agent import AgentConfig
from entity.configs.node.human import HumanConfig
from entity.configs.node.subgraph import (
    SubgraphConfig,
    SubgraphFileConfig,
    SubgraphInlineConfig,
    register_subgraph_source,
)
from entity.configs.node.passthrough import PassthroughConfig
from entity.configs.node.literal import LiteralNodeConfig
from entity.configs.node.python_runner import PythonRunnerConfig
from entity.configs.node.loop_counter import LoopCounterConfig
from runtime.node.executor.agent_executor import AgentNodeExecutor
from runtime.node.executor.human_executor import HumanNodeExecutor
from runtime.node.executor.passthrough_executor import PassthroughNodeExecutor
from runtime.node.executor.literal_executor import LiteralNodeExecutor
from runtime.node.executor.python_executor import PythonNodeExecutor
from runtime.node.executor.subgraph_executor import SubgraphNodeExecutor
from runtime.node.executor.loop_counter_executor import LoopCounterNodeExecutor
from runtime.node.registry import NodeCapabilities, register_node_type


register_node_type(
    "agent",
    config_cls=AgentConfig,
    executor_cls=AgentNodeExecutor,
    capabilities=NodeCapabilities(
        default_role_field="role",
        exposes_tools=True,
    ),
    summary="Agent execution node backed by configured LLM/tool providers with support for tooling, memory, and thinking extensions.",
)

register_node_type(
    "human",
    config_cls=HumanConfig,
    executor_cls=HumanNodeExecutor,
    capabilities=NodeCapabilities(
        resource_key="node_type:human",
        resource_limit=1,
    ),
    summary="Pauses graph and waits for human operator response",
)

register_node_type(
    "subgraph",
    config_cls=SubgraphConfig,
    executor_cls=SubgraphNodeExecutor,
    capabilities=NodeCapabilities(
    ),
    executor_factory=lambda context, subgraphs=None: SubgraphNodeExecutor(context, subgraphs or {}),
    summary="Embeds (through file path or inline config) and runs another named subgraph within the current workflow",
)

register_node_type(
    "python",
    config_cls=PythonRunnerConfig,
    executor_cls=PythonNodeExecutor,
    capabilities=NodeCapabilities(
        resource_key="node_type:python",
        resource_limit=1,
    ),
    summary="Executes repository Python snippets",
)

register_node_type(
    "passthrough",
    config_cls=PassthroughConfig,
    executor_cls=PassthroughNodeExecutor,
    capabilities=NodeCapabilities(
    ),
    summary="Forwards prior node output downstream without modification",
)

register_node_type(
    "literal",
    config_cls=LiteralNodeConfig,
    executor_cls=LiteralNodeExecutor,
    capabilities=NodeCapabilities(
    ),
    summary="Emits the configured text message every time it is triggered",
)

register_node_type(
    "loop_counter",
    config_cls=LoopCounterConfig,
    executor_cls=LoopCounterNodeExecutor,
    capabilities=NodeCapabilities(),
    summary="Blocks downstream edges until the configured iteration limit is reached, then emits a message to release the loop.",
)

# Register subgraph source types (file-based and inline config)
register_subgraph_source(
    "config",
    config_cls=SubgraphInlineConfig,
    description="Inline subgraph definition embedded directly in the YAML graph",
)
register_subgraph_source(
    "file",
    config_cls=SubgraphFileConfig,
    description="Reference an external YAML file containing the subgraph",
)
