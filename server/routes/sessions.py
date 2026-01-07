import atexit
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from server.settings import WARE_HOUSE_DIR
from utils.exceptions import ResourceNotFoundError, ValidationError
from utils.structured_logger import get_server_logger, LogType

router = APIRouter()


@router.get("/api/sessions/{session_id}/download")
async def download_session(session_id: str):
    try:
        if not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
            logger = get_server_logger()
            logger.log_security_event(
                "INVALID_SESSION_ID_FORMAT",
                f"Invalid session_id format: {session_id}",
                details={"received_session_id": session_id},
            )
            raise ValidationError(
                "Invalid session_id: only letters, digits, underscores, and hyphens are allowed",
                field="session_id",
            )

        dir_name = f"session_{session_id}"
        session_path = WARE_HOUSE_DIR / dir_name

        if not session_path.exists() or not session_path.is_dir():
            raise ResourceNotFoundError(
                "Session directory not found",
                resource_type="session",
                resource_id=session_id,
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            zip_path = Path(tmp_file.name)

        archive_base = zip_path.with_suffix("")
        try:
            shutil.make_archive(str(archive_base), "zip", root_dir=WARE_HOUSE_DIR, base_dir=dir_name)
        except Exception as exc:
            if zip_path.exists():
                zip_path.unlink()
            logger = get_server_logger()
            logger.log_exception(exc, f"Failed to create zip archive for session: {session_id}")
            raise HTTPException(status_code=500, detail="Failed to create zip archive")

        logger = get_server_logger()
        logger.info(
            "Session download prepared",
            log_type=LogType.WORKFLOW,
            session_id=session_id,
            archive_path=str(zip_path),
        )

        def cleanup_zip():
            if zip_path.exists():
                zip_path.unlink()

        atexit.register(cleanup_zip)

        return FileResponse(
            path=zip_path,
            filename=f"{dir_name}.zip",
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={dir_name}.zip"},
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Session directory not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error during session download: {session_id}")
        raise HTTPException(status_code=500, detail="Failed to download session")
