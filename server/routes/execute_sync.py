from __future__ import annotations

import json
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence, Union

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from check.check import load_config
from entity.enums import LogLevel
from entity.graph_config import GraphConfig
from entity.messages import Message
from runtime.bootstrap.schema import ensure_schema_registry_populated
from runtime.sdk import OUTPUT_ROOT, run_workflow
from server.models import WorkflowRunRequest
from server.services.workflow_handoff_service import load_handoffs_from_workflow, run_handoffs
from server.settings import YAML_DIR
from utils.attachments import AttachmentStore
from utils.exceptions import ValidationError, WorkflowExecutionError
from utils.logger import WorkflowLogger
from utils.structured_logger import get_server_logger, LogType
from utils.task_input import TaskInputBuilder
from workflow.graph import GraphExecutor
from workflow.graph_context import GraphContext

router = APIRouter()

_SSE_CONTENT_TYPE = "text/event-stream"


def _normalize_session_name(yaml_path: Path, session_name: Optional[str]) -> str:
    if session_name and session_name.strip():
        return session_name.strip()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"sdk_{yaml_path.stem}_{timestamp}"


def _resolve_yaml_path(yaml_file: Union[str, Path]) -> Path:
    candidate = Path(yaml_file).expanduser()
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    repo_root = Path(__file__).resolve().parents[2]
    yaml_root = YAML_DIR if YAML_DIR.is_absolute() else (repo_root / YAML_DIR)
    return (yaml_root / candidate).expanduser()


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


def _run_workflow_with_logger(
    *,
    yaml_file: Union[str, Path],
    task_prompt: str,
    attachments: Optional[Sequence[Union[str, Path]]],
    session_name: Optional[str],
    variables: Optional[dict],
    log_level: Optional[LogLevel],
    log_callback,
) -> tuple[Optional[Message], dict[str, Any]]:
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

    design = load_config(yaml_path, vars_override=variables)
    normalized_session = _normalize_session_name(yaml_path, session_name)

    graph_config = GraphConfig.from_definition(
        design.graph,
        name=normalized_session,
        output_root=OUTPUT_ROOT,
        source_path=str(yaml_path),
        vars=design.vars,
    )

    if log_level:
        graph_config.log_level = log_level
        graph_config.definition.log_level = log_level

    graph_context = GraphContext(config=graph_config)
    task_input = _build_task_input(graph_context, task_prompt, attachments)

    class _StreamingWorkflowLogger(WorkflowLogger):
        def add_log(self, *args, **kwargs):
            entry = super().add_log(*args, **kwargs)
            if entry:
                payload = entry.to_dict()
                payload.pop("details", None)
                log_callback("log", payload)
            return entry

    class _StreamingExecutor(GraphExecutor):
        def _create_logger(self) -> WorkflowLogger:
            level = log_level or self.graph.log_level
            return _StreamingWorkflowLogger(
                self.graph.name,
                level,
                use_structured_logging=True,
                log_to_console=False,
            )

    executor = _StreamingExecutor(graph_context, session_id=normalized_session)
    executor._execute(task_input)
    final_message = executor.get_final_output_message()

    logger = executor.log_manager.get_logger() if executor.log_manager else None
    log_id = logger.workflow_id if logger else None
    token_usage = executor.token_tracker.get_token_usage() if executor.token_tracker else None

    meta = {
        "session_name": normalized_session,
        "yaml_file": str(yaml_path),
        "log_id": log_id,
        "outputs": executor.outputs,
        "token_usage": token_usage,
        "output_dir": graph_context.directory,
    }
    return final_message, meta


def _sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.post("/api/workflow/run")
async def run_workflow_sync(request: WorkflowRunRequest, http_request: Request):
    try:
        resolved_log_level: Optional[LogLevel] = None
        if request.log_level:
            resolved_log_level = LogLevel(request.log_level)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="log_level must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL",
        )

    accepts_stream = _SSE_CONTENT_TYPE in (http_request.headers.get("accept") or "")
    if not accepts_stream:
        try:
            result = await run_in_threadpool(
                run_workflow,
                request.yaml_file,
                task_prompt=request.task_prompt,
                attachments=request.attachments,
                session_name=request.session_name,
                variables=request.variables,
                log_level=resolved_log_level,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger = get_server_logger()
            logger.log_exception(exc, "Failed to run workflow via sync API")
            raise WorkflowExecutionError(f"Failed to run workflow: {exc}")

        final_message = result.final_message.text_content() if result.final_message else ""
        meta = result.meta_info
        handoff_results = await run_in_threadpool(
            run_handoffs,
            load_handoffs_from_workflow(meta.yaml_file, request.variables),
            source_workflow=meta.yaml_file,
            final_message=final_message,
            results=meta.outputs,
            token_usage=meta.token_usage,
            variables=request.variables,
            log_level=resolved_log_level,
        )

        logger = get_server_logger()
        logger.info(
            "Workflow execution completed via sync API",
            log_type=LogType.WORKFLOW,
            session_id=meta.session_name,
            yaml_path=meta.yaml_file,
        )

        return {
            "status": "completed",
            "final_message": final_message,
            "token_usage": meta.token_usage,
            "output_dir": str(meta.output_dir.resolve()),
            "handoffs": handoff_results,
        }

    event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
    done_event = threading.Event()

    def enqueue(event_type: str, data: Any) -> None:
        event_queue.put((event_type, data))

    def worker() -> None:
        try:
            enqueue(
                "started",
                {"yaml_file": request.yaml_file, "task_prompt": request.task_prompt},
            )
            final_message, meta = _run_workflow_with_logger(
                yaml_file=request.yaml_file,
                task_prompt=request.task_prompt,
                attachments=request.attachments,
                session_name=request.session_name,
                variables=request.variables,
                log_level=resolved_log_level,
                log_callback=enqueue,
            )
            final_text = final_message.text_content() if final_message else ""
            enqueue(
                "completed",
                {
                    "status": "completed",
                    "final_message": final_text,
                    "token_usage": meta["token_usage"],
                    "output_dir": str(meta["output_dir"].resolve()),
                },
            )
            handoff_results = run_handoffs(
                load_handoffs_from_workflow(meta["yaml_file"], request.variables),
                source_workflow=meta["yaml_file"],
                final_message=final_text,
                results=meta.get("outputs"),
                token_usage=meta["token_usage"],
                variables=request.variables,
                log_level=resolved_log_level,
            )
            if handoff_results:
                enqueue("handoffs_completed", {"handoffs": handoff_results})
        except (FileNotFoundError, ValidationError) as exc:
            enqueue("error", {"message": str(exc)})
        except Exception as exc:
            logger = get_server_logger()
            logger.log_exception(exc, "Failed to run workflow via streaming API")
            enqueue("error", {"message": f"Failed to run workflow: {exc}"})
        finally:
            done_event.set()

    threading.Thread(target=worker, daemon=True).start()

    async def stream():
        while True:
            try:
                event_type, data = event_queue.get(timeout=0.1)
                yield _sse_event(event_type, data)
            except queue.Empty:
                if done_event.is_set():
                    break

    return StreamingResponse(stream(), media_type=_SSE_CONTENT_TYPE)
