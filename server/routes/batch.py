import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from entity.enums import LogLevel
from server.services.batch_parser import parse_batch_file
from server.services.batch_run_service import BatchRunService
from server.state import ensure_known_session
from utils.exceptions import ValidationError

router = APIRouter()


@router.post("/api/workflows/batch")
async def execute_batch(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    yaml_file: str = Form(...),
    max_parallel: int = Form(5),
    log_level: str | None = Form(None),
):
    try:
        manager = ensure_known_session(session_id, require_connection=True)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if max_parallel < 1:
        raise HTTPException(status_code=400, detail="max_parallel must be >= 1")

    try:
        content = await file.read()
        tasks, file_base = parse_batch_file(content, file.filename or "batch.csv")
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    resolved_level = None
    if log_level:
        try:
            resolved_level = LogLevel(log_level)
        except ValueError:
            raise HTTPException(status_code=400, detail="log_level must be either DEBUG or INFO")

    service = BatchRunService()
    asyncio.create_task(
        service.run_batch(
            session_id,
            yaml_file,
            tasks,
            manager,
            max_parallel=max_parallel,
            file_base=file_base,
            log_level=resolved_level,
        )
    )

    return {
        "status": "accepted",
        "session_id": session_id,
        "batch_id": session_id,
        "task_count": len(tasks),
    }
