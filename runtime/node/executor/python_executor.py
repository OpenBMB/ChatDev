"""Executor for Python code runner nodes."""

import os
import re
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List

from entity.configs import Node
from entity.configs.node.python_runner import PythonRunnerConfig
from entity.messages import Message, MessageRole
from runtime.node.executor.base import NodeExecutor


_CODE_BLOCK_RE = re.compile(r"```(?P<lang>[a-zA-Z0-9_+-]*)?\s*\n(?P<code>.*?)```", re.DOTALL)


@dataclass
class _ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int | None
    error: str | None = None


class PythonNodeExecutor(NodeExecutor):
    """Execute inline Python code passed to the node."""

    WORKSPACE_KEY = "python_workspace_root"
    COUNTER_KEY = "python_node_run_counters"

    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        if node.node_type != "python":
            raise ValueError(f"Node {node.id} is not a python node")

        workspace = self._ensure_workspace_root()
        last_message = inputs[-1] if inputs else None
        code_payload = self._extract_code(last_message)
        if not code_payload:
            return [self._build_failure_message(
                node,
                workspace,
                error_text="No executable code segment found",
            )]

        script_path = self._write_script_file(node, workspace, code_payload)
        config = node.as_config(PythonRunnerConfig)
        if not config:
            raise ValueError(f"Node {node.id} missing PythonRunnerConfig")

        result = self._run_process(config, script_path, workspace, node)
        metadata = {
            "workspace": str(workspace),
            "script_path": str(script_path),
        }
        if result.success:
            if result.stderr:
                self.log_manager.debug(
                    f"Python node {node.id} stderr", node_id=node.id, details={"stderr": result.stderr}
                )
            return [self._build_message(
                role=MessageRole.ASSISTANT,
                content=result.stdout,
                source=node.id,
                metadata=metadata,
            )]

        error_text = result.error or "Script execution failed"
        return [self._build_failure_message(
            node,
            workspace,
            error_text=error_text,
            exit_code=result.exit_code,
            stderr=result.stderr,
            script_path=script_path,
        )]

    def _ensure_workspace_root(self) -> Path:
        root = self.context.global_state.setdefault(self.WORKSPACE_KEY, None)
        if root is None:
            graph_dir = self.context.global_state.get("graph_directory")
            if not graph_dir:
                raise RuntimeError("graph_directory missing from execution context")
            root = (Path(graph_dir) / "code_workspace").resolve()
            root.mkdir(parents=True, exist_ok=True)
            self.context.global_state[self.WORKSPACE_KEY] = str(root)
        else:
            root = Path(root).resolve()
            root.mkdir(parents=True, exist_ok=True)
        return root

    def _extract_code(self, message: Message | None) -> str:
        if not message:
            return ""
        raw = message.text_content()
        if not raw or not raw.strip():
            return ""
        match = _CODE_BLOCK_RE.search(raw)
        code = match.group("code") if match else raw
        return textwrap.dedent(code).strip()

    def _write_script_file(self, node: Node, workspace: Path, code: str) -> Path:
        counters = self.context.global_state.setdefault(self.COUNTER_KEY, {})
        safe_node_id = re.sub(r"[^0-9A-Za-z_\-]", "_", node.id)
        run_count = counters.get(node.id, 0) + 1
        counters[node.id] = run_count
        suffix = f"_run-{run_count}" if run_count > 1 else ""
        filename = f"{safe_node_id}{suffix}.py"
        path = (workspace / filename).resolve()
        path.write_text(code + ("\n" if not code.endswith("\n") else ""), encoding="utf-8")
        return path

    def _run_process(
        self,
        config: PythonRunnerConfig,
        script_path: Path,
        workspace: Path,
        node: Node,
    ) -> _ExecutionResult:
        cmd = [config.interpreter]
        if config.args:
            cmd.extend(config.args)
        cmd.append(str(script_path))
        env = os.environ.copy()
        env.update(config.env or {})
        env.update(
            {
                "MAC_CODE_WORKSPACE": str(workspace),
                "MAC_CODE_SCRIPT": str(script_path),
                "MAC_NODE_ID": node.id,
            }
        )
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                check=False,
                timeout=config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return _ExecutionResult(
                success=False,
                stdout="",
                stderr=exc.stdout.decode(config.encoding, errors="replace") if exc.stdout else "",
                exit_code=None,
                error=f"Script did not finish within {config.timeout_seconds}s",
            )
        except FileNotFoundError:
            return _ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=None,
                error=f"Interpreter {config.interpreter} not found",
            )
        stdout = completed.stdout.decode(config.encoding, errors="replace")
        stderr = completed.stderr.decode(config.encoding, errors="replace")
        return _ExecutionResult(
            success=completed.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=completed.returncode,
        )

    def _build_failure_message(
        self,
        node: Node,
        workspace: Path,
        *,
        error_text: str,
        exit_code: int | None = None,
        stderr: str | None = None,
        script_path: Path | None = None,
    ) -> Message:
        metadata = {
            "workspace": str(workspace),
        }
        if script_path:
            metadata["script_path"] = str(script_path)
        if exit_code is not None:
            metadata["exit_code"] = exit_code
        if stderr:
            metadata["stderr"] = stderr

        content_lines = ["==CODE EXECUTION FAILED==", error_text]
        if exit_code is not None:
            content_lines.append(f"exit_code={exit_code}")
        if stderr:
            content_lines.append(f"stderr:\n{stderr}")

        return self._build_message(
            role=MessageRole.ASSISTANT,
            content="\n".join(content_lines),
            source=node.id,
            metadata=metadata,
        )

    # workspace hook handled via ExecutionContext.workspace_hook
