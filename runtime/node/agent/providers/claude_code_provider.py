"""Claude Code provider implementation.

Uses the Claude Code CLI (claude -p) as the LLM backend, leveraging the user's
Max subscription instead of requiring a separate API key.

Claude Code works in its native agentic mode, using its own built-in tools
(Write, Edit, Read, Bash) to accomplish tasks like writing code, running tests,
etc. The provider returns the text result from Claude's work.
"""

import json
import os
import subprocess
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from entity.configs import AgentConfig
from entity.messages import (
    Message,
    MessageRole,
)
from entity.tool_spec import ToolSpec
from runtime.node.agent import ModelProvider, ModelResponse
from utils.token_tracker import TokenUsage



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

        Claude Code works in native agentic mode — it uses its own built-in
        tools (Write, Edit, Read, Bash) to accomplish tasks. The working
        directory is set to the workspace root so files are created in the
        correct location.

        Supports persistent sessions via --resume flag when node_id is available.
        """
        node_id = getattr(self.config, "node_id", None)
        workspace_root = getattr(self.config, "workspace_root", None)

        # Check for existing session
        existing_session = self.get_session(node_id) if node_id else None
        is_continuation = existing_session is not None

        # Build prompt (simplified for continuations)
        prompt = self._build_prompt(
            conversation, tool_specs,
            is_continuation=is_continuation,
            workspace_root=workspace_root,
        )

        cmd = [client, "-p", prompt, "--output-format", "json"]

        # Skip all permission checks for non-interactive mode.
        # Without this, -p mode blocks on permission prompts and produces
        # empty output.
        cmd.append("--dangerously-skip-permissions")

        # Resume existing session or start new one
        if existing_session:
            cmd.extend(["--resume", existing_session])
            cmd.extend(["--max-turns", "20"])
        else:
            cmd.extend(["--max-turns", "15"])

        if self._model_flag:
            cmd.extend(["--model", self._model_flag])

        # Set CWD to workspace root so Claude's file operations land in the
        # correct directory. Ensure the directory exists.
        cwd = None
        if workspace_root:
            ws_path = Path(workspace_root)
            ws_path.mkdir(parents=True, exist_ok=True)
            cwd = str(ws_path)

        # Snapshot workspace before Claude Code runs so we can diff afterwards
        before_snapshot = self._snapshot_workspace(cwd) if cwd else {}

        timeout = kwargs.pop("timeout", 600)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            if node_id and not existing_session:
                self.clear_session(node_id)
            return ModelResponse(
                message=Message(
                    role=MessageRole.ASSISTANT,
                    content="[Error: Claude Code CLI timed out]",
                ),
                raw_response={"error": "timeout"},
            )

        raw_response = self._parse_cli_output(result)
        self._track_token_usage(raw_response)

        # Diff workspace to detect files created/modified by Claude Code
        if cwd:
            after_snapshot = self._snapshot_workspace(cwd)
            raw_response["file_changes"] = self._diff_workspace(
                before_snapshot, after_snapshot,
            )

        # Save session ID for future calls (persistent session support)
        new_session_id = raw_response.get("session_id")
        if new_session_id and node_id:
            self.set_session(node_id, new_session_id)

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
        workspace_root: Optional[Any] = None,
    ) -> str:
        """Build a single prompt string from conversation messages.

        When is_continuation=True (resuming an existing session), the prompt
        is simplified since system instructions and prior context are already
        in Claude's memory. Only new user/tool messages are sent.
        """
        parts: List[str] = []

        if is_continuation:
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
        else:
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

        if tool_specs and not is_continuation:
            parts.append(self._format_tool_specs(tool_specs, workspace_root))

        if workspace_root and not is_continuation:
            parts.append(
                f"[Working Directory]: {workspace_root}\n"
                "Your current working directory is set to the project workspace above. "
                "All files you create with your Write tool will be saved there. "
                "Use relative paths (e.g. 'main.py', 'src/utils.py') for all file operations."
            )

        return "\n\n".join(parts)

    def _format_tool_specs(
        self, tool_specs: List[ToolSpec], workspace_root: Optional[Any] = None,
    ) -> str:
        """Format tool specs as guidance for Claude's native tools.

        Maps ChatDev tool capabilities to Claude Code's built-in tools so
        Claude knows what actions are expected and how to accomplish them.
        """
        # Build a mapping from ChatDev tools to Claude Code native actions
        tool_mappings: List[str] = []
        for spec in tool_specs:
            name = spec.name
            desc = spec.description or ""
            if "save_file" in name or "write" in name.lower():
                tool_mappings.append(
                    f"- {name}: {desc}\n"
                    "  -> Use your Write tool to create/save files with relative paths."
                )
            elif "read_file" in name or "read" in name.lower():
                tool_mappings.append(
                    f"- {name}: {desc}\n"
                    "  -> Use your Read tool to read file contents."
                )
            elif "run" in name.lower() or "exec" in name.lower() or "bash" in name.lower():
                tool_mappings.append(
                    f"- {name}: {desc}\n"
                    "  -> Use your Bash tool to execute commands."
                )
            else:
                tool_mappings.append(f"- {name}: {desc}")

        lines = [
            "[Task Capabilities — Native Tool Mapping]:",
            "You have built-in tools: Write, Edit, Read, Bash.",
            "The following tasks are expected. Use your tools directly to accomplish them:",
            "",
        ]
        lines.extend(tool_mappings)
        lines.append("")
        lines.append(
            "CRITICAL: Create all files using your Write tool with RELATIVE paths "
            "(e.g. 'main.py', not absolute paths). "
            "Your working directory is already set to the project workspace."
        )
        if workspace_root:
            lines.append(f"Workspace: {workspace_root}")
        return "\n".join(lines)

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

    # ------------------------------------------------------------------
    # Workspace scanning helpers
    # ------------------------------------------------------------------

    _SCAN_EXCLUDE_DIRS = frozenset({
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".mypy_cache", ".pytest_cache", "attachments",
    })

    def _snapshot_workspace(self, workspace_root: str) -> Dict[str, tuple]:
        """Take a lightweight snapshot of workspace files.

        Returns a dict of ``{relative_path: (size, mtime_ns)}``.
        """
        snapshot: Dict[str, tuple] = {}
        root = Path(workspace_root)
        if not root.exists():
            return snapshot

        for item in root.rglob("*"):
            if not item.is_file():
                continue
            rel = item.relative_to(root)
            # Skip hidden and excluded directories
            if any(
                part.startswith(".") or part in self._SCAN_EXCLUDE_DIRS
                for part in rel.parts[:-1]  # check parent dirs, not filename
            ):
                continue
            try:
                st = item.stat()
                snapshot[str(rel)] = (st.st_size, st.st_mtime_ns)
            except OSError:
                continue
        return snapshot

    @staticmethod
    def _diff_workspace(
        before: Dict[str, tuple],
        after: Dict[str, tuple],
    ) -> List[Dict[str, Any]]:
        """Compare two workspace snapshots and return a list of changes."""
        changes: List[Dict[str, Any]] = []
        for path, (size, mtime) in after.items():
            if path not in before:
                changes.append({"path": path, "change": "created", "size": size})
            elif before[path] != (size, mtime):
                changes.append({"path": path, "change": "modified", "size": size})
        for path in before:
            if path not in after:
                changes.append({"path": path, "change": "deleted", "size": 0})
        return changes

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
