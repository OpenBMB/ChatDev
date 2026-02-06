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
- **Workspace scanning**: Before/after snapshots to detect files created/modified/deleted by Claude Code
- **Prompt building**: Maps ChatDev tool specs to Claude Code's native tools, includes workspace info

### 2. Agent Config Extensions (`entity/configs/node/agent.py`)

- `workspace_root`: Runtime attribute — set dynamically by executor, points to `code_workspace/`
- `persistent_session: bool = True`: Config flag (for future use)
- `skip_memory: bool = False`: Config flag to bypass ChatDev's memory system (for future use)

### 3. Agent Executor Integration (`runtime/node/executor/agent_executor.py`)

- Passes `workspace_root` from `global_state["python_workspace_root"]` to provider config
- **Synthetic tool logs**: After Claude Code finishes, emits `claude:Write`, `claude:Edit`, `claude:Delete` log entries based on workspace diff — so the logging system records file operations

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
| Synthetic tool logs in session log | ✅ Working |
| Multi-agent workflow (Programmer → Code Reviewer → Programmer) | ✅ Working |
| Claude Code running tests autonomously | ✅ Working |
| Token usage tracking | ✅ Working |

## Known Issues / Remaining Work

### 1. Tool Activity & Generated Code Not Visible in UI (HIGH PRIORITY)

**Problem**: In the previous API-based flow, when an agent called `save_file` or `read_file_segment`, the UI displayed these tool calls in real-time **and** showed the generated source code files. With Claude Code provider, tools are used internally by Claude and ChatDev's `ToolManager` is completely bypassed.

**Current state**:
- Agent chat messages (what each agent said) **do** appear in the UI
- Tool calls (file write/edit/delete operations) **do NOT** appear in the UI activity feed
- Generated source code files **are NOT** browsable from the UI — they exist only on disk at `WareHouse/session_<id>/code_workspace/`
- Synthetic tool logs (`claude:Write`, etc.) are emitted to session log files, but the UI doesn't pick them up

**Verified in end-to-end test**: A full workflow ran successfully (Programmer → Code Reviewer → Programmer Code Review → CEO Manual Review). All files were created correctly on disk (`main.py`, `test_calculator.py`, `manual.md`, `README.md`), code review feedback was applied (files merged into single file), tests passed — but the UI only showed agent messages, not the file operations or generated code.

**What needs to happen**:
- (a) The UI should display synthetic tool logs (`claude:Write`, `claude:Edit`, `claude:Delete`) in the activity feed — these are already in the session log with `"synthetic": true` flag
- (b) The UI should allow browsing/viewing files in `code_workspace/` — perhaps by reading the `file_changes` from the log or scanning the workspace directory
- (c) For real-time tool visibility, consider switching to `--output-format stream-json` instead of `--output-format json` to get tool use events as they happen, parse them, and emit them via WebSocket

### 2. `firebase-debug.log` Pollution

**Problem**: Firebase MCP server creates `firebase-debug.log` in the CWD (workspace). The workspace scanner picks it up as a `claude:Write` artifact.

**Fix**: Either add `firebase-debug.log` to the exclude list in `_snapshot_workspace()`, or disable Firebase MCP for Claude Code subprocess calls.

### 3. ChatDev ToolManager Completely Bypassed

**Problem**: ChatDev has a rich tool system (`ToolManager`, `FunctionCallingProvider`, file tools like `save_file`, `read_file_segment`). With Claude Code, none of these are used — Claude uses its own built-in tools.

**Implications**:
- Tool-level logging/metrics from ToolManager don't apply
- Any custom tools defined in YAML `tooling` config are mapped to prompt guidance only (not actual function calls)
- `WorkspaceArtifactHook` in `graph.py` still works (it does its own before/after file scanning)

**This may be acceptable** — Claude Code's native tools are more capable than ChatDev's tool wrappers. But if specific ChatDev tools are needed (e.g., custom API integrations), a hybrid approach would need to be designed.

### 4. Memory System Bypass (OPTIONAL)

`skip_memory: true` config is defined but not yet wired up in executor. When `provider: claude-code` and `skip_memory: true`, the executor should skip `_apply_memory_retrieval()`. This is optional since Claude Code maintains its own context via `--resume`.

### 5. Session Timeout Handling

Claude Code sessions may expire after some time. Currently, if `--resume` fails, the error is returned as-is. Should add fallback logic: if resume fails, start a new session automatically.

### 6. Cost Tracking

Claude Code returns `total_cost_usd` in response. This is tracked but not prominently displayed. May want to aggregate costs per workflow run.

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
    │       ├── subprocess.run(["claude", "-p", prompt, ...], cwd=workspace)
    │       ├── Parse JSON response (session_id, result, usage)
    │       ├── Workspace diff (before/after snapshot)
    │       └── Return ModelResponse
    │   ↓
    │   Emit synthetic tool logs (claude:Write, claude:Edit, claude:Delete)
    │
    └── provider == "openai" / "anthropic"?
        ↓ YES
        Traditional API-based flow with ToolManager
```

## File Map

```
runtime/node/agent/providers/
├── claude_code_provider.py    ← Main provider (450+ lines)
├── base.py                    ← ModelProvider base class
├── openai_compatible.py       ← OpenAI/Anthropic API provider
└── response.py                ← ModelResponse dataclass

runtime/node/executor/
└── agent_executor.py          ← Lines 141-148: Claude Code synthetic logs
                               ← Lines 486-530: _emit_claude_code_file_changes()

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
