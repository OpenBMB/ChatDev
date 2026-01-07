from fastapi import APIRouter, HTTPException

from server.models import VueGraphContentPayload
from server.services.vuegraphs_storage import fetch_vuegraph_content, save_vuegraph_content
from utils.structured_logger import get_server_logger, LogType

router = APIRouter()


@router.post("/api/vuegraphs/upload/content")
async def upload_vuegraph_content(payload: VueGraphContentPayload):
    logger = get_server_logger()
    try:
        save_vuegraph_content(payload.filename, payload.content)
    except Exception as exc:
        logger.error(
            "Failed to persist Vue graph content",
            log_type=LogType.ERROR,
            filename=payload.filename,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Unable to save graph content")

    logger.info(
        "Vue graph content saved",
        log_type=LogType.REQUEST,
        filename=payload.filename,
    )
    return {"filename": payload.filename, "status": "saved"}


@router.get("/api/vuegraphs/{filename}")
async def get_vuegraph_content(filename: str):
    logger = get_server_logger()
    try:
        content = fetch_vuegraph_content(filename)
    except Exception as exc:
        logger.error(
            "Failed to load Vue graph content",
            log_type=LogType.ERROR,
            filename=filename,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Unable to read graph content")

    if content is None:
        raise HTTPException(status_code=404, detail="Graph content not found")

    logger.info(
        "Vue graph content fetched",
        log_type=LogType.REQUEST,
        filename=filename,
    )
    return {"filename": filename, "content": content}
