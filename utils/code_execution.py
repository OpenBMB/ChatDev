"""Server-controlled opt-in for running workflow-supplied code."""

import os

from utils.exceptions import SecurityError


UNSAFE_CODE_EXECUTION_ENV = "MAC_ALLOW_UNSAFE_CODE_EXECUTION"


def require_unsafe_code_execution(operation: str) -> None:
    # Never consult workflow variables, tool arguments, or child-process env overrides.
    enabled = os.environ.get(UNSAFE_CODE_EXECUTION_ENV, "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        raise SecurityError(
            f"{operation} is disabled. Running workflow-supplied code requires "
            f"{UNSAFE_CODE_EXECUTION_ENV}=1 in the server environment. "
            "Enable this only for trusted workflows; execution is not sandboxed.",
            details={"operation": operation},
        )
