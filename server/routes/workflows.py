from fastapi import APIRouter, HTTPException

from server.models import (
    WorkflowCopyRequest,
    WorkflowRenameRequest,
    WorkflowUpdateContentRequest,
    WorkflowUploadContentRequest,
)
from server.services.workflow_storage import (
    copy_workflow,
    persist_workflow,
    rename_workflow,
    validate_workflow_content,
    validate_workflow_filename,
)
from server.settings import YAML_DIR
from utils.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    SecurityError,
    ValidationError,
    WorkflowExecutionError,
)
from utils.structured_logger import get_server_logger, LogType

router = APIRouter()


def _persist_workflow_from_content(
    filename: str,
    content: str,
    *,
    allow_overwrite: bool,
    action: str,
    success_message: str,
):
    try:
        safe_filename, yaml_content = validate_workflow_content(filename.strip(), content)
        save_path = YAML_DIR / safe_filename

        if save_path.exists() and not allow_overwrite:
            raise HTTPException(status_code=409, detail="Workflow already exists; use the update API to overwrite")

        if not save_path.exists() and allow_overwrite:
            raise HTTPException(status_code=404, detail="Workflow file not found")

        persist_workflow(safe_filename, content, yaml_content, action=action, directory=YAML_DIR)
        return {
            "status": "success",
            "filename": safe_filename,
            "message": success_message.format(filename=safe_filename),
        }
    except ValidationError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error during workflow {action}")
        raise WorkflowExecutionError(f"Failed to {action} workflow: {exc}")


@router.get("/api/workflows")
async def list_workflows():
    if not YAML_DIR.exists():
        return {"workflows": []}
    return {"workflows": [file.name for file in YAML_DIR.glob("*.yaml")]}


@router.post("/api/workflows/upload/content")
async def upload_workflow_content(request: WorkflowUploadContentRequest):
    return _persist_workflow_from_content(
        request.filename,
        request.content,
        allow_overwrite=False,
        action="upload",
        success_message="Workflow {filename} created successfully from content",
    )


@router.put("/api/workflows/{filename}")
async def update_workflow_content(filename: str, request: WorkflowUpdateContentRequest):
    return _persist_workflow_from_content(
        filename,
        request.content,
        allow_overwrite=True,
        action="update",
        success_message="Workflow {filename} updated successfully",
    )


@router.delete("/api/workflows/{filename}")
async def delete_workflow(filename: str):
    try:
        safe_filename = validate_workflow_filename(filename, require_yaml_extension=True)
        file_path = YAML_DIR / safe_filename
        if not file_path.exists() or not file_path.is_file():
            raise ResourceNotFoundError(
                "Workflow file not found",
                resource_type="workflow",
                resource_id=safe_filename,
            )

        try:
            file_path.unlink()
        except Exception as exc:
            logger = get_server_logger()
            logger.log_exception(exc, f"Failed to delete workflow file: {safe_filename}")
            raise WorkflowExecutionError("Failed to delete workflow file", details={"filename": safe_filename})

        logger = get_server_logger()
        logger.info(
            "Workflow file deleted",
            log_type=LogType.WORKFLOW,
            filename=safe_filename,
        )

        return {
            "status": "deleted",
            "filename": safe_filename,
            "message": f"Workflow '{safe_filename}' deleted successfully",
        }
    except ValidationError:
        raise
    except SecurityError:
        raise
    except ResourceNotFoundError:
        raise
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error deleting workflow: {filename}")
        raise WorkflowExecutionError(f"Failed to delete workflow: {exc}")


@router.post("/api/workflows/{filename}/rename")
async def rename_workflow_file(filename: str, request: WorkflowRenameRequest):
    try:
        rename_workflow(filename, request.new_filename, directory=YAML_DIR)
        return {
            "status": "success",
            "source": validate_workflow_filename(filename, require_yaml_extension=True),
            "target": validate_workflow_filename(request.new_filename, require_yaml_extension=True),
            "message": f"Workflow renamed to '{request.new_filename}' successfully",
        }
    except ValidationError:
        raise
    except SecurityError:
        raise
    except ResourceConflictError:
        raise
    except ResourceNotFoundError:
        raise
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error renaming workflow: {filename}")
        raise WorkflowExecutionError(f"Failed to rename workflow: {exc}")


@router.post("/api/workflows/{filename}/copy")
async def copy_workflow_file(filename: str, request: WorkflowCopyRequest):
    try:
        copy_workflow(filename, request.new_filename, directory=YAML_DIR)
        return {
            "status": "success",
            "source": validate_workflow_filename(filename, require_yaml_extension=True),
            "target": validate_workflow_filename(request.new_filename, require_yaml_extension=True),
            "message": f"Workflow copied to '{request.new_filename}' successfully",
        }
    except ValidationError:
        raise
    except SecurityError:
        raise
    except ResourceConflictError:
        raise
    except ResourceNotFoundError:
        raise
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error copying workflow: {filename}")
        raise WorkflowExecutionError(f"Failed to copy workflow: {exc}")


@router.get("/api/workflows/{filename}")
async def get_workflow_raw_content(filename: str):
    try:
        safe_filename = validate_workflow_filename(filename, require_yaml_extension=True)

        file_path = YAML_DIR / safe_filename
        if not file_path.exists() or not file_path.is_file():
            raise ResourceNotFoundError(
                "Workflow file not found",
                resource_type="workflow",
                resource_id=safe_filename,
            )

        with open(file_path, "r", encoding="utf-8") as handle:
            raw_content = handle.read()

        logger = get_server_logger()
        logger.info("Workflow file content retrieved", log_type=LogType.WORKFLOW, filename=safe_filename)
        return {"content": raw_content}
    except ValidationError:
        raise
    except SecurityError:
        raise
    except ResourceNotFoundError:
        raise
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error retrieving workflow: {filename}")
        raise WorkflowExecutionError(f"Failed to retrieve workflow: {exc}")
