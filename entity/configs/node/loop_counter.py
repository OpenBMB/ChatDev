"""Configuration for loop counter guard nodes."""

from dataclasses import dataclass
from typing import Mapping, Any, Optional

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    require_mapping,
    extend_path,
    optional_str,
)


@dataclass
class LoopCounterConfig(BaseConfig):
    """Configuration schema for the loop counter node type."""

    max_iterations: int = 10
    reset_on_emit: bool = True
    message: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "LoopCounterConfig":
        mapping = require_mapping(data or {}, path)
        max_iterations_raw = mapping.get("max_iterations", 10)
        try:
            max_iterations = int(max_iterations_raw)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ConfigError(
                "max_iterations must be an integer",
                extend_path(path, "max_iterations"),
            ) from exc

        if max_iterations < 1:
            raise ConfigError("max_iterations must be >= 1", extend_path(path, "max_iterations"))

        reset_on_emit = bool(mapping.get("reset_on_emit", True))
        message = optional_str(mapping, "message", path)

        return cls(
            max_iterations=max_iterations,
            reset_on_emit=reset_on_emit,
            message=message,
            path=path,
        )

    def validate(self) -> None:
        if self.max_iterations < 1:
            raise ConfigError("max_iterations must be >= 1", extend_path(self.path, "max_iterations"))

    FIELD_SPECS = {
        "max_iterations": ConfigFieldSpec(
            name="max_iterations",
            display_name="Maximum Iterations",
            type_hint="int",
            required=True,
            default=10,
            description="How many times the loop can run before this node emits an output.",
        ),
        "reset_on_emit": ConfigFieldSpec(
            name="reset_on_emit",
            display_name="Reset After Emit",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether to reset the internal counter after reaching the limit.",
            advance=True,
        ),
        "message": ConfigFieldSpec(
            name="message",
            display_name="Release Message",
            type_hint="text",
            required=False,
            description="Optional text sent downstream once the iteration cap is reached.",
            advance=True,
        ),
    }
