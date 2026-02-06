# Claude Code Integration — Handoff Document

## Repo & Branch

```bash
git clone https://github.com/mytsx/ChatDev.git
cd ChatDev
git checkout feature/claude-code-persistent-session
```

## Vision

ChatDev 2.0 (DevAll) uses LLM providers (OpenAI, etc.) via API keys. This branch adds **Claude Code CLI** (`claude -p`) as a native provider, leveraging the user's **Claude Max subscription** instead of requiring a separate API key.

The key advantage: Claude Code runs in its own **agentic mode** with built-in tools (Write, Edit, Read, Bash), which means it can autonomously write code, run tests, create virtual environments — all without ChatDev's traditional tool-calling pipeline.

## What's Been Implemented

### 1. Claude Code Provider (`runtime/node/agent/providers/claude_code_provider.py`)

- Calls `claude -p <prompt> --output-format json --dangerously-skip-permissions` via subprocess
- **Persistent sessions**: First call gets a `session_id` from response, subsequent calls use `--resume <session_id>` to maintain context
- **Thread-safe session storage**: Class-level `Dict[str, str]` with `threading.Lock` for `node_id → session_id` mapping
- **CWD-based file creation**: `subprocess.run(cwd=workspace_root)` so Claude's Write tool saves files in the correct workspace directory
- **Workspace scanning**: Before/after snapshots to detect files created/modified/deleted by Claude Code. Excludes `firebase-debug.log`, `.DS_Store` and similar OS artifacts
- **Prompt building**: Maps ChatDev tool specs to Claude Code's native tools, includes workspace info
- **Session timeout recovery**: If `--resume` fails (expired/invalid session), automatically retries with a fresh session

### 2. Agent Config Extensions (`entity/configs/node/agent.py`)

- `workspace_root`: Runtime attribute — set dynamically by executor, points to `code_workspace/`
- `persistent_session: bool = True`: Config flag (for future use)
- `skip_memory: bool = False`: Config flag to bypass ChatDev's memory system (for future use)

### 3. Agent Executor Integration (`runtime/node/executor/agent_executor.py`)

- Passes `workspace_root` from `global_state["python_workspace_root"]` to provider config
- **Synthetic tool logs**: After Claude Code finishes, emits `claude:Write`, `claude:Edit`, `claude:Delete` log entries with both `BEFORE` and `AFTER` stages — so the UI can show loading indicators and completion states
- **File attachments**: Generated/modified files are read from disk, base64-encoded, and attached to the response message as `MessageBlock(type="artifact")` with `AttachmentRef` — this makes files browsable in the UI

### 4. Circular Import Fix (`runtime/sdk.py`)

- `ClaudeCodeProvider.clear_all_sessions()` call uses lazy import to avoid circular dependency

### 5. Example YAML (`yaml_instance/ChatDev_v1_claude.yaml`)

- Full ChatDev workflow config with all agents using `provider: claude-code`

## What's Working

| Feature | Status |
|---------|--------|
| Claude Code as LLM provider | ✅ Working |
| File creation in workspace | ✅ Working (via `--dangerously-skip-permissions`) |
| Persistent sessions (`--resume`) | ✅ Working |
| Session isolation per agent node | ✅ Working |
| Workspace diff (detect file changes) | ✅ Working |
| Synthetic tool logs in session log | ✅ Working (BEFORE + AFTER stages) |
| Generated files attached to messages | ✅ Working (base64 data URI attachments) |
| Multi-agent workflow (Programmer → Code Reviewer → Programmer) | ✅ Working |
| Claude Code running tests autonomously | ✅ Working |
| Token usage tracking | ✅ Working |
| Session timeout recovery (auto-retry) | ✅ Working |
| Workspace scan excludes OS/debug artifacts | ✅ Working |

## Known Issues / Remaining Work

### 1. Real-Time Tool Activity Streaming (ENHANCEMENT)

**Current state**: Tool activity (file writes, edits, deletes) is logged **after** Claude Code finishes execution. Synthetic tool logs with BEFORE/AFTER stages are emitted, and generated files are attached to messages as artifacts.

**What could be improved**: For real-time tool visibility during long-running agent tasks, consider switching to `--output-format stream-json` instead of `--output-format json`. This would allow:
- Parsing tool use events as they happen (Write, Edit, Read, Bash)
- Emitting them via WebSocket to the UI in real-time
- Showing a live activity feed instead of a post-execution summary

**Implementation hint**: The `_parse_cli_output()` method already handles stream-mode JSON (line-by-line parsing). The change would be in `call_model()` — use `subprocess.Popen` instead of `subprocess.run` and parse stdout line-by-line.

### 2. ChatDev ToolManager Completely Bypassed

**Problem**: ChatDev has a rich tool system (`ToolManager`, `FunctionCallingProvider`, file tools like `save_file`, `read_file_segment`). With Claude Code, none of these are used — Claude uses its own built-in tools.

**Implications**:
- Tool-level logging/metrics from ToolManager don't apply
- Any custom tools defined in YAML `tooling` config are mapped to prompt guidance only (not actual function calls)
- `WorkspaceArtifactHook` in `graph.py` still works (it does its own before/after file scanning)

**This may be acceptable** — Claude Code's native tools are more capable than ChatDev's tool wrappers. But if specific ChatDev tools are needed (e.g., custom API integrations), a hybrid approach would need to be designed.

### 3. Memory System Bypass (OPTIONAL)

`skip_memory: true` config is defined but not yet wired up in executor. When `provider: claude-code` and `skip_memory: true`, the executor should skip `_apply_memory_retrieval()`. This is optional since Claude Code maintains its own context via `--resume`.

### 4. Cost Tracking Display

Claude Code returns `total_cost_usd` in response. This is tracked in token usage metadata but not prominently displayed. May want to aggregate costs per workflow run and show in UI.

## Resolved Issues

These were previously known issues that have been fixed:

### ✅ Tool Activity & Generated Code Not Visible in UI (RESOLVED)

**Was**: Synthetic tool logs existed in session logs but UI didn't pick them up. Generated files were only on disk.

**Fix**:
- Synthetic tool logs now emit both `BEFORE` and `AFTER` stages via `record_tool_call()` with proper `CallStage` — enabling UI loading indicators
- Generated/modified files are now attached to response messages as base64 data URI attachments with `AttachmentRef` and `MessageBlock(type="artifact")` — making them browsable in the UI
- See `agent_executor.py` → `_emit_claude_code_file_changes()`

### ✅ `firebase-debug.log` Pollution (RESOLVED)

**Was**: Firebase MCP server created `firebase-debug.log` in workspace, picked up as `claude:Write` artifact.

**Fix**: Added `_SCAN_EXCLUDE_FILES` frozenset in `claude_code_provider.py` that filters out `firebase-debug.log`, `.DS_Store`, `Thumbs.db`, `desktop.ini` from workspace scanning.

### ✅ Session Timeout Handling (RESOLVED)

**Was**: If `--resume` failed on an expired session, the error was returned as-is.

**Fix**: Added retry logic in `call_model()` — if `--resume` returns an error containing "session" or "resume", the session is cleared and the command is retried without `--resume` flag (fresh session).

## Technical Challenges We Encountered (and Solved)

### Challenge 1: `--tools ""` Disables Built-in Tools
**What happened**: We initially passed `--tools ""` thinking it would prevent tool output from polluting the response. Instead, it **disabled all of Claude Code's built-in tools** (Write, Edit, Read, Bash), making it unable to create files.
**Fix**: Removed `--tools ""` entirely.

### Challenge 2: `--json-schema` Causes Structured Output Failures
**What happened**: We tried using `--json-schema` to force Claude to return tool calls in a structured format matching ChatDev's `ToolCallPayload`. Claude failed with "Failed to provide valid structured output after 5 attempts."
**Fix**: Removed `--json-schema`. Embraced Claude Code's native tool mode instead of trying to force ChatDev's tool-calling format.

### Challenge 3: Permission Prompts Block Non-Interactive Mode
**What happened**: Claude Code's `-p` (pipe) mode still requires tool permissions. Without pre-approval, Write/Edit/Read/Bash tools block on permission prompts, producing empty output.
**Fix**: Added `--dangerously-skip-permissions` flag. Alternative: `--allowedTools Write Edit Read Bash` for more granular control.

### Challenge 4: Files Created in Wrong Directory
**What happened**: Claude Code's Write tool uses absolute paths by default. Files were being created in random locations instead of the project workspace.
**Fix**: Set `cwd=workspace_root` in `subprocess.run()` and instructed Claude via prompt to use relative paths.

### Challenge 5: Circular Import
**What happened**: `runtime/sdk.py` imports from `check.check` which imports from `runtime.sdk`, creating a circular dependency when adding `ClaudeCodeProvider.clear_all_sessions()`.
**Fix**: Lazy import — moved the import inside the function body.

## Architecture Overview

```
User Request (UI)
    ↓
server_main.py (FastAPI)
    ↓
runtime/sdk.py → run_workflow()
    ↓
Graph Execution Engine (runtime/graph.py)
    ↓
AgentNodeExecutor (runtime/node/executor/agent_executor.py)
    ↓
    ├── provider == "claude-code"?
    │   ↓ YES
    │   ClaudeCodeProvider.call_model()
    │       ├── Build prompt (system + conversation + tool mapping)
    │       ├── Check for existing session (--resume)
    │       ├── If resume fails → retry with fresh session
    │       ├── subprocess.run(["claude", "-p", prompt, ...], cwd=workspace)
    │       ├── Parse JSON response (session_id, result, usage)
    │       ├── Workspace diff (before/after snapshot, excludes OS artifacts)
    │       └── Return ModelResponse
    │   ↓
    │   _emit_claude_code_file_changes():
    │       ├── Emit BEFORE/AFTER tool logs (claude:Write, claude:Edit, claude:Delete)
    │       └── Attach generated files to response message as artifacts
    │
    └── provider == "openai" / "anthropic"?
        ↓ YES
        Traditional API-based flow with ToolManager
```

## File Map

```
runtime/node/agent/providers/
├── claude_code_provider.py    ← Main provider (~500 lines)
│   ├── Session management (get/set/clear with threading.Lock)
│   ├── call_model() with --resume support + timeout recovery
│   ├── _build_prompt() with is_continuation optimization
│   ├── _snapshot_workspace() / _diff_workspace() for file change detection
│   └── _SCAN_EXCLUDE_FILES for filtering OS/debug artifacts
├── base.py                    ← ModelProvider base class
├── openai_compatible.py       ← OpenAI/Anthropic API provider
└── response.py                ← ModelResponse dataclass

runtime/node/executor/
└── agent_executor.py
    ├── Lines ~141-148: Claude Code integration hook
    └── _emit_claude_code_file_changes():
        ├── BEFORE/AFTER stage tool logs
        └── File attachment as base64 data URI artifacts

entity/configs/node/
└── agent.py                   ← workspace_root, persistent_session, skip_memory

runtime/
└── sdk.py                     ← Lazy import for circular dependency fix

yaml_instance/
└── ChatDev_v1_claude.yaml     ← Example workflow config
```

## How to Test

```bash
# 1. Start backend
uv run python server_main.py --port 6400

# 2. From UI, create a new session using "ChatDev_v1_claude" workflow

# 3. Enter a task like: "Build a Python calculator that can add, subtract, multiply and divide two numbers."

# 4. Check logs
ls -la logs/session_*.log

# 5. Check workspace output
ls -la WareHouse/session_<id>/code_workspace/
```

## Quick CLI Test (No UI Needed)

```bash
# Verify Claude Code works with skip-permissions
claude --dangerously-skip-permissions -p "Write a file called /tmp/test_hello.py with content: print('hello')" --output-format json --max-turns 3

# Check file was created
cat /tmp/test_hello.py
```

## Prerequisites

- Claude Code CLI installed (`claude` in PATH)
- Claude Max subscription (no API key needed)
- Python 3.12+ with `uv`
- Node.js (for DevAll frontend)
