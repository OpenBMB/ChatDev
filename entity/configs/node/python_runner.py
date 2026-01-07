"""Configuration for Python code execution nodes."""

import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    ensure_list,
    optional_dict,
    optional_str,
    require_mapping,
)


def _default_interpreter() -> str:
    return sys.executable or "python3"


@dataclass
class PythonRunnerConfig(BaseConfig):
    interpreter: str = field(default_factory=_default_interpreter)
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 60
    encoding: str = "utf-8"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "PythonRunnerConfig":
        mapping = require_mapping(data, path)
        interpreter = optional_str(mapping, "interpreter", path) or _default_interpreter()
        args_raw = mapping.get("args")
        args = [str(item) for item in ensure_list(args_raw)] if args_raw is not None else []
        env = optional_dict(mapping, "env", path) or {}
        timeout_value = mapping.get("timeout_seconds", 60)
        if not isinstance(timeout_value, int) or timeout_value <= 0:
            raise ConfigError("timeout_seconds must be a positive integer", f"{path}.timeout_seconds")
        encoding = optional_str(mapping, "encoding", path) or "utf-8"
        if not encoding:
            raise ConfigError("encoding cannot be empty", f"{path}.encoding")
        return cls(
            interpreter=interpreter,
            args=args,
            env={str(key): str(value) for key, value in env.items()},
            timeout_seconds=timeout_value,
            encoding=encoding,
            path=path,
        )

    FIELD_SPECS = {
        "interpreter": ConfigFieldSpec(
            name="interpreter",
            display_name="Python Path",
            type_hint="str",
            required=False,
            default=_default_interpreter(),
            description="Python executable file path, defaults to current process interpreter",
            advance=True,
        ),
        "args": ConfigFieldSpec(
            name="args",
            display_name="Startup Parameters",
            type_hint="list[str]",
            required=False,
            default=[],
            description="Parameter list appended after interpreter",
            advance=True,
        ),
        "env": ConfigFieldSpec(
            name="env",
            display_name="Additional Environment Variables",
            type_hint="dict[str, str]",
            required=False,
            default={},
            description="Additional environment variables, will override process defaults",
            advance=True,
        ),
        "timeout_seconds": ConfigFieldSpec(
            name="timeout_seconds",
            display_name="Timeout (seconds)",
            type_hint="int",
            required=False,
            default=60,
            description="Script execution timeout (seconds)",
        ),
        "encoding": ConfigFieldSpec(
            name="encoding",
            display_name="Output Encoding",
            type_hint="str",
            required=False,
            default="utf-8",
            description="Encoding used to parse stdout/stderr",
            advance=True,
        ),
    }
