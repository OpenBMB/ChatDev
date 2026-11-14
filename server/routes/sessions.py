import re
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from server.settings import WARE_HOUSE_DIR
from utils.exceptions import ResourceNotFoundError, SecurityError, ValidationError
from utils.structured_logger import get_server_logger, LogType
from utils.workspace_paths import resolve_workspace_path, session_directory_name

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

        dir_name = session_directory_name(session_id)
        session_path = resolve_workspace_path(WARE_HOUSE_DIR, dir_name)

        if not session_path.exists() or not session_path.is_dir():
            raise ResourceNotFoundError(
                "Session directory not found",
                resource_type="session",
                resource_id=session_id,
            )

        if (WARE_HOUSE_DIR / dir_name).is_symlink():
            raise SecurityError("Session downloads must not follow symbolic links")
        entries = [session_path]
        for path in session_path.rglob("*"):
            if path.is_symlink():
                continue
            if not path.resolve().is_relative_to(session_path):
                raise SecurityError("Session downloads must not follow symbolic links")
            if path.is_file() or path.is_dir():
                entries.append(path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            zip_path = Path(tmp_file.name)

        try:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in entries:
                    archive.write(path, arcname=str(Path(dir_name) / path.relative_to(session_path)))
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

        return FileResponse(
            path=zip_path,
            filename=f"{dir_name}.zip",
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={dir_name}.zip"},
            background=BackgroundTask(cleanup_zip),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Session directory not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error during session download: {session_id}")
        raise HTTPException(status_code=500, detail="Failed to download session")
