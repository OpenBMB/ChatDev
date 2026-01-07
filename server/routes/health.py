from fastapi import APIRouter

from utils.structured_logger import get_server_logger, LogType

router = APIRouter()


@router.get("/health")
async def health_check():
    logger = get_server_logger()
    logger.info("Health check requested", log_type=LogType.REQUEST)
    return {"status": "healthy"}


@router.get("/health/live")
async def liveness_check():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_check():
    return {"status": "ready"}
