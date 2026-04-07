from fastapi import APIRouter, HTTPException
from typing import Any

import yaml

from server.models import (
    WorkflowCopyRequest,
    WorkflowMoveGroupRequest,
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


def _load_workflow_metadata(file_path):
    raw_content = file_path.read_text(encoding="utf-8")
    yaml_content = yaml.safe_load(raw_content) or {}

    description = ""
    organization = ""

    if isinstance(yaml_content, dict):
        graph = yaml_content.get("graph") or {}
        if isinstance(graph, dict):
            description = str(graph.get("description") or "")
            organization = str(graph.get("organization") or "")

    return {
        "name": file_path.name,
        "description": description,
        "organization": organization,
    }


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

    workflows = []
    for file_path in sorted(YAML_DIR.glob("*.yaml")):
        try:
            workflows.append(_load_workflow_metadata(file_path))
        except Exception as exc:
            logger = get_server_logger()
            logger.log_exception(exc, f"Failed to load workflow metadata for {file_path.name}")
            workflows.append(
                {
                    "name": file_path.name,
                    "description": "",
                    "organization": "",
                }
            )
    return {"workflows": workflows}


@router.get("/api/workflows/{filename}/args")
async def get_workflow_args(filename: str):
    print(str)
    try:
        safe_filename = validate_workflow_filename(filename, require_yaml_extension=True)
        print(safe_filename)
        file_path = YAML_DIR / safe_filename

        if not file_path.exists() or not file_path.is_file():
            raise ResourceNotFoundError(
                "Workflow file not found",
                resource_type="workflow",
                resource_id=safe_filename,
            )

        # Load and validate YAML content
        raw_content = file_path.read_text(encoding="utf-8")
        _, yaml_content = validate_workflow_content(safe_filename, raw_content)

        args: list[dict[str, Any]] = []
        if isinstance(yaml_content, dict):
            graph = yaml_content.get("graph") or {}
            if isinstance(graph, dict):
                raw_args = graph.get("args") or []
                if isinstance(raw_args, list):
                    if len(raw_args) == 0:
                        raise ResourceNotFoundError(
                            "Workflow file does not have args",
                            resource_type="workflow",
                            resource_id=safe_filename,
                        )
                    for item in raw_args:
                        # Each item is expected to be like: { arg_name: [ {key: value}, ... ] }
                        if not isinstance(item, dict) or len(item) != 1:
                            continue
                        (arg_name, spec_list), = item.items()
                        if not isinstance(arg_name, str):
                            continue

                        arg_info: dict[str, Any] = {"name": arg_name}
                        if isinstance(spec_list, list):
                            for spec in spec_list:
                                if isinstance(spec, dict):
                                    for key, value in spec.items():
                                        # Later entries override earlier ones if duplicated
                                        arg_info[str(key)] = value
                        args.append(arg_info)

        logger = get_server_logger()
        logger.info(
            "Workflow args retrieved",
            log_type=LogType.WORKFLOW,
            filename=safe_filename,
            args_count=len(args),
        )

        return {"args": args}
    except ValidationError as exc:
        # 参数或文件名等校验错误
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc)},
        )
    except SecurityError as exc:
        # 安全相关错误（例如路径遍历）
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc)},
        )
    except ResourceNotFoundError as exc:
        # 文件不存在
        raise HTTPException(
            status_code=404,
            detail={"message": str(exc)},
        )
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error retrieving workflow args: {filename}")
        # 兜底错误
        raise HTTPException(
            status_code=500,
            detail={"message": f"Failed to retrieve workflow args: {exc}"},
        )


@router.get("/api/workflows/{filename}/desc")
async def get_workflow_desc(filename: str):
    try:
        safe_filename = validate_workflow_filename(filename, require_yaml_extension=True)
        file_path = YAML_DIR / safe_filename

        if not file_path.exists() or not file_path.is_file():
            raise ResourceNotFoundError(
                "Workflow file not found",
                resource_type="workflow",
                resource_id=safe_filename,
            )

        # Load and validate YAML content
        raw_content = file_path.read_text(encoding="utf-8")
        _, yaml_content = validate_workflow_content(safe_filename, raw_content)

        desc = ""
        organization = ""
        if isinstance(yaml_content, dict):
            graph = yaml_content.get("graph") or {}
            if isinstance(graph, dict):
                desc = graph.get("description") or ""
                organization = graph.get("organization") or ""
        logger = get_server_logger()
        logger.info(
            "Workflow description retrieved",
            log_type=LogType.WORKFLOW,
            filename=safe_filename,
        )
        return {"description": desc, "organization": organization}
    except ValidationError as exc:
        # 参数或文件名等校验错误
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc)},
        )
    except SecurityError as exc:
        # 安全相关错误（例如路径遍历）
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc)},
        )
    except ResourceNotFoundError as exc:
        # 文件不存在
        raise HTTPException(
            status_code=404,
            detail={"message": str(exc)},
        )
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Unexpected error retrieving workflow args: {filename}")
        # 兜底错误
        raise HTTPException(
            status_code=500,
            detail={"message": f"Failed to retrieve workflow args: {exc}"},
        )


@router.post("/api/workflows/upload/content")
async def upload_workflow_content(request: WorkflowUploadContentRequest):
    return _persist_workflow_from_content(
        request.filename,
        request.content,
        allow_overwrite=False,
        action="upload",
        success_message="Workflow {filename} created successfully from content",
    )


@router.put("/api/workflows/{filename}/update")
async def update_workflow_content(filename: str, request: WorkflowUpdateContentRequest):
    return _persist_workflow_from_content(
        filename,
        request.content,
        allow_overwrite=True,
        action="update",
        success_message="Workflow {filename} updated successfully",
    )


@router.put("/api/workflows/{filename}/organization")
async def update_workflow_organization(filename: str, request: WorkflowMoveGroupRequest):
    try:
        safe_filename = validate_workflow_filename(filename, require_yaml_extension=True)
        file_path = YAML_DIR / safe_filename
        if not file_path.exists() or not file_path.is_file():
            raise ResourceNotFoundError(
                "Workflow file not found",
                resource_type="workflow",
                resource_id=safe_filename,
            )

        raw_content = file_path.read_text(encoding="utf-8")
        yaml_content = yaml.safe_load(raw_content) or {}
        if not isinstance(yaml_content, dict):
            raise ValidationError("Workflow YAML root must be a mapping", field="content")

        graph = yaml_content.get("graph")
        if not isinstance(graph, dict):
            graph = {}
            yaml_content["graph"] = graph

        organization = (request.organization or "").strip()
        if organization:
            graph["organization"] = organization
        else:
            graph.pop("organization", None)

        file_path.write_text(
            yaml.safe_dump(yaml_content, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return {
            "status": "success",
            "filename": safe_filename,
            "organization": organization,
            "message": "Workflow organization updated successfully",
        }
    except ValidationError:
        raise
    except ResourceNotFoundError:
        raise
    except Exception as exc:
        logger = get_server_logger()
        logger.log_exception(exc, f"Failed to update workflow organization for {filename}")
        raise WorkflowExecutionError(f"Failed to update workflow organization: {exc}")


@router.delete("/api/workflows/{filename}/delete")
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


@router.get("/api/workflows/{filename}/get")
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
