"""Agent-specific configuration dataclasses."""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:  # pragma: no cover - Python < 3.11 lacks BaseExceptionGroup
    from builtins import BaseExceptionGroup as _BASE_EXCEPTION_GROUP_TYPE  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    _BASE_EXCEPTION_GROUP_TYPE = None  # type: ignore[assignment]

from entity.enums import AgentInputMode
from schema_registry import iter_model_provider_schemas
from utils.strs import titleize

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    EnumOption,
    optional_bool,
    optional_dict,
    optional_str,
    require_mapping,
    require_str,
    extend_path,
)
from .memory import MemoryAttachmentConfig
from .thinking import ThinkingConfig
from entity.configs.node.tooling import ToolingConfig


DEFAULT_RETRYABLE_STATUS_CODES = [408, 409, 425, 429, 500, 502, 503, 504]
DEFAULT_RETRYABLE_EXCEPTION_TYPES = [
    "RateLimitError",
    "APITimeoutError",
    "APIError",
    "APIConnectionError",
    "ServiceUnavailableError",
    "TimeoutError",
    "InternalServerError",
    "RemoteProtocolError",
    "TransportError",
    "ConnectError",
    "ConnectTimeout",
    "ReadError",
    "ReadTimeout",
]
DEFAULT_RETRYABLE_MESSAGE_SUBSTRINGS = [
    "rate limit",
    "temporarily unavailable",
    "timeout",
    "server disconnected",
    "connection reset",
]


def _coerce_float(value: Any, *, field_path: str, minimum: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        coerced = float(value)
    else:
        raise ConfigError("expected number", field_path)
    if coerced < minimum:
        raise ConfigError(f"value must be >= {minimum}", field_path)
    return coerced


def _coerce_positive_int(value: Any, *, field_path: str, minimum: int = 1) -> int:
    if isinstance(value, bool):
        raise ConfigError("expected integer", field_path)
    if isinstance(value, int):
        coerced = value
    else:
        raise ConfigError("expected integer", field_path)
    if coerced < minimum:
        raise ConfigError(f"value must be >= {minimum}", field_path)
    return coerced


def _coerce_str_list(value: Any, *, field_path: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ConfigError("expected list of strings", field_path)
    result: List[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise ConfigError("expected list of strings", f"{field_path}[{idx}]")
        result.append(item.strip())
    return result


def _coerce_int_list(value: Any, *, field_path: str) -> List[int]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ConfigError("expected list of integers", field_path)
    ints: List[int] = []
    for idx, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int):
            raise ConfigError("expected list of integers", f"{field_path}[{idx}]")
        ints.append(item)
    return ints


@dataclass
class AgentRetryConfig(BaseConfig):
    enabled: bool = True
    max_attempts: int = 5
    min_wait_seconds: float = 1.0
    max_wait_seconds: float = 6.0
    retry_on_status_codes: List[int] = field(default_factory=lambda: list(DEFAULT_RETRYABLE_STATUS_CODES))
    retry_on_exception_types: List[str] = field(default_factory=lambda: [name.lower() for name in DEFAULT_RETRYABLE_EXCEPTION_TYPES])
    non_retry_exception_types: List[str] = field(default_factory=list)
    retry_on_error_substrings: List[str] = field(default_factory=lambda: list(DEFAULT_RETRYABLE_MESSAGE_SUBSTRINGS))

    FIELD_SPECS = {
        "enabled": ConfigFieldSpec(
            name="enabled",
            display_name="Enable Retry",
            type_hint="bool",
            required=False,
            default=True,
            description="Toggle automatic retry for provider calls",
        ),
        "max_attempts": ConfigFieldSpec(
            name="max_attempts",
            display_name="Max Attempts",
            type_hint="int",
            required=False,
            default=5,
            description="Maximum number of total attempts (initial call + retries)",
        ),
        "min_wait_seconds": ConfigFieldSpec(
            name="min_wait_seconds",
            display_name="Min Wait Seconds",
            type_hint="float",
            required=False,
            default=1.0,
            description="Minimum backoff wait before retry",
            advance=True,
        ),
        "max_wait_seconds": ConfigFieldSpec(
            name="max_wait_seconds",
            display_name="Max Wait Seconds",
            type_hint="float",
            required=False,
            default=6.0,
            description="Maximum backoff wait before retry",
            advance=True,
        ),
        "retry_on_status_codes": ConfigFieldSpec(
            name="retry_on_status_codes",
            display_name="Retryable Status Codes",
            type_hint="list[int]",
            required=False,
            description="HTTP status codes that should trigger a retry",
            advance=True,
        ),
        "retry_on_exception_types": ConfigFieldSpec(
            name="retry_on_exception_types",
            display_name="Retryable Exception Types",
            type_hint="list[str]",
            required=False,
            description="Exception class names (case-insensitive) that should trigger retries",
            advance=True,
        ),
        "non_retry_exception_types": ConfigFieldSpec(
            name="non_retry_exception_types",
            display_name="Non-Retryable Exception Types",
            type_hint="list[str]",
            required=False,
            description="Exception class names (case-insensitive) that should never retry",
            advance=True,
        ),
        "retry_on_error_substrings": ConfigFieldSpec(
            name="retry_on_error_substrings",
            display_name="Retryable Message Substrings",
            type_hint="list[str]",
            required=False,
            description="Substring matches within exception messages that enable retry",
            advance=True,
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "AgentRetryConfig":
        mapping = require_mapping(data, path)
        enabled = optional_bool(mapping, "enabled", path, default=True)
        if enabled is None:
            enabled = True
        max_attempts = _coerce_positive_int(mapping.get("max_attempts", 5), field_path=extend_path(path, "max_attempts"))
        min_wait = _coerce_float(mapping.get("min_wait_seconds", 1.0), field_path=extend_path(path, "min_wait_seconds"), minimum=0.0)
        max_wait = _coerce_float(mapping.get("max_wait_seconds", 6.0), field_path=extend_path(path, "max_wait_seconds"), minimum=0.0)
        if max_wait < min_wait:
            raise ConfigError("max_wait_seconds must be >= min_wait_seconds", extend_path(path, "max_wait_seconds"))

        status_codes = mapping.get("retry_on_status_codes")
        if status_codes is None:
            retry_status_codes = list(DEFAULT_RETRYABLE_STATUS_CODES)
        else:
            retry_status_codes = _coerce_int_list(status_codes, field_path=extend_path(path, "retry_on_status_codes"))

        retry_types_raw = mapping.get("retry_on_exception_types")
        if retry_types_raw is None:
            retry_types = [name.lower() for name in DEFAULT_RETRYABLE_EXCEPTION_TYPES]
        else:
            retry_types = [value.lower() for value in _coerce_str_list(retry_types_raw, field_path=extend_path(path, "retry_on_exception_types")) if value]

        non_retry_types = [value.lower() for value in _coerce_str_list(mapping.get("non_retry_exception_types"), field_path=extend_path(path, "non_retry_exception_types")) if value]

        retry_substrings_raw = mapping.get("retry_on_error_substrings")
        if retry_substrings_raw is None:
            retry_substrings = list(DEFAULT_RETRYABLE_MESSAGE_SUBSTRINGS)
        else:
            retry_substrings = [
                value.lower()
                for value in _coerce_str_list(
                    retry_substrings_raw,
                    field_path=extend_path(path, "retry_on_error_substrings"),
                )
                if value
            ]

        return cls(
            enabled=enabled,
            max_attempts=max_attempts,
            min_wait_seconds=min_wait,
            max_wait_seconds=max_wait,
            retry_on_status_codes=retry_status_codes,
            retry_on_exception_types=retry_types,
            non_retry_exception_types=non_retry_types,
            retry_on_error_substrings=retry_substrings,
            path=path,
        )

    @property
    def is_active(self) -> bool:
        return self.enabled and self.max_attempts > 1

    def should_retry(self, exc: BaseException) -> bool:
        if not self.is_active:
            return False

        chain: List[tuple[BaseException, set[str], int | None, str]] = []
        for error in self._iter_exception_chain(exc):
            chain.append(
                (
                    error,
                    self._exception_name_set(error),
                    self._extract_status_code(error),
                    str(error).lower(),
                )
            )

        if self.non_retry_exception_types:
            for _, names, _, _ in chain:
                if any(name in names for name in self.non_retry_exception_types):
                    return False

        if self.retry_on_exception_types:
            for _, names, _, _ in chain:
                if any(name in names for name in self.retry_on_exception_types):
                    return True

        if self.retry_on_status_codes:
            for _, _, status_code, _ in chain:
                if status_code is not None and status_code in self.retry_on_status_codes:
                    return True

        if self.retry_on_error_substrings:
            for _, _, _, message in chain:
                if message and any(substr in message for substr in self.retry_on_error_substrings):
                    return True

        return False

    def _exception_name_set(self, exc: BaseException) -> set[str]:
        names: set[str] = set()
        for cls in exc.__class__.mro():
            names.add(cls.__name__.lower())
            names.add(f"{cls.__module__}.{cls.__name__}".lower())
        return names

    def _extract_status_code(self, exc: BaseException) -> int | None:
        for attr in ("status_code", "http_status", "status", "statusCode"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
        response = getattr(exc, "response", None)
        if response is not None:
            for attr in ("status_code", "status", "statusCode"):
                value = getattr(response, attr, None)
                if isinstance(value, int):
                    return value
        return None

    def _iter_exception_chain(self, exc: BaseException) -> Iterable[BaseException]:
        seen: set[int] = set()
        stack: List[BaseException] = [exc]
        while stack:
            current = stack.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            yield current

            linked: List[BaseException] = []
            cause = getattr(current, "__cause__", None)
            context = getattr(current, "__context__", None)
            if isinstance(cause, BaseException):
                linked.append(cause)
            if isinstance(context, BaseException):
                linked.append(context)
            if _BASE_EXCEPTION_GROUP_TYPE is not None and isinstance(current, _BASE_EXCEPTION_GROUP_TYPE):
                for exc_item in getattr(current, "exceptions", None) or ():
                    if isinstance(exc_item, BaseException):
                        linked.append(exc_item)
            stack.extend(linked)


@dataclass
class AgentConfig(BaseConfig):
    provider: str
    base_url: str
    name: str
    role: str | None = None
    api_key: str | None = None
    params: Dict[str, Any] = field(default_factory=dict)
    retry: AgentRetryConfig | None = None
    input_mode: AgentInputMode = AgentInputMode.MESSAGES
    tooling: List[ToolingConfig] = field(default_factory=list)
    thinking: ThinkingConfig | None = None
    memories: List[MemoryAttachmentConfig] = field(default_factory=list)
    # Claude Code persistent session support
    persistent_session: bool = True  # Keep session alive across calls (claude-code only)
    skip_memory: bool = False  # Skip ChatDev memory system (claude-code manages its own)

    # Runtime attributes (attached dynamically)
    token_tracker: Any | None = field(default=None, init=False, repr=False)
    node_id: str | None = field(default=None, init=False, repr=False)
    workspace_root: Any | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "AgentConfig":
        mapping = require_mapping(data, path)
        provider = require_str(mapping, "provider", path)
        base_url = optional_str(mapping, "base_url", path)
        name_value = mapping.get("name")
        if isinstance(name_value, str) and name_value.strip():
            model_name = name_value.strip()
        else:
            raise ConfigError("model.name must be a non-empty string", extend_path(path, "name"))

        role = optional_str(mapping, "role", path)
        api_key = optional_str(mapping, "api_key", path)
        params = optional_dict(mapping, "params", path) or {}
        raw_input_mode = optional_str(mapping, "input_mode", path)
        input_mode = AgentInputMode.MESSAGES
        if raw_input_mode:
            try:
                input_mode = AgentInputMode(raw_input_mode.strip().lower())
            except ValueError as exc:
                raise ConfigError(
                    "model.input_mode must be 'prompt' or 'messages'",
                    extend_path(path, "input_mode"),
                ) from exc

        tooling_cfg: List[ToolingConfig] = []
        if "tooling" in mapping and mapping["tooling"] is not None:
            raw_tooling = mapping["tooling"]
            if not isinstance(raw_tooling, list):
                 raise ConfigError("tooling must be a list", extend_path(path, "tooling"))
            for idx, item in enumerate(raw_tooling):
                tooling_cfg.append(
                    ToolingConfig.from_dict(item, path=extend_path(path, f"tooling[{idx}]"))
                )

        thinking_cfg = None
        if "thinking" in mapping and mapping["thinking"] is not None:
            thinking_cfg = ThinkingConfig.from_dict(mapping["thinking"], path=extend_path(path, "thinking"))

        memories_cfg: List[MemoryAttachmentConfig] = []
        if "memories" in mapping and mapping["memories"] is not None:
            raw_memories = mapping["memories"]
            if not isinstance(raw_memories, list):
                raise ConfigError("memories must be a list", extend_path(path, "memories"))
            for idx, item in enumerate(raw_memories):
                memories_cfg.append(
                    MemoryAttachmentConfig.from_dict(item, path=extend_path(path, f"memories[{idx}]"))
                )

        retry_cfg = None
        if "retry" in mapping and mapping["retry"] is not None:
            retry_cfg = AgentRetryConfig.from_dict(mapping["retry"], path=extend_path(path, "retry"))

        # Claude Code persistent session options
        persistent_session = optional_bool(mapping, "persistent_session", path, default=True)
        if persistent_session is None:
            persistent_session = True
        skip_memory = optional_bool(mapping, "skip_memory", path, default=False)
        if skip_memory is None:
            skip_memory = False

        return cls(
            provider=provider,
            base_url=base_url,
            name=model_name,
            role=role,
            api_key=api_key,
            params=params,
            tooling=tooling_cfg,
            thinking=thinking_cfg,
            memories=memories_cfg,
            retry=retry_cfg,
            input_mode=input_mode,
            persistent_session=persistent_session,
            skip_memory=skip_memory,
            path=path,
        )

    FIELD_SPECS = {
        "name": ConfigFieldSpec(
            name="name",
            display_name="Model Name",
            type_hint="str",
            required=True,
            description="Specific model name e.g. gpt-4o",
        ),
        "role": ConfigFieldSpec(
            name="role",
            display_name="System Prompt",
            type_hint="text",
            required=False,
            description="Model system prompt",
        ),
        "provider": ConfigFieldSpec(
            name="provider",
            display_name="Model Provider",
            type_hint="str",
            required=True,
            description="Name of a registered provider (openai, gemini, etc.) that selects the underlying client adapter.",
            default="openai",
        ),
        "base_url": ConfigFieldSpec(
            name="base_url",
            display_name="Base URL",
            type_hint="str",
            required=False,
            description="Override the provider's default endpoint; leave empty to use the built-in base URL.",
            advance=True,
            default="${BASE_URL}",
        ),
        "api_key": ConfigFieldSpec(
            name="api_key",
            display_name="API Key",
            type_hint="str",
            required=False,
            description="Credential consumed by the provider client; reference an env var such as ${API_KEY} that matches the selected provider.",
            advance=True,
            default="${API_KEY}",
        ),
        "params": ConfigFieldSpec(
            name="params",
            display_name="Call Parameters",
            type_hint="dict[str, Any]",
            required=False,
            default={},
            description="Call parameters (temperature, top_p, etc.)",
            advance=True,
        ),
        # "input_mode": ConfigFieldSpec(  # currently, many features depend on messages mode, so hide this and force messages
        #     name="input_mode",
        #     display_name="Input Mode",
        #     type_hint="enum:AgentInputMode",
        #     required=False,
        #     default=AgentInputMode.MESSAGES.value,
        #     description="Model input mode: messages (default) or prompt",
        #     enum=[item.value for item in AgentInputMode],
        #     advance=True,
        #     enum_options=enum_options_for(AgentInputMode),
        # ),
        "tooling": ConfigFieldSpec(
            name="tooling",
            display_name="Tool Configuration",
            type_hint="list[ToolingConfig]",
            required=False,
            description="Bound tool configuration list",
            child=ToolingConfig,
            advance=True,
        ),
        "thinking": ConfigFieldSpec(
            name="thinking",
            display_name="Thinking Configuration",
            type_hint="ThinkingConfig",
            required=False,
            description="Thinking process configuration",
            child=ThinkingConfig,
            advance=True,
        ),
        "memories": ConfigFieldSpec(
            name="memories",
            display_name="Memory Attachments",
            type_hint="list[MemoryAttachmentConfig]",
            required=False,
            description="Associated memory references",
            child=MemoryAttachmentConfig,
            advance=True,
        ),
        "retry": ConfigFieldSpec(
            name="retry",
            display_name="Retry Policy",
            type_hint="AgentRetryConfig",
            required=False,
            description="Automatic retry policy for this model",
            child=AgentRetryConfig,
            advance=True,
        ),
        "persistent_session": ConfigFieldSpec(
            name="persistent_session",
            display_name="Persistent Session",
            type_hint="bool",
            required=False,
            default=True,
            description="Keep Claude Code session alive across calls (claude-code provider only)",
            advance=True,
        ),
        "skip_memory": ConfigFieldSpec(
            name="skip_memory",
            display_name="Skip Memory",
            type_hint="bool",
            required=False,
            default=False,
            description="Skip ChatDev memory system when using claude-code provider (Claude manages its own context)",
            advance=True,
        ),
    }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        provider_spec = specs.get("provider")
        if provider_spec:
            enum_spec = cls._apply_provider_enum(provider_spec)
            specs["provider"] = enum_spec
        return specs

    @staticmethod
    def _apply_provider_enum(provider_spec: ConfigFieldSpec) -> ConfigFieldSpec:
        provider_names, metadata = AgentConfig._provider_registry_snapshot()
        if not provider_names:
            return provider_spec

        enum_options: List[EnumOption] = []
        for name in provider_names:
            meta = metadata.get(name) or {}
            label = meta.get("label") or titleize(name)
            enum_options.append(
                EnumOption(
                    value=name,
                    label=label,
                    description=meta.get("summary"),
                )
            )

        default_value = provider_spec.default
        if not default_value or default_value not in provider_names:
            default_value = AgentConfig._preferred_provider_default(provider_names)

        return replace(
            provider_spec,
            enum=provider_names,
            enum_options=enum_options,
            default=default_value,
        )

    @staticmethod
    def _preferred_provider_default(provider_names: List[str]) -> str:
        if "openai" in provider_names:
            return "openai"
        return provider_names[0]

    @staticmethod
    def _provider_registry_snapshot() -> tuple[List[str], Dict[str, Dict[str, Any]]]:
        specs = iter_model_provider_schemas()
        names = list(specs.keys())
        metadata: Dict[str, Dict[str, Any]] = {}
        for name, spec in specs.items():
            metadata[name] = {
                "label": spec.label,
                "summary": spec.summary,
                **(spec.metadata or {}),
            }
        return names, metadata
