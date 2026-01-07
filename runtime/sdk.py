"""SDK helpers for executing workflows from Python code."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Union

from check.check import load_config
from entity.enums import LogLevel
from entity.graph_config import GraphConfig
from entity.messages import Message
from runtime.bootstrap.schema import ensure_schema_registry_populated
from utils.attachments import AttachmentStore
from utils.exceptions import ValidationError
from server.settings import YAML_DIR
from utils.task_input import TaskInputBuilder
from workflow.graph import GraphExecutor
from workflow.graph_context import GraphContext


OUTPUT_ROOT = Path("WareHouse")


@dataclass
class WorkflowMetaInfo:
    session_name: str
    yaml_file: str
    log_id: Optional[str]
    outputs: Optional[Dict[str, Any]]
    token_usage: Optional[Dict[str, Any]]
    output_dir: Path


@dataclass
class WorkflowRunResult:
    final_message: Optional[Message]
    meta_info: WorkflowMetaInfo


def _normalize_session_name(yaml_path: Path, session_name: Optional[str]) -> str:
    if session_name and session_name.strip():
        return session_name.strip()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"sdk_{yaml_path.stem}_{timestamp}"


def _build_task_input(
    graph_context: GraphContext,
    prompt: str,
    attachments: Sequence[Union[str, Path]],
) -> Union[str, list[Message]]:
    if not attachments:
        return prompt

    attachments_dir = graph_context.directory / "code_workspace" / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    store = AttachmentStore(attachments_dir)
    builder = TaskInputBuilder(store)
    normalized_paths = [str(Path(path).expanduser()) for path in attachments]
    return builder.build_from_file_paths(prompt, normalized_paths)


def _resolve_yaml_path(yaml_file: Union[str, Path]) -> Path:
    candidate = Path(yaml_file).expanduser()
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    repo_root = Path(__file__).resolve().parents[1]
    yaml_root = YAML_DIR if YAML_DIR.is_absolute() else (repo_root / YAML_DIR)
    return (yaml_root / candidate).expanduser()


def run_workflow(
    yaml_file: Union[str, Path],
    *,
    task_prompt: str,
    attachments: Optional[Sequence[Union[str, Path]]] = None,
    session_name: Optional[str] = None,
    fn_module: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    log_level: Optional[Union[LogLevel, str]] = None,
) -> WorkflowRunResult:
    """Run a workflow YAML and return the end-node message plus metadata."""
    ensure_schema_registry_populated()

    yaml_path = _resolve_yaml_path(yaml_file)
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    attachments = attachments or []
    if (not task_prompt or not task_prompt.strip()) and not attachments:
        raise ValidationError(
            "Task prompt cannot be empty",
            details={"task_prompt_provided": bool(task_prompt)},
        )

    design = load_config(yaml_path, fn_module=fn_module, vars_override=variables)
    normalized_session = _normalize_session_name(yaml_path, session_name)

    graph_config = GraphConfig.from_definition(
        design.graph,
        name=normalized_session,
        output_root=OUTPUT_ROOT,
        source_path=str(yaml_path),
        vars=design.vars,
    )

    if log_level:
        resolved_level = LogLevel(log_level) if isinstance(log_level, str) else log_level
        graph_config.log_level = resolved_level
        graph_config.definition.log_level = resolved_level

    graph_context = GraphContext(config=graph_config)
    task_input = _build_task_input(graph_context, task_prompt, attachments)

    executor = GraphExecutor.execute_graph(graph_context, task_input)
    final_message = executor.get_final_output_message()

    logger = executor.log_manager.get_logger() if executor.log_manager else None
    log_id = logger.workflow_id if logger else None
    token_usage = executor.token_tracker.get_token_usage() if executor.token_tracker else None

    meta_info = WorkflowMetaInfo(
        session_name=normalized_session,
        yaml_file=str(yaml_path),
        log_id=log_id,
        outputs=executor.outputs,
        token_usage=token_usage,
        output_dir=graph_context.directory,
    )

    return WorkflowRunResult(final_message=final_message, meta_info=meta_info)
