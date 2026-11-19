"""General utility function tools for model-invoked actions."""

import math
import os
import time
from datetime import UTC, datetime

DEFAULT_MAX_WAIT_SECONDS = float(os.getenv("MAX_WAIT_SECONDS", "300"))


def wait(seconds: float, max_seconds: float = DEFAULT_MAX_WAIT_SECONDS) -> str:
    """
    Wait for a specified number of seconds.

    Args:
        seconds (float): The number of seconds to wait. Must be non-negative and finite.
        max_seconds (float): Maximum allowed wait time in seconds. Defaults to 300 seconds.

    Returns:
        str: Confirmation message indicating the duration waited.
    """
    if isinstance(seconds, bool):
        raise TypeError("Wait duration must be a number, not a boolean")
    if seconds is None:
        raise TypeError("Wait duration cannot be None")

    if isinstance(seconds, str):
        stripped = seconds.strip()
        if not stripped:
            raise ValueError("Wait duration cannot be empty")
        try:
            val = float(stripped)
        except ValueError as exc:
            raise ValueError(f"Invalid wait duration: {seconds}") from exc
    elif isinstance(seconds, (int, float)):
        val = float(seconds)
    else:
        raise TypeError(f"Wait duration must be a number, got {type(seconds).__name__}")

    if math.isnan(val) or math.isinf(val):
        raise ValueError("Wait duration must be a finite number")

    if val < 0:
        raise ValueError(f"Wait duration must be non-negative, got {seconds}")

    if max_seconds is not None:
        if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)):
            raise TypeError("max_seconds must be a number")
        if math.isnan(max_seconds) or math.isinf(max_seconds) or max_seconds < 0:
            raise ValueError("max_seconds must be a non-negative finite number")
        if val > max_seconds:
            raise ValueError(
                f"Wait duration of {val}s exceeds the maximum limit of {max_seconds}s"
            )

    time.sleep(val)
    display_sec = int(val) if val.is_integer() else val
    return f"Successfully waited for {display_sec} second(s)."


def get_current_time(timezone: str = "local") -> str:
    """
    Get the current time in the format: YYYY-MM-DD HH:MM:SS.

    Args:
        timezone (str): Timezone for formatting, either 'local' or 'utc'. Defaults to 'local'.

    Returns:
        str: The current time in the format: YYYY-MM-DD HH:MM:SS.
    """
    if not isinstance(timezone, str):
        raise TypeError("timezone must be a string")

    tz = timezone.strip().lower()
    if tz == "utc":
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    elif tz == "local":
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    else:
        raise ValueError(f"Unsupported timezone '{timezone}'. Supported options are 'local' or 'utc'.")
