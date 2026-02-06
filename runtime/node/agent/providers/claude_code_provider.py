"""Claude Code provider implementation.

Uses the Claude Code CLI (claude -p) as the LLM backend, leveraging the user's
Max subscription instead of requiring a separate API key.

Tool calling is handled via --json-schema, which forces Claude to output
structured JSON with a response field and a tool_calls array.
"""

import hashlib
import json
import os
import subprocess
import shutil
import threading
from typing import Any, Dict, List, Optional

from entity.configs import AgentConfig
from entity.messages import (
    Message,
    MessageRole,
    ToolCallPayload,
)
from entity.tool_spec import ToolSpec
from runtime.node.agent import ModelProvider, ModelResponse
from utils.token_tracker import TokenUsage


# JSON schema used when tools are available.
# Forces Claude to output structured JSON with tool_calls.
_TOOL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {
            "type": "string",
            "description": "Your text response. Empty string if calling tools.",
        },
        "tool_calls": {
            "type": "array",
            "description": "Tool calls to make. Empty array if just responding with text.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["name", "arguments"],
            },
        },
    },
    "required": ["response", "tool_calls"],
}


class ClaudeCodeProvider(ModelProvider):
    """Provider that uses Claude Code CLI (claude -p) as the LLM backend.

    This provider calls the `claude` binary via subprocess, using the user's
    Max subscription. No ANTHROPIC_API_KEY is needed.

    Supports persistent sessions via --resume flag, allowing context to be
    preserved across multiple calls for the same agent node.
    """

    # Thread-safe session storage: node_id -> session_id
    _sessions: Dict[str, str] = {}
    _sessions_lock = threading.Lock()

    @classmethod
    def get_session(cls, node_id: str) -> Optional[str]:
        """Get existing session ID for a node."""
        with cls._sessions_lock:
            return cls._sessions.get(node_id)

    @classmethod
    def set_session(cls, node_id: str, session_id: str) -> None:
        """Store session ID for a node."""
        with cls._sessions_lock:
            cls._sessions[node_id] = session_id

    @classmethod
    def clear_session(cls, node_id: str) -> None:
        """Clear session for a specific node."""
        with cls._sessions_lock:
            cls._sessions.pop(node_id, None)

    @classmethod
    def clear_all_sessions(cls) -> None:
        """Clear all sessions (call when workflow completes)."""
        with cls._sessions_lock:
            cls._sessions.clear()

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._claude_binary = self._find_claude_binary()
        self._model_flag = self._resolve_model_flag()

    def _find_claude_binary(self) -> str:
        """Locate the claude binary."""
        path = shutil.which("claude")
        if path:
            return path
        for candidate in [
            "/usr/local/bin/claude",
            "/opt/homebrew/bin/claude",
            os.path.expanduser("~/.local/bin/claude"),
        ]:
            if os.path.isfile(candidate):
                return candidate
        raise FileNotFoundError(
            "Claude Code CLI not found. Install it or ensure 'claude' is in PATH."
        )

    def _resolve_model_flag(self) -> Optional[str]:
        """Map model name to claude CLI --model flag."""
        name = (self.model_name or "").lower().strip()
        if not name or name in ("claude", "default"):
            return None
        # claude CLI accepts: sonnet, opus, haiku, or full model IDs
        if name in ("sonnet", "opus", "haiku"):
            return name
        if "opus" in name:
            return "opus"
        if "sonnet" in name:
            return "sonnet"
        if "haiku" in name:
            return "haiku"
        return name

    def create_client(self):
        """Return the claude binary path as the 'client'."""
        return self._claude_binary

    def call_model(
        self,
        client: str,
        conversation: List[Message],
        timeline: List[Any],
        tool_specs: Optional[List[ToolSpec]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Call Claude Code CLI with the conversation and tool specs.

        When tool_specs are provided, uses --json-schema to get structured
        output with tool_calls. Otherwise, returns plain text.

        Supports persistent sessions via --resume flag when node_id is available.
        """
        has_tools = bool(tool_specs)
        node_id = getattr(self.config, "node_id", None)

        # Check for existing session
        existing_session = self.get_session(node_id) if node_id else None
        is_continuation = existing_session is not None

        # Build prompt (simplified for continuations)
        prompt = self._build_prompt(conversation, tool_specs, is_continuation=is_continuation)

        cmd = [client, "-p", prompt, "--output-format", "json"]

        # Disable Claude Code's own tools - we only want LLM text output
        cmd.extend(["--tools", ""])

        # Resume existing session or start new one
        if existing_session:
            cmd.extend(["--resume", existing_session])
            # Allow more turns for ongoing sessions since context grows
            cmd.extend(["--max-turns", "5"])
        else:
            # Allow 3 turns so --json-schema can work (needs 2 turns internally)
            cmd.extend(["--max-turns", "3"])

        if self._model_flag:
            cmd.extend(["--model", self._model_flag])

        if has_tools:
            cmd.extend(["--json-schema", json.dumps(_TOOL_RESPONSE_SCHEMA)])

        timeout = kwargs.pop("timeout", 300)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ModelResponse(
                message=Message(
                    role=MessageRole.ASSISTANT,
                    content="[Error: Claude Code CLI timed out]",
                ),
                raw_response={"error": "timeout"},
            )

        raw_response = self._parse_cli_output(result)
        self._track_token_usage(raw_response)

        # Save session ID for future calls (persistent session support)
        new_session_id = raw_response.get("session_id")
        if new_session_id and node_id:
            self.set_session(node_id, new_session_id)

        if has_tools:
            return self._parse_structured_response(raw_response)
        else:
            return self._parse_text_response(raw_response, result)

    def extract_token_usage(self, response: Any) -> TokenUsage:
        """Extract token usage from Claude Code CLI JSON response."""
        if not isinstance(response, dict):
            return TokenUsage()

        usage = response.get("usage", {}) or {}
        cost = response.get("total_cost_usd", 0) or 0

        # Try modelUsage for detailed per-model breakdown
        model_usage = response.get("modelUsage", {})
        if model_usage and not usage.get("input_tokens"):
            for _model, stats in model_usage.items():
                input_tokens = stats.get("inputTokens", 0)
                output_tokens = stats.get("outputTokens", 0)
                return TokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    metadata={"total_cost_usd": cost, **stats},
                )

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            metadata={"total_cost_usd": cost},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _track_token_usage(self, raw_response: dict) -> None:
        """Record token usage if a tracker is attached."""
        token_tracker = getattr(self.config, "token_tracker", None)
        if not token_tracker:
            return

        usage = self.extract_token_usage(raw_response)
        node_id = getattr(self.config, "node_id", "ALL")
        usage.node_id = node_id
        usage.model_name = self.model_name
        usage.workflow_id = token_tracker.workflow_id
        usage.provider = "claude-code"

        token_tracker.record_usage(
            node_id, self.model_name, usage, provider="claude-code"
        )

    def _build_prompt(
        self,
        conversation: List[Message],
        tool_specs: Optional[List[ToolSpec]],
        is_continuation: bool = False,
    ) -> str:
        """Build a single prompt string from conversation messages.

        The system message becomes a preamble, user/assistant/tool messages
        are serialized with role prefixes.

        When is_continuation=True (resuming an existing session), the prompt
        is simplified since system instructions and prior context are already
        in Claude's memory. Only new user/tool messages are sent.
        """
        parts: List[str] = []

        if is_continuation:
            # For continuations, only include new messages (skip system prompt)
            # System instructions are already in the session context
            for msg in conversation:
                text = msg.text_content()
                if msg.role == MessageRole.USER:
                    parts.append(f"[User]:\n{text}")
                elif msg.role == MessageRole.TOOL:
                    tool_name = msg.metadata.get("tool_name", "unknown")
                    call_id = msg.tool_call_id or "unknown"
                    parts.append(
                        f"[Tool Result for '{tool_name}' (call_id: {call_id})]:\n{text}"
                    )
                # Skip SYSTEM and ASSISTANT for continuations - they're in context
        else:
            # Full prompt for new sessions
            for msg in conversation:
                text = msg.text_content()
                if msg.role == MessageRole.SYSTEM:
                    parts.append(f"[System Instructions]:\n{text}")
                elif msg.role == MessageRole.USER:
                    parts.append(f"[User]:\n{text}")
                elif msg.role == MessageRole.ASSISTANT:
                    parts.append(f"[Assistant]:\n{text}")
                elif msg.role == MessageRole.TOOL:
                    tool_name = msg.metadata.get("tool_name", "unknown")
                    call_id = msg.tool_call_id or "unknown"
                    parts.append(
                        f"[Tool Result for '{tool_name}' (call_id: {call_id})]:\n{text}"
                    )

        # Include tool specs on first call only (they persist in session)
        if tool_specs and not is_continuation:
            parts.append(self._format_tool_specs(tool_specs))

        return "\n\n".join(parts)

    def _format_tool_specs(self, tool_specs: List[ToolSpec]) -> str:
        """Format tool specs into a prompt section."""
        lines = [
            "[Available Tools]:",
            "You can call tools by including them in the tool_calls array.",
            "If you don't need to call any tool, set tool_calls to an empty array [].",
            "If calling tools, set response to empty string.",
            "",
        ]
        for spec in tool_specs:
            params_str = json.dumps(
                spec.parameters or {"type": "object", "properties": {}},
                indent=2,
            )
            lines.append(f"- **{spec.name}**: {spec.description}")
            lines.append(f"  Parameters: {params_str}")
            lines.append("")
        return "\n".join(lines)

    def _parse_structured_response(self, raw_response: dict) -> ModelResponse:
        """Parse structured JSON output (when tools were available)."""
        structured = raw_response.get("structured_output")

        if not structured:
            # Fallback: try to parse result text as JSON
            result_text = raw_response.get("result", "")
            if result_text:
                try:
                    structured = json.loads(result_text)
                except (json.JSONDecodeError, TypeError):
                    pass

        if not structured:
            # No structured output - return plain text
            fallback_text = raw_response.get("result", "")
            if not fallback_text:
                errors = raw_response.get("errors", [])
                fallback_text = (
                    f"[Claude Code Error]: {errors}" if errors else ""
                )
            return ModelResponse(
                message=Message(
                    role=MessageRole.ASSISTANT, content=fallback_text
                ),
                raw_response=raw_response,
            )

        response_text = structured.get("response", "")
        raw_tool_calls = structured.get("tool_calls", [])

        tool_calls: List[ToolCallPayload] = []
        for idx, tc in enumerate(raw_tool_calls):
            name = tc.get("name", "")
            if not name:
                continue
            arguments = tc.get("arguments", {})
            arguments_str = (
                json.dumps(arguments, ensure_ascii=False)
                if isinstance(arguments, dict)
                else str(arguments)
            )
            call_id = self._build_tool_call_id(
                name, arguments_str, fallback_prefix=f"cc_call_{idx}"
            )
            tool_calls.append(
                ToolCallPayload(
                    id=call_id,
                    function_name=name,
                    arguments=arguments_str,
                    type="function",
                )
            )

        return ModelResponse(
            message=Message(
                role=MessageRole.ASSISTANT,
                content=response_text,
                tool_calls=tool_calls,
            ),
            raw_response=raw_response,
        )

    def _parse_text_response(
        self, raw_response: dict, result: subprocess.CompletedProcess
    ) -> ModelResponse:
        """Parse plain text response (no tools mode)."""
        response_text = raw_response.get("result", "")
        if not response_text and result.stderr:
            response_text = f"[Claude Code Error]: {result.stderr[:500]}"
        return ModelResponse(
            message=Message(role=MessageRole.ASSISTANT, content=response_text),
            raw_response=raw_response,
        )

    def _build_tool_call_id(
        self,
        function_name: str,
        arguments: str,
        *,
        fallback_prefix: str = "tool_call",
    ) -> str:
        base = function_name or fallback_prefix
        payload = f"{base}:{arguments or ''}".encode("utf-8")
        digest = hashlib.md5(payload).hexdigest()[:8]
        return f"{base}_{digest}"

    def _parse_cli_output(self, result: subprocess.CompletedProcess) -> dict:
        """Parse the JSON output from claude CLI."""
        stdout = result.stdout or ""
        if not stdout.strip():
            return {
                "result": "",
                "error": result.stderr or "empty response",
                "returncode": result.returncode,
            }

        # Single JSON object (normal --output-format json)
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass

        # Stream mode: try last result-type line
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict) and parsed.get("type") == "result":
                    return parsed
            except json.JSONDecodeError:
                continue

        return {"result": stdout.strip(), "type": "text_fallback"}
