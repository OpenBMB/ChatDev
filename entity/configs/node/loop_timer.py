"""Configuration for loop timer guard nodes."""

from dataclasses import dataclass
from typing import Mapping, Any, Optional

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    EnumOption,
    require_mapping,
    extend_path,
    optional_str,
)


@dataclass
class LoopTimerConfig(BaseConfig):
    """Configuration schema for the loop timer node type."""

    max_duration: float = 60.0
    duration_unit: str = "seconds"
    reset_on_emit: bool = True
    message: Optional[str] = None
    passthrough: bool = False

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any] | None, *, path: str
    ) -> "LoopTimerConfig":
        mapping = require_mapping(data or {}, path)
        max_duration_raw = mapping.get("max_duration", 60.0)
        try:
            max_duration = float(max_duration_raw)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ConfigError(
                "max_duration must be a number",
                extend_path(path, "max_duration"),
            ) from exc

        if max_duration <= 0:
            raise ConfigError(
                "max_duration must be > 0", extend_path(path, "max_duration")
            )

        duration_unit = str(mapping.get("duration_unit", "seconds"))
        valid_units = ["seconds", "minutes", "hours"]
        if duration_unit not in valid_units:
            raise ConfigError(
                f"duration_unit must be one of: {', '.join(valid_units)}",
                extend_path(path, "duration_unit"),
            )

        reset_on_emit = bool(mapping.get("reset_on_emit", True))
        message = optional_str(mapping, "message", path)
        passthrough = bool(mapping.get("passthrough", False))

        return cls(
            max_duration=max_duration,
            duration_unit=duration_unit,
            reset_on_emit=reset_on_emit,
            message=message,
            passthrough=passthrough,
            path=path,
        )

    def validate(self) -> None:
        if self.max_duration <= 0:
            raise ConfigError(
                "max_duration must be > 0", extend_path(self.path, "max_duration")
            )

        valid_units = ["seconds", "minutes", "hours"]
        if self.duration_unit not in valid_units:
            raise ConfigError(
                f"duration_unit must be one of: {', '.join(valid_units)}",
                extend_path(self.path, "duration_unit"),
            )

    FIELD_SPECS = {
        "max_duration": ConfigFieldSpec(
            name="max_duration",
            display_name="Maximum Duration",
            type_hint="float",
            required=True,
            default=60.0,
            description="How long the loop can run before this node emits an output.",
        ),
        "duration_unit": ConfigFieldSpec(
            name="duration_unit",
            display_name="Duration Unit",
            type_hint="str",
            required=True,
            default="seconds",
            description="Unit of time for max_duration: 'seconds', 'minutes', or 'hours'.",
            enum=["seconds", "minutes", "hours"],
            enum_options=[
                EnumOption(
                    value="seconds", label="Seconds", description="Time in seconds"
                ),
                EnumOption(
                    value="minutes", label="Minutes", description="Time in minutes"
                ),
                EnumOption(value="hours", label="Hours", description="Time in hours"),
            ],
        ),
        "reset_on_emit": ConfigFieldSpec(
            name="reset_on_emit",
            display_name="Reset After Emit",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether to reset the internal timer after reaching the limit.",
            advance=True,
        ),
        "message": ConfigFieldSpec(
            name="message",
            display_name="Release Message",
            type_hint="text",
            required=False,
            description="Optional text sent downstream once the time limit is reached.",
            advance=True,
        ),
        "passthrough": ConfigFieldSpec(
            name="passthrough",
            display_name="Passthrough Mode",
            type_hint="bool",
            required=False,
            default=False,
            description="If true, after emitting the limit message, all subsequent inputs pass through unchanged.",
            advance=True,
        ),
    }
