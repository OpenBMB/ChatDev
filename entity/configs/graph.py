"""Graph-level configuration dataclasses."""

from dataclasses import dataclass, field
from collections import Counter
from typing import Any, Dict, List, Mapping

from entity.enums import LogLevel
from entity.enum_options import enum_options_for

from .base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    ensure_list,
    optional_bool,
    optional_dict,
    optional_str,
    require_mapping,
    extend_path,
)
from .edge import EdgeConfig
from entity.configs.node.memory import MemoryStoreConfig
from entity.configs.node.agent import AgentConfig
from entity.configs.node.node import Node


@dataclass
class GraphDefinition(BaseConfig):
    id: str | None
    description: str | None
    log_level: LogLevel
    is_majority_voting: bool
    nodes: List[Node] = field(default_factory=list)
    edges: List[EdgeConfig] = field(default_factory=list)
    memory: List[MemoryStoreConfig] | None = None
    organization: str | None = None
    initial_instruction: str | None = None
    start_nodes: List[str] = field(default_factory=list)
    end_nodes: List[str] | None = None

    FIELD_SPECS = {
        "id": ConfigFieldSpec(
            name="id",
            display_name="Graph ID",
            type_hint="str",
            required=True,
            description="Graph identifier for referencing. Can only contain alphanumeric characters, underscores or hyphens, no spaces",
        ),
        "description": ConfigFieldSpec(
            name="description",
            display_name="Graph Description",
            type_hint="text",
            required=False,
            description="Human-readable narrative shown in UI/templates that explains the workflow goal, scope, and manual touchpoints.",
        ),
        "log_level": ConfigFieldSpec(
            name="log_level",
            display_name="Log Level",
            type_hint="enum:LogLevel",
            required=False,
            default=LogLevel.DEBUG.value,
            enum=[lvl.value for lvl in LogLevel],
            description="Runtime log level",
            advance=True,
            enum_options=enum_options_for(LogLevel),
        ),
        "is_majority_voting": ConfigFieldSpec(
            name="is_majority_voting",
            display_name="Majority Voting Mode",
            type_hint="bool",
            required=False,
            default=False,
            description="Whether this is a majority voting graph",
            advance=True,
        ),
        "nodes": ConfigFieldSpec(
            name="nodes",
            display_name="Node List",
            type_hint="list[Node]",
            required=False,
            description="Node list, must contain at least one node",
            child=Node,
        ),
        "edges": ConfigFieldSpec(
            name="edges",
            display_name="Edge List",
            type_hint="list[EdgeConfig]",
            required=False,
            description="Directed edges between nodes",
            child=EdgeConfig,
        ),
        "memory": ConfigFieldSpec(
            name="memory",
            display_name="Memory Stores",
            type_hint="list[MemoryStoreConfig]",
            required=False,
            description="Optional list of memory stores that nodes can reference through their model.memories attachments.",
            child=MemoryStoreConfig,
        ),
        # "organization": ConfigFieldSpec(
        #     name="organization",
        #     display_name="Organization Name",
        #     type_hint="str",
        #     required=False,
        #     description="Organization name",
        # ),
        "initial_instruction": ConfigFieldSpec(
            name="initial_instruction",
            display_name="Initial Instruction",
            type_hint="text",
            required=False,
            description="Graph level initial instruction (for user)",
        ),
        "start": ConfigFieldSpec(
            name="start",
            display_name="Start Node",
            type_hint="list[str]",
            required=False,
            description="Start node ID list (entry list executed at workflow start; not recommended to edit manually)",
            advance=True,
        ),
        "end": ConfigFieldSpec(
            name="end",
            display_name="End Node",
            type_hint="list[str]",
            required=False,
            description="End node ID list (used to collect final graph output, not part of execution logic). Commonly needed in subgraphs. This is an ordered list: earlier nodes are checked first; the first with output becomes the graph output, otherwise continue down the list.",
            advance=True,
        ),
    }

    # CONSTRAINTS = (
    #     RuntimeConstraint(
    #         when={"memory": "*"},
    #         require=["memory"],
    #         message="After defining memory, at least one store must be declared",
    #     ),
    # )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "GraphDefinition":
        mapping = require_mapping(data, path)
        graph_id = optional_str(mapping, "id", path)
        description = optional_str(mapping, "description", path)

        if "vars" in mapping and mapping["vars"]:
            raise ConfigError("vars are only supported at DesignConfig root", extend_path(path, "vars"))

        log_level_raw = mapping.get("log_level", LogLevel.DEBUG.value)
        try:
            log_level = LogLevel(log_level_raw)
        except ValueError as exc:
            raise ConfigError(
                f"log_level must be one of {[lvl.value for lvl in LogLevel]}", extend_path(path, "log_level")
            ) from exc

        is_majority = optional_bool(mapping, "is_majority_voting", path, default=False)
        organization = optional_str(mapping, "organization", path)
        initial_instruction = optional_str(mapping, "initial_instruction", path)

        nodes_raw = ensure_list(mapping.get("nodes"))
        # if not nodes_raw:
        #     raise ConfigError("graph must define at least one node", extend_path(path, "nodes"))
        nodes: List[Node] = []
        for idx, node_dict in enumerate(nodes_raw):
            nodes.append(Node.from_dict(node_dict, path=extend_path(path, f"nodes[{idx}]")))

        edges_raw = ensure_list(mapping.get("edges"))
        edges: List[EdgeConfig] = []
        for idx, edge_dict in enumerate(edges_raw):
            edges.append(EdgeConfig.from_dict(edge_dict, path=extend_path(path, f"edges[{idx}]")))

        memory_cfg: List[MemoryStoreConfig] | None = None
        if "memory" in mapping and mapping["memory"] is not None:
            raw_stores = ensure_list(mapping.get("memory"))
            stores: List[MemoryStoreConfig] = []
            seen: set[str] = set()
            for idx, item in enumerate(raw_stores):
                store = MemoryStoreConfig.from_dict(item, path=extend_path(path, f"memory[{idx}]"))
                if store.name in seen:
                    raise ConfigError(
                        f"duplicated memory store name '{store.name}'",
                        extend_path(path, f"memory[{idx}].name"),
                    )
                seen.add(store.name)
                stores.append(store)
            memory_cfg = stores

        start_nodes: List[str] = []
        if "start" in mapping and mapping["start"] is not None:
            start_value = mapping["start"]
            if isinstance(start_value, str):
                start_nodes = [start_value]
            elif isinstance(start_value, list) and all(isinstance(item, str) for item in start_value):
                seen = set()
                start_nodes = []
                for item in start_value:
                    if item not in seen:
                        seen.add(item)
                        start_nodes.append(item)
            else:
                raise ConfigError("start must be a string or list of strings if provided", extend_path(path, "start"))

        end_nodes = None
        if "end" in mapping and mapping["end"] is not None:
            end_value = mapping["end"]
            if isinstance(end_value, str):
                end_nodes = [end_value]
            elif isinstance(end_value, list) and all(isinstance(item, str) for item in end_value):
                end_nodes = list(end_value)
            else:
                raise ConfigError("end must be a string or list of strings", extend_path(path, "end"))

        definition = cls(
            id=graph_id,
            description=description,
            log_level=log_level,
            is_majority_voting=bool(is_majority) if is_majority is not None else False,
            nodes=nodes,
            edges=edges,
            memory=memory_cfg,
            organization=organization,
            initial_instruction=initial_instruction,
            start_nodes=start_nodes,
            end_nodes=end_nodes,
            path=path,
        )
        definition.validate()
        return definition

    def validate(self) -> None:
        node_ids = [node.id for node in self.nodes]
        counts = Counter(node_ids)
        duplicates = [nid for nid, count in counts.items() if count > 1]
        if duplicates:
            dup_list = ", ".join(sorted(duplicates))
            raise ConfigError(f"duplicate node ids detected: {dup_list}", extend_path(self.path, "nodes"))

        node_set = set(node_ids)
        for start_node in self.start_nodes:
            if start_node not in node_set:
                raise ConfigError(
                    f"start node '{start_node}' not defined in nodes",
                    extend_path(self.path, "start"),
                )
        for edge in self.edges:
            if edge.source not in node_set:
                raise ConfigError(
                    f"edge references unknown source node '{edge.source}'",
                    extend_path(self.path, f"edges->{edge.source}->{edge.target}"),
                )
            if edge.target not in node_set:
                raise ConfigError(
                    f"edge references unknown target node '{edge.target}'",
                    extend_path(self.path, f"edges->{edge.source}->{edge.target}"),
                )

        store_names = {store.name for store in self.memory} if self.memory else set()

        for node in self.nodes:
            model = node.as_config(AgentConfig)
            if model:
                for attachment in model.memories:
                            if attachment.name not in store_names:
                                raise ConfigError(
                                    f"memory reference '{attachment.name}' not defined in graph.memory",
                                    attachment.path or extend_path(node.path, "config.memories"),
                                )


@dataclass
class DesignConfig(BaseConfig):
    version: str
    vars: Dict[str, Any]
    graph: GraphDefinition

    FIELD_SPECS = {
        "version": ConfigFieldSpec(
            name="version",
            display_name="Configuration Version",
            type_hint="str",
            required=False,
            default="0.0.0",
            description="Configuration version number",
            advance=True,
        ),
        "vars": ConfigFieldSpec(
            name="vars",
            display_name="Global Variables",
            type_hint="dict[str, Any]",
            required=False,
            default={},
            description="Global variables that can be referenced via ${VAR}",
        ),
        "graph": ConfigFieldSpec(
            name="graph",
            display_name="Graph Definition",
            type_hint="GraphDefinition",
            required=True,
            description="Core graph definition",
            child=GraphDefinition,
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str = "root") -> "DesignConfig":
        mapping = require_mapping(data, path)
        version = optional_str(mapping, "version", path) or "0.0.0"
        vars_block = optional_dict(mapping, "vars", path) or {}
        if "graph" not in mapping or mapping["graph"] is None:
            raise ConfigError("graph section is required", extend_path(path, "graph"))
        graph = GraphDefinition.from_dict(mapping["graph"], path=extend_path(path, "graph"))
        return cls(version=version, vars=vars_block, graph=graph, path=path)
