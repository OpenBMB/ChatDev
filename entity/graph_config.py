"""GraphConfig wraps parsed graph definitions with runtime metadata."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from entity.enums import LogLevel
from entity.configs import GraphDefinition, MemoryStoreConfig, Node, EdgeConfig


@dataclass
class GraphConfig:
    definition: GraphDefinition
    name: str
    output_root: Path
    log_level: LogLevel
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[str] = None
    vars: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        config: Dict[str, Any],
        name: str,
        output_root: Path | str,
        *,
        source_path: str | None = None,
        vars: Dict[str, Any] | None = None,
    ) -> "GraphConfig":
        definition = GraphDefinition.from_dict(config, path="graph")
        return cls(
            definition=definition,
            name=name,
            output_root=Path(output_root) if output_root else Path("WareHouse"),
            log_level=definition.log_level,
            metadata={},
            source_path=source_path,
            vars=dict(vars or {}),
        )

    @classmethod
    def from_definition(
        cls,
        definition: GraphDefinition,
        name: str,
        output_root: Path | str,
        *,
        source_path: str | None = None,
        vars: Dict[str, Any] | None = None,
    ) -> "GraphConfig":
        return cls(
            definition=definition,
            name=name,
            output_root=Path(output_root) if output_root else Path("WareHouse"),
            log_level=definition.log_level,
            metadata={},
            source_path=source_path,
            vars=dict(vars or {}),
        )

    def get_node_definitions(self) -> List[Node]:
        return self.definition.nodes

    def get_edge_definitions(self) -> List[EdgeConfig]:
        return self.definition.edges

    def get_memory_config(self) -> List[MemoryStoreConfig] | None:
        return self.definition.memory

    def get_organization(self) -> str:
        return self.definition.organization or "DefaultOrg"

    def get_source_path(self) -> str:
        if self.source_path:
            return self.source_path
        return self.definition.id or "config.yaml"

    def get_initial_instruction(self) -> str:
        return self.definition.initial_instruction or ""

    @property
    def is_majority_voting(self) -> bool:
        return self.definition.is_majority_voting

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "output_root": str(self.output_root),
            "log_level": self.log_level.value,
            "metadata": self.metadata,
            "graph": self.definition,
            "vars": self.vars,
        }
