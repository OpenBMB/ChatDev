import asyncio

from fastapi import APIRouter, HTTPException

from entity.enums import LogLevel
from server.models import WorkflowRequest
from server.state import ensure_known_session
from utils.exceptions import ValidationError, WorkflowExecutionError
from utils.structured_logger import get_server_logger, LogType

router = APIRouter()


@router.post("/api/workflow/execute")
async def execute_workflow(request: WorkflowRequest):
    try:
        manager = ensure_known_session(request.session_id, require_connection=True)
        # log_level = LogLevel(request.log_level) if request.log_level else None
        log_level = None
    except ValueError:
        raise HTTPException(status_code=400, detail="log_level must be either DEBUG or INFO")
    try:
        asyncio.create_task(
            manager.workflow_run_service.start_workflow(
                request.session_id,
                request.yaml_file,
                request.task_prompt,
                manager,
                attachments=request.attachments,
                log_level=log_level,
            )
        )

        logger = get_server_logger()
        logger.info(
            "Workflow execution started",
            log_type=LogType.WORKFLOW,
            session_id=request.session_id,
            yaml_file=request.yaml_file,
            task_prompt_length=len(request.task_prompt or ""),
        )

        return {
            "status": "started",
            "session_id": request.session_id,
            "message": "Workflow execution started",
        }
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, "Failed to start workflow execution")
        raise WorkflowExecutionError(f"Failed to start workflow: {exc}")
