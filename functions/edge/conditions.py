"""Edge condition helpers used by workflow YAML definitions."""

import re

def contains_keyword(data: str) -> bool:
    """Check if data contains the keyword 'trigger'."""
    return "trigger" in data.lower()

def length_greater_than_5(data: str) -> bool:
    """Check if data length is greater than 5."""
    return len(data) > 5

def always_false(data: str) -> bool:
    """Always return false for testing."""
    return False

def not_contains_keyword(data: str) -> bool:
    """Check if data contains the keyword 'trigger'."""
    return "trigger" not in data.lower()

def code_pass(data: str) -> bool:
    return "==CODE EXECUTION FAILED==" not in data

def code_fail(data: str) -> bool:
    return "==CODE EXECUTION FAILED==" in data

def _extract_verdict(data: str) -> str | None:
    """Parse `Verdict: CONTINUE|STOP` markers from agent outputs."""
    match = re.search(r"verdict\s*:\s*(\w+)", data, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper()


def need_reflection_loop(data: str) -> bool:
    """Return True when the Reasoner asks for another Reflexion iteration."""
    verdict = _extract_verdict(data)
    if verdict is None:
        return True  # Default to continuing until STOP is explicit
    return verdict not in {"STOP", "DONE"}


def should_stop_loop(data: str) -> bool:
    """Return True when the Reasoner signals the Reflexion loop can stop."""
    verdict = _extract_verdict(data)
    if verdict is None:
        return False
    return verdict in {"STOP", "DONE"}
