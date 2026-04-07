"""External trigger endpoints for application and bot integrations."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from entity.enums import LogLevel
from runtime.sdk import run_workflow
from server.models import WorkflowTriggerRequest
from server.services.workflow_handoff_service import load_handoffs_from_workflow, run_handoffs
from utils.exceptions import ValidationError, WorkflowExecutionError
from utils.structured_logger import get_server_logger, LogType

router = APIRouter()


def _build_trigger_prompt(request: WorkflowTriggerRequest) -> str:
    parts = []
    source = (request.source or "").strip()
    event = (request.event or "").strip()
    message = (request.message or "").strip()

    if source:
        parts.append(f"触发来源: {source}")
    if event:
        parts.append(f"触发事件: {event}")
    if message:
        parts.append(message)
    if request.payload:
        parts.append("触发载荷:\n" + json.dumps(request.payload, ensure_ascii=False, indent=2))

    return "\n\n".join(parts).strip()


@router.post("/api/triggers/run")
async def run_workflow_from_trigger(request: WorkflowTriggerRequest):
    """Run a workflow from an external trigger such as a bot message or app event."""

    try:
        resolved_log_level = LogLevel(request.log_level) if request.log_level else None
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="log_level must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL",
        )

    task_prompt = _build_trigger_prompt(request)
    if not task_prompt and not request.attachments:
        raise HTTPException(status_code=400, detail="Trigger message, payload, or attachments are required")

    try:
        result = await run_in_threadpool(
            run_workflow,
            request.yaml_file,
            task_prompt=task_prompt,
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
        logger.log_exception(exc, "Failed to run workflow from external trigger")
        raise WorkflowExecutionError(f"Failed to run workflow from trigger: {exc}")

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
        "Workflow execution completed from external trigger",
        log_type=LogType.WORKFLOW,
        session_id=meta.session_name,
        yaml_path=meta.yaml_file,
        trigger_source=request.source,
        trigger_event=request.event,
    )

    return {
        "status": "completed",
        "final_message": final_message,
        "token_usage": meta.token_usage,
        "output_dir": str(meta.output_dir.resolve()),
        "handoffs": handoff_results,
        "trigger": {
            "source": request.source,
            "event": request.event,
        },
    }
