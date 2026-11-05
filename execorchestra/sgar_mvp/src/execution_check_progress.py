"""Track explicitly delegated command checks against real Tool observations.

This extracts only imperative, quoted commands already supplied by the user.
It grants no Tool authority and never dispatches commands itself.
"""
import re
import shlex
from typing import Any, Mapping, Sequence

from .pipeline_control import canonical_sha256


def explicit_command_checks(text: str) -> tuple[dict[str, str], ...]:
    result = []
    seen = set()
    pattern = re.compile(
        r"\b(?:run|running|execute|executing|invoke|invoking|re-run|rerun)\s+"
        r"(?:exactly\s+|the command\s+)?"
        r"(?:`([^`\r\n]+)`|\"([^\"\r\n]+)\"|'([^'\r\n]+)')", re.IGNORECASE,
    )
    for match in pattern.finditer(str(text or "")):
        prefix = str(text)[max(0, match.start()-80):match.start()]
        # Optional suggestions and prohibitions are not mandatory actions.
        if re.search(r"(?:do not|don't|must not|never|optional|for example|e\.g\.|if needed)\s*$"
                     r"|\b(?:may|can|could)\s+(?:\w+\s+){0,6}$",
                     prefix, re.IGNORECASE):
            continue
        command = next(value for value in match.groups() if value is not None).strip()
        if not command or command in seen:
            continue
        seen.add(command)
        result.append({"check_id": canonical_sha256(command), "command": command,
                       "source_quote": match.group(0)})
    return tuple(result)


def _tokens(script: str) -> list[str]:
    lexer = shlex.shlex(script, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def standalone_check_command(script: str, command: str) -> bool:
    """Accept a direct invocation or cwd binding followed by that invocation.

    A larger script may skip a check or hide its exit status in a pipeline.
    It is not used as machine evidence for a separate explicit command.
    """
    try:
        actual, expected = _tokens(script), _tokens(command)
    except ValueError:
        return False
    if actual == expected:
        return True
    if len(actual) > 3 and actual[0] == "cd" and actual[2] == "&&":
        return actual[3:] == expected
    return False


class ExplicitCheckProgress:
    def __init__(self, *, original_request: str, task_instruction: str,
                 callable_tools: Sequence[Any]) -> None:
        original = {item["command"]: item for item in explicit_command_checks(original_request)}
        delegated = {item["command"] for item in explicit_command_checks(task_instruction)}
        self.checks = tuple(item for command, item in original.items() if command in delegated)
        self.tools = {item.callable_id: item for item in callable_tools
                      if str(item.capability_operation_id).rsplit("::", 1)[-1]
                      == "execute_shell_commands"}
        if not self.tools:
            self.checks = ()
        self.records: dict[str, dict[str, Any]] = {}

    def observe(self, intent: Any, invocation: Any, observation_id: str) -> None:
        tool = self.tools.get(intent.callable_id)
        if tool is None:
            return
        arguments = dict(intent.normalized_dynamic_arguments)
        # Runtime-fixed arguments retain authority over model-supplied values.
        for name, binding in getattr(tool, "fixed_input_bindings", {}).items():
            if isinstance(binding, Mapping) and "literal" in binding:
                arguments[name] = binding["literal"]
        script = arguments.get("script")
        if not isinstance(script, str):
            return
        for check in self.checks:
            if standalone_check_command(script, check["command"]):
                self.records[check["check_id"]] = {
                    "check_id": check["check_id"], "observation_id": observation_id,
                    "observation_sha256": invocation.observation.observation_sha256,
                    "status": invocation.observation.status,
                    "arguments_sha256": intent.dynamic_arguments_sha256,
                }

    def pending(self) -> tuple[dict[str, str], ...]:
        return tuple(item for item in self.checks if item["check_id"] not in self.records)

    def projection(self) -> dict[str, Any]:
        return {
            "required_checks": list(self.checks),
            "observed_checks": list(self.records.values()),
            "pending_checks": list(self.pending()),
            "rule": (
                "After dependent task work, execute each pending check through the selected Tool. "
                "Use a separate invocation in the correct working directory so its actual "
                "exit status is observed. A request or file write is not an executed check. "
                "Observed does not mean passed or still valid after later changes: assess the "
                "actual result against the original criterion. Diagnostic commands with expected "
                "nonzero outcomes do not alone prove implementation failure."
            ),
        }
