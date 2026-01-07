"""Tooling configuration models."""

import hashlib
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Tuple

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    EnumOption,
    ChildKey,
    ensure_list,
    optional_bool,
    optional_str,
    require_mapping,
    require_str,
    extend_path,
)
from entity.enum_options import enum_options_from_values
from utils.registry import Registry, RegistryError
from utils.function_catalog import FunctionCatalog, get_function_catalog


tooling_type_registry = Registry("tooling_type")
MODULE_ALL_SUFFIX = ":All"


def register_tooling_type(
    name: str,
    *,
    config_cls: type[BaseConfig],
    description: str | None = None,
) -> None:
    metadata = {"summary": description} if description else None
    tooling_type_registry.register(name, target=config_cls, metadata=metadata)


def get_tooling_type_config(name: str) -> type[BaseConfig]:
    entry = tooling_type_registry.get(name)
    config_cls = entry.load()
    if not isinstance(config_cls, type) or not issubclass(config_cls, BaseConfig):
        raise RegistryError(f"Entry '{name}' is not a BaseConfig subclass")
    return config_cls


def iter_tooling_type_registrations() -> Dict[str, type[BaseConfig]]:
    return {name: entry.load() for name, entry in tooling_type_registry.items()}


def iter_tooling_type_metadata() -> Dict[str, Dict[str, Any]]:
    return {name: dict(entry.metadata or {}) for name, entry in tooling_type_registry.items()}


@dataclass
class FunctionToolEntryConfig(BaseConfig):
    """Schema helper used to describe per-function options."""

    name: str | None = None
    description: str | None = None
    parameters: Dict[str, Any] | None = None
    auto_fill: bool = True

    FIELD_SPECS = {
        "name": ConfigFieldSpec(
            name="name",
            display_name="Function Name",
            type_hint="str",
            required=True,
            description="Function name from functions/function_calling directory",
        ),
        # "description": ConfigFieldSpec(
        #     name="description",
        #     display_name="Description",
        #     type_hint="str",
        #     required=False,
        #     description="Override auto-parsed function description, optional",
        #     advance=True,
        # ),
        # "parameters": ConfigFieldSpec(
        #     name="parameters",
        #     display_name="Parameter Schema",
        #     type_hint="object",
        #     required=False,
        #     description="Override JSON Schema generated from function signature, optional",
        #     advance=True,
        # ),
        # "auto_fill": ConfigFieldSpec(
        #     name="auto_fill",
        #     display_name="Auto Fill Description",
        #     type_hint="bool",
        #     required=False,
        #     default=True,
        #     description="Whether to auto-fill description/parameters based on Python function signature",
        #     advance=True,
        # ),
    }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        catalog = get_function_catalog()
        modules = catalog.iter_modules()
        name_spec = specs.get("name")
        if name_spec is not None:
            description = name_spec.description or "Function name"
            enum_options: List[EnumOption] | None = None
            enum_values: List[str] | None = None
            if catalog.load_error:
                description = f"{description} (loading failed: {catalog.load_error})"
            elif not modules:
                description = f"{description} (no functions found in directory)"
            else:
                enum_options = []
                enum_values = []
                for module_name, metas in modules:
                    all_label = f"{module_name}{MODULE_ALL_SUFFIX}"
                    enum_values.append(all_label)
                    preview = ", ".join(meta.name for meta in metas[:3])
                    suffix = "..." if len(metas) > 3 else ""
                    module_hint = f"{module_name}.py"
                    enum_options.append(
                        EnumOption(
                            value=all_label,
                            label=all_label,
                            description=(
                                f"Load all {len(metas)} functions from {module_hint}"
                                + (f" ({preview}{suffix})" if preview else "")
                            ),
                        )
                    )
                for module_name, metas in modules:
                    for meta in metas:
                        label = f"{module_name}:{meta.name}"
                        enum_values.append(meta.name)
                        option_description = meta.description or "This function does not provide a docstring"
                        enum_options.append(
                            EnumOption(
                                value=meta.name,
                                label=label,
                                description=option_description,
                            )
                        )
            specs["name"] = replace(
                name_spec,
                enum=enum_values,
                enum_options=enum_options,
                description=description,
            )
        return specs


@dataclass
class FunctionToolConfig(BaseConfig):
    tools: List[Dict[str, Any]]
    auto_load: bool = True
    timeout: float | None = None
    # schema_version: str | None = None

    FIELD_SPECS = {
        "tools": ConfigFieldSpec(
            name="tools",
            display_name="Function Tool List",
            type_hint="list[FunctionToolEntryConfig]",
            required=True,
            description="Function tool list, at least one item",
            child=FunctionToolEntryConfig,
        ),
        # "auto_load": ConfigFieldSpec(
        #     name="auto_load",
        #     display_name="Auto Load Directory",
        #     type_hint="bool",
        #     required=False,
        #     default=True,
        #     description="Auto-load functions directory on startup",
        #     advance=True
        # ),
        "timeout": ConfigFieldSpec(
            name="timeout",
            display_name="Execution Timeout",
            type_hint="float",
            required=False,
            description="Tool execution timeout (seconds)",
            advance=True
        ),
        # "schema_version": ConfigFieldSpec(
        #     name="schema_version",
        #     display_name="Schema Version",
        #     type_hint="str",
        #     required=False,
        #     description="Tool schema version",
        # ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "FunctionToolConfig":
        mapping = require_mapping(data, path)
        tools = ensure_list(mapping.get("tools"))
        if not tools:
            raise ConfigError("tools must be provided for function tooling", extend_path(path, "tools"))

        catalog = get_function_catalog()
        expanded_tools: List[Tuple[Dict[str, Any], str]] = []
        for idx, tool in enumerate(tools):
            tool_path = extend_path(path, f"tools[{idx}]")
            if not isinstance(tool, Mapping):
                raise ConfigError("tool entry must be a mapping", tool_path)
            normalized = dict(tool)
            raw_name = normalized.get("name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise ConfigError("tool name is required", extend_path(tool_path, "name"))
            name = raw_name.strip()
            normalized["name"] = name
            module_name = cls._extract_module_from_all(name)
            if module_name:
                expanded_tools.extend(
                    cls._expand_module_all_entry(
                        module_name=module_name,
                        catalog=catalog,
                        path=tool_path,
                        original=normalized,
                    )
                )
                continue
            expanded_tools.append((normalized, tool_path))

        tool_specs: List[Dict[str, Any]] = []
        seen_functions: Dict[str, str] = {}
        for entry, entry_path in expanded_tools:
            normalized = dict(entry)
            name = normalized.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ConfigError("tool name is required", extend_path(entry_path, "name"))
            metadata = catalog.get(name)
            if metadata is None:
                raise ConfigError(
                    f"function '{name}' not found under function directory",
                    extend_path(entry_path, "name"),
                )
            previous = seen_functions.get(name)
            if previous is not None:
                raise ConfigError(
                    f"function '{name}' is declared multiple times (also in {previous})",
                    extend_path(entry_path, "name"),
                )
            seen_functions[name] = entry_path

            auto_fill = normalized.get("auto_fill", True)
            if not isinstance(auto_fill, bool):
                raise ConfigError("auto_fill must be boolean", extend_path(entry_path, "auto_fill"))
            merged = dict(normalized)
            if auto_fill:
                if not merged.get("description") and metadata.description:
                    merged["description"] = metadata.description
                if not merged.get("parameters"):
                    merged["parameters"] = deepcopy(metadata.parameters_schema)
            merged.pop("auto_fill", None)
            tool_specs.append(merged)

        auto_load = optional_bool(mapping, "auto_load", path, default=True)
        timeout_value = mapping.get("timeout")
        if timeout_value is not None and not isinstance(timeout_value, (int, float)):
            raise ConfigError("timeout must be numeric", extend_path(path, "timeout"))

        # schema_version = optional_str(mapping, "schema_version", path)

        return cls(
            tools=tool_specs,
            auto_load=bool(auto_load) if auto_load is not None else True,
            timeout=float(timeout_value) if isinstance(timeout_value, (int, float)) else None,
            # schema_version=schema_version,
            path=path,
        )

    @staticmethod
    def _extract_module_from_all(value: str) -> str | None:
        if not value.endswith(MODULE_ALL_SUFFIX):
            return None
        module = value[: -len(MODULE_ALL_SUFFIX)].strip()
        return module or None

    @staticmethod
    def _expand_module_all_entry(
        *,
        module_name: str,
        catalog: FunctionCatalog,
        path: str,
        original: Mapping[str, Any],
    ) -> List[Tuple[Dict[str, Any], str]]:
        disallowed = [key for key in ("description", "parameters", "auto_fill") if key in original]
        if disallowed:
            fields = ", ".join(disallowed)
            raise ConfigError(
                f"{module_name}{MODULE_ALL_SUFFIX} does not support overriding {fields}",
                extend_path(path, "name"),
            )
        functions = catalog.functions_for_module(module_name)
        if not functions:
            raise ConfigError(
                f"module '{module_name}' has no functions under function directory",
                extend_path(path, "name"),
            )
        entries: List[Tuple[Dict[str, Any], str]] = []
        for fn_name in functions:
            entries.append(({"name": fn_name}, path))
        return entries


@dataclass
class McpRemoteConfig(BaseConfig):
    server: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float | None = None

    FIELD_SPECS = {
        "server": ConfigFieldSpec(
            name="server",
            display_name="MCP Server URL",
            type_hint="str",
            required=True,
            description="HTTP(S) endpoint of the MCP server",
        ),
        "headers": ConfigFieldSpec(
            name="headers",
            display_name="Custom Headers",
            type_hint="dict[str, str]",
            required=False,
            description="Additional request headers (e.g. Authorization)",
            advance=True,
        ),
        "timeout": ConfigFieldSpec(
            name="timeout",
            display_name="Client Timeout",
            type_hint="float",
            required=False,
            description="Per-request timeout in seconds",
            advance=True,
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "McpRemoteConfig":
        mapping = require_mapping(data, path)
        server = require_str(mapping, "server", path)

        headers_raw = mapping.get("headers")
        headers: Dict[str, str] = {}
        if headers_raw is not None:
            if not isinstance(headers_raw, Mapping):
                raise ConfigError("headers must be a mapping", extend_path(path, "headers"))
            headers = {str(k): str(v) for k, v in headers_raw.items()}

        timeout_value = mapping.get("timeout")
        timeout: float | None
        if timeout_value is None:
            timeout = None
        elif isinstance(timeout_value, (int, float)):
            timeout = float(timeout_value)
        else:
            raise ConfigError("timeout must be numeric", extend_path(path, "timeout"))

        return cls(server=server, headers=headers, timeout=timeout, path=path)

    def cache_key(self) -> str:
        payload = (
            self.server,
            tuple(sorted(self.headers.items())),
            self.timeout,
        )
        return hashlib.sha1(repr(payload).encode("utf-8")).hexdigest()


@dataclass
class McpLocalConfig(BaseConfig):
    command: str
    args: List[str] = field(default_factory=list)
    cwd: str | None = None
    env: Dict[str, str] = field(default_factory=dict)
    inherit_env: bool = True
    startup_timeout: float = 10.0
    wait_for_log: str | None = None

    FIELD_SPECS = {
        "command": ConfigFieldSpec(
            name="command",
            display_name="Launch Command",
            type_hint="str",
            required=True,
            description="Executable used to start the MCP stdio server (e.g. uvx)",
        ),
        "args": ConfigFieldSpec(
            name="args",
            display_name="Arguments",
            type_hint="list[str]",
            required=False,
            description="Command arguments, defaults to empty list",
        ),
        "cwd": ConfigFieldSpec(
            name="cwd",
            display_name="Working Directory",
            type_hint="str",
            required=False,
            description="Optional working directory for the launch command",
            advance=True,
        ),
        "env": ConfigFieldSpec(
            name="env",
            display_name="Environment Variables",
            type_hint="dict[str, str]",
            required=False,
            description="Additional environment variables for the process",
            advance=True,
        ),
        "inherit_env": ConfigFieldSpec(
            name="inherit_env",
            display_name="Inherit Parent Env",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether to start from parent env before applying overrides",
            advance=True,
        ),
        "startup_timeout": ConfigFieldSpec(
            name="startup_timeout",
            display_name="Startup Timeout",
            type_hint="float",
            required=False,
            default=10.0,
            description="Seconds to wait for readiness logs",
            advance=True,
        ),
        "wait_for_log": ConfigFieldSpec(
            name="wait_for_log",
            display_name="Ready Log Pattern",
            type_hint="str",
            required=False,
            description="Regex that marks readiness when matched against stdout",
            advance=True,
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "McpLocalConfig":
        mapping = require_mapping(data, path)
        command = require_str(mapping, "command", path)
        args_raw = ensure_list(mapping.get("args"))
        normalized_args: List[str] = []
        for idx, arg in enumerate(args_raw):
            arg_path = extend_path(path, f"args[{idx}]")
            if not isinstance(arg, str):
                raise ConfigError("args entries must be strings", arg_path)
            normalized_args.append(arg)

        cwd = optional_str(mapping, "cwd", path)
        inherit_env = optional_bool(mapping, "inherit_env", path, default=True)
        if inherit_env is None:
            inherit_env = True

        env_mapping = mapping.get("env")
        if env_mapping is not None:
            if not isinstance(env_mapping, Mapping):
                raise ConfigError("env must be a mapping", extend_path(path, "env"))
            env = {str(k): str(v) for k, v in env_mapping.items()}
        else:
            env = {}

        timeout_value = mapping.get("startup_timeout", 10.0)
        if timeout_value is None:
            startup_timeout = 10.0
        elif isinstance(timeout_value, (int, float)):
            startup_timeout = float(timeout_value)
        else:
            raise ConfigError("startup_timeout must be numeric", extend_path(path, "startup_timeout"))

        wait_for_log = optional_str(mapping, "wait_for_log", path)
        return cls(
            command=command,
            args=normalized_args,
            cwd=cwd,
            env=env,
            inherit_env=bool(inherit_env),
            startup_timeout=startup_timeout,
            wait_for_log=wait_for_log,
            path=path,
        )

    def cache_key(self) -> str:
        payload = (
            self.command,
            tuple(self.args),
            self.cwd or "",
            tuple(sorted(self.env.items())),
            self.inherit_env,
            self.startup_timeout,
            self.wait_for_log or "",
        )
        return hashlib.sha1(repr(payload).encode("utf-8")).hexdigest()

register_tooling_type(
    "function",
    config_cls=FunctionToolConfig,
    description="Use local Python functions",
)
register_tooling_type(
    "mcp_remote",
    config_cls=McpRemoteConfig,
    description="Connect to an HTTP-based MCP server",
)
register_tooling_type(
    "mcp_local",
    config_cls=McpLocalConfig,
    description="Launch and connect to a local stdio MCP server",
)


@dataclass
class ToolingConfig(BaseConfig):
    type: str
    config: BaseConfig | None = None
    prefix: str | None = None

    FIELD_SPECS = {
        "type": ConfigFieldSpec(
            name="type",
            display_name="Tool Type",
            type_hint="str",
            required=True,
            description="Select a tooling adapter registered via tooling_type_registry (function, mcp_remote, mcp_local, etc.).",
        ),
        "prefix": ConfigFieldSpec(
            name="prefix",
            display_name="Tool Prefix",
            type_hint="str",
            required=False,
            description="Optional prefix for all tools from this source to prevent name collisions (e.g. 'mcp1').",
            advance=True,
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Tool Configuration",
            type_hint="object",
            required=True,
            description="Configuration block validated by the chosen tool type (Python function list, MCP server settings, local command MCP launch, etc.).",
        ),
    }

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, type[BaseConfig]]:
        return {
            ChildKey(field="config", value=name): config_cls
            for name, config_cls in iter_tooling_type_registrations().items()
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "ToolingConfig":
        mapping = require_mapping(data, path)
        tooling_type = require_str(mapping, "type", path)
        try:
            config_cls = get_tooling_type_config(tooling_type)
        except RegistryError as exc:
            raise ConfigError(
                f"tooling.type must be one of {list(iter_tooling_type_registrations().keys())}",
                extend_path(path, "type"),
            ) from exc

        config_payload = mapping.get("config")
        if config_payload is None:
            raise ConfigError("tooling requires config block", extend_path(path, "config"))

        config_obj = config_cls.from_dict(config_payload, path=extend_path(path, "config"))

        prefix = optional_str(mapping, "prefix", path)
        return cls(type=tooling_type, config=config_obj, prefix=prefix, path=path)

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_tooling_type_registrations()
            metadata = iter_tooling_type_metadata()
            type_names = list(registrations.keys())
            default_value = type_names[0] if type_names else None
            descriptions = {name: (metadata.get(name) or {}).get("summary") for name in type_names}
            specs["type"] = replace(
                type_spec,
                enum=type_names,
                default=default_value,
                enum_options=enum_options_from_values(type_names, descriptions),
            )
        return specs
