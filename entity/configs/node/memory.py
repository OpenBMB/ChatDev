"""Memory-related configuration dataclasses."""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping

from entity.enums import AgentExecFlowStage
from entity.enum_options import enum_options_for, enum_options_from_values
from schema_registry import (
    SchemaLookupError,
    get_memory_store_schema,
    iter_memory_store_schemas,
)

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    ChildKey,
    ensure_list,
    optional_dict,
    optional_str,
    require_mapping,
    require_str,
    extend_path,
)


@dataclass
class EmbeddingConfig(BaseConfig):
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "EmbeddingConfig":
        mapping = require_mapping(data, path)
        provider = require_str(mapping, "provider", path)
        model = require_str(mapping, "model", path)
        api_key = optional_str(mapping, "api_key", path)
        base_url = optional_str(mapping, "base_url", path)
        params = optional_dict(mapping, "params", path) or {}
        return cls(provider=provider, model=model, api_key=api_key, base_url=base_url, params=params, path=path)

    FIELD_SPECS = {
        "provider": ConfigFieldSpec(
            name="provider",
            display_name="Embedding Provider",
            type_hint="str",
            required=True,
            default="openai",
            description="Embedding provider",
        ),
        "model": ConfigFieldSpec(
            name="model",
            display_name="Embedding Model",
            type_hint="str",
            required=True,
            default="text-embedding-3-small",
            description="Embedding model name",
        ),
        "api_key": ConfigFieldSpec(
            name="api_key",
            display_name="API Key",
            type_hint="str",
            required=False,
            description="API key",
            default="${API_KEY}",
            advance=True,
        ),
        "base_url": ConfigFieldSpec(
            name="base_url",
            display_name="Base URL",
            type_hint="str",
            required=False,
            description="Custom Base URL",
            default="${BASE_URL}",
            advance=True,
        ),
        "params": ConfigFieldSpec(
            name="params",
            display_name="Custom Parameters",
            type_hint="dict[str, Any]",
            required=False,
            default={},
            description="Embedding parameters (temperature, etc.)",
            advance=True,
        ),
    }


@dataclass
class FileSourceConfig(BaseConfig):
    source_path: str
    file_types: List[str] | None = None
    recursive: bool = True
    encoding: str = "utf-8"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "FileSourceConfig":
        mapping = require_mapping(data, path)
        file_path = require_str(mapping, "path", path)
        file_types_value = mapping.get("file_types")
        file_types: List[str] | None = None
        if file_types_value is not None:
            items = ensure_list(file_types_value)
            normalized: List[str] = []
            for idx, item in enumerate(items):
                if not isinstance(item, str):
                    raise ConfigError("file_types entries must be strings", extend_path(path, f"file_types[{idx}]") )
                normalized.append(item)
            file_types = normalized

        recursive_value = mapping.get("recursive", True)
        if not isinstance(recursive_value, bool):
            raise ConfigError("recursive must be boolean", extend_path(path, "recursive"))

        encoding = optional_str(mapping, "encoding", path) or "utf-8"
        return cls(source_path=file_path, file_types=file_types, recursive=recursive_value, encoding=encoding, path=path)

    FIELD_SPECS = {
        "path": ConfigFieldSpec(
            name="path",
            display_name="File/Directory Path",
            type_hint="str",
            required=True,
            description="Path to file/directory to be indexed",
        ),
        "file_types": ConfigFieldSpec(
            name="file_types",
            display_name="File Type Filter",
            type_hint="list[str]",
            required=False,
            description="List of file type suffixes to limit (e.g. .md, .txt)",
        ),
        "recursive": ConfigFieldSpec(
            name="recursive",
            display_name="Recursive Subdirectories",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether to include subdirectories recursively",
            advance=True,
        ),
        "encoding": ConfigFieldSpec(
            name="encoding",
            display_name="File Encoding",
            type_hint="str",
            required=False,
            default="utf-8",
            description="Encoding used to read files",
            advance=True,
        ),
    }


@dataclass
class SimpleMemoryConfig(BaseConfig):
    memory_path: str | None = None
    embedding: EmbeddingConfig | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "SimpleMemoryConfig":
        mapping = require_mapping(data, path)
        memory_path = optional_str(mapping, "memory_path", path)
        embedding_cfg = None
        if "embedding" in mapping and mapping["embedding"] is not None:
            embedding_cfg = EmbeddingConfig.from_dict(mapping["embedding"], path=extend_path(path, "embedding"))
        return cls(memory_path=memory_path, embedding=embedding_cfg, path=path)

    FIELD_SPECS = {
        "memory_path": ConfigFieldSpec(
            name="memory_path",
            display_name="Memory File Path",
            type_hint="str",
            required=False,
            description="Simple memory file path",
            advance=True,
        ),
        "embedding": ConfigFieldSpec(
            name="embedding",
            display_name="Embedding Configuration",
            type_hint="EmbeddingConfig",
            required=False,
            description="Optional embedding configuration",
            child=EmbeddingConfig,
        ),
    }


@dataclass
class FileMemoryConfig(BaseConfig):
    index_path: str | None = None
    file_sources: List[FileSourceConfig] = field(default_factory=list)
    embedding: EmbeddingConfig | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "FileMemoryConfig":
        mapping = require_mapping(data, path)
        sources_raw = ensure_list(mapping.get("file_sources"))
        if not sources_raw:
            raise ConfigError("file_sources must contain at least one entry", extend_path(path, "file_sources"))
        sources: List[FileSourceConfig] = []
        for idx, item in enumerate(sources_raw):
            sources.append(FileSourceConfig.from_dict(item, path=extend_path(path, f"file_sources[{idx}]")))

        index_path = optional_str(mapping, "index_path", path)
        if index_path is None:
            index_path = optional_str(mapping, "memory_path", path)

        embedding_cfg = None
        if "embedding" in mapping and mapping["embedding"] is not None:
            embedding_cfg = EmbeddingConfig.from_dict(mapping["embedding"], path=extend_path(path, "embedding"))

        return cls(index_path=index_path, file_sources=sources, embedding=embedding_cfg, path=path)

    FIELD_SPECS = {
        "index_path": ConfigFieldSpec(
            name="index_path",
            display_name="Index Path",
            type_hint="str",
            required=False,
            description="Vector index storage path",
            advance=True,
        ),
        "file_sources": ConfigFieldSpec(
            name="file_sources",
            display_name="File Source List",
            type_hint="list[FileSourceConfig]",
            required=True,
            description="List of file sources to ingest",
            child=FileSourceConfig,
        ),
        "embedding": ConfigFieldSpec(
            name="embedding",
            display_name="Embedding Configuration",
            type_hint="EmbeddingConfig",
            required=False,
            description="Embedding used for file memory",
            child=EmbeddingConfig,
        ),
    }


@dataclass
class BlackboardMemoryConfig(BaseConfig):
    memory_path: str | None = None
    max_items: int = 1000

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "BlackboardMemoryConfig":
        mapping = require_mapping(data, path)
        memory_path = optional_str(mapping, "memory_path", path)
        max_items_value = mapping.get("max_items", 1000)
        if not isinstance(max_items_value, int) or max_items_value <= 0:
            raise ConfigError("max_items must be a positive integer", extend_path(path, "max_items"))
        return cls(memory_path=memory_path, max_items=max_items_value, path=path)

    FIELD_SPECS = {
        "memory_path": ConfigFieldSpec(
            name="memory_path",
            display_name="Blackboard Path",
            type_hint="str",
            required=False,
            description="JSON path for blackboard memory writing. Pass 'auto' to auto-create in working directory, valid for this run only",
            default="auto",
            advance=True,
        ),
        "max_items": ConfigFieldSpec(
            name="max_items",
            display_name="Maximum Items",
            type_hint="int",
            required=False,
            default=1000,
            description="Maximum number of memory items to retain (trimmed by time)",
            advance=True,
        ),
    }


@dataclass
class MemoryStoreConfig(BaseConfig):
    name: str
    type: str
    config: BaseConfig | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "MemoryStoreConfig":
        mapping = require_mapping(data, path)
        name = require_str(mapping, "name", path)
        store_type = require_str(mapping, "type", path)
        try:
            schema = get_memory_store_schema(store_type)
        except SchemaLookupError as exc:
            raise ConfigError(f"unsupported memory store type '{store_type}'", extend_path(path, "type")) from exc

        if "config" not in mapping or mapping["config"] is None:
            raise ConfigError("memory store requires config block", extend_path(path, "config"))

        config_obj = schema.config_cls.from_dict(mapping["config"], path=extend_path(path, "config"))
        return cls(name=name, type=store_type, config=config_obj, path=path)

    def require_payload(self) -> BaseConfig:
        if not self.config:
            raise ConfigError("memory store payload missing", extend_path(self.path, "config"))
        return self.config

    FIELD_SPECS = {
        "name": ConfigFieldSpec(
            name="name",
            display_name="Store Name",
            type_hint="str",
            required=True,
            description="Unique name of the memory store",
        ),
        "type": ConfigFieldSpec(
            name="type",
            display_name="Store Type",
            type_hint="str",
            required=True,
            description="Memory store type",
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Store Configuration",
            type_hint="object",
            required=True,
            description="Schema required by the selected store type (simple/file/blackboard/etc.), following that type's required keys.",
        ),
    }

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, type[BaseConfig]]:
        return {
            ChildKey(field="config", value=name): schema.config_cls
            for name, schema in iter_memory_store_schemas().items()
        }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_memory_store_schemas()
            names = list(registrations.keys())
            descriptions = {name: schema.summary for name, schema in registrations.items()}
            specs["type"] = replace(
                type_spec,
                enum=names,
                enum_options=enum_options_from_values(names, descriptions, preserve_label_case=True),
            )
        return specs


@dataclass
class MemoryAttachmentConfig(BaseConfig):
    name: str
    retrieve_stage: List[AgentExecFlowStage] | None = None
    top_k: int = 3
    similarity_threshold: float = -1.0
    read: bool = True
    write: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "MemoryAttachmentConfig":
        mapping = require_mapping(data, path)
        name = require_str(mapping, "name", path)

        stages_raw = mapping.get("retrieve_stage")
        stages: List[AgentExecFlowStage] | None = None
        if stages_raw is not None:
            stage_list = ensure_list(stages_raw)
            parsed: List[AgentExecFlowStage] = []
            for idx, item in enumerate(stage_list):
                try:
                    parsed.append(AgentExecFlowStage(item))
                except ValueError as exc:
                    raise ConfigError(
                        f"retrieve_stage entries must be one of {[stage.value for stage in AgentExecFlowStage]}",
                        extend_path(path, f"retrieve_stage[{idx}]"),
                    ) from exc
            stages = parsed

        top_k_value = mapping.get("top_k", 3)
        if not isinstance(top_k_value, int) or top_k_value <= 0:
            raise ConfigError("top_k must be a positive integer", extend_path(path, "top_k"))

        threshold_value = mapping.get("similarity_threshold", -1.0)
        if not isinstance(threshold_value, (int, float)):
            raise ConfigError("similarity_threshold must be numeric", extend_path(path, "similarity_threshold"))

        read_value = mapping.get("read", True)
        if not isinstance(read_value, bool):
            raise ConfigError("read must be boolean", extend_path(path, "read"))

        write_value = mapping.get("write", True)
        if not isinstance(write_value, bool):
            raise ConfigError("write must be boolean", extend_path(path, "write"))

        return cls(
            name=name,
            retrieve_stage=stages,
            top_k=top_k_value,
            similarity_threshold=float(threshold_value),
            read=read_value,
            write=write_value,
            path=path,
        )

    FIELD_SPECS = {
        "name": ConfigFieldSpec(
            name="name",
            display_name="Memory Name",
            type_hint="str",
            required=True,
            description="Name of the referenced memory store",
        ),
        "retrieve_stage": ConfigFieldSpec(
            name="retrieve_stage",
            display_name="Retrieve Stage",
            type_hint="list[AgentExecFlowStage]",
            required=False,
            description="Execution stages when memory retrieval occurs. If not set, defaults to all stages. NOTE: this config is related to thinking, if the thinking module is not used, this config has only effect on `gen` stage.",
            enum=[stage.value for stage in AgentExecFlowStage],
            enum_options=enum_options_for(AgentExecFlowStage),
        ),
        "top_k": ConfigFieldSpec(
            name="top_k",
            display_name="Top K",
            type_hint="int",
            required=False,
            default=3,
            description="Number of items to retrieve",
            advance=True,
        ),
        "similarity_threshold": ConfigFieldSpec(
            name="similarity_threshold",
            display_name="Similarity Threshold",
            type_hint="float",
            required=False,
            default=-1.0,
            description="Similarity threshold (-1 means no similarity threshold filter)",
            advance=True,
        ),
        "read": ConfigFieldSpec(
            name="read",
            display_name="Allow Read",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether to read this memory during execution",
            advance=True,
        ),
        "write": ConfigFieldSpec(
            name="write",
            display_name="Allow Write",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether to write back to this memory after execution",
            advance=True,
        ),
    }
