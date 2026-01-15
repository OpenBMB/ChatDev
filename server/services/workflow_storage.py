"""Utilities for validating and persisting workflow YAML files."""

import re
from pathlib import Path
from typing import Any, Tuple

import yaml

from check.check import check_config
from utils.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    SecurityError,
    ValidationError,
    WorkflowExecutionError,
)
from utils.structured_logger import get_server_logger, LogType


def _update_workflow_id(content: str, workflow_id: str) -> str:
    # Pattern to match graph:\n  id: <value>
    pattern = re.compile(r"(graph:\s*\n\s*id:\s*).*$", re.MULTILINE)
    match = pattern.search(content)
    if match:
        # Replace the value after "graph:\n  id: "
        return pattern.sub(rf"\1{workflow_id}", content, count=1)

    # If no graph.id found, look for standalone id: at root level (legacy support)
    root_id_pattern = re.compile(r"^(id:\s*).*$", re.MULTILINE)
    root_match = root_id_pattern.search(content)
    if root_match:
        return root_id_pattern.sub(rf"\1{workflow_id}", content, count=1)

    # If neither found, add graph.id after graph: section if it exists
    graph_pattern = re.compile(r"(graph:\s*\n)")
    graph_match = graph_pattern.search(content)
    if graph_match:
        return graph_pattern.sub(rf"\1  id: {workflow_id}\n", content, count=1)

    # Fallback (is invalid)
    lines = content.splitlines()
    insert_index = 0
    if lines and lines[0].strip() == "---":
        insert_index = 1
    lines.insert(insert_index, f"graph:\n  id: {workflow_id}")
    updated = "\n".join(lines)
    if content.endswith("\n"):
        updated += "\n"
    return updated


def validate_workflow_filename(filename: str, *, require_yaml_extension: bool = True) -> str:
    """Sanitize workflow filenames and guard against traversal attempts."""

    value = (filename or "").strip()
    if not value:
        raise ValidationError("Filename cannot be empty", field="filename")

    if ".." in value or value.startswith(("/", "\\")):
        logger = get_server_logger()
        logger.log_security_event(
            "PATH_TRAVERSAL_ATTEMPT",
            f"Suspicious filename detected: {value}",
            details={"received_filename": value},
        )
        raise SecurityError("Invalid filename format", details={"filename": value})

    if not re.match(r"^[a-zA-Z0-9._-]+$", value):
        raise ValidationError(
            "Invalid filename: only letters, digits, dots, underscores, and hyphens are allowed",
            field="filename",
        )

    if require_yaml_extension and not value.endswith((".yaml", ".yml")):
        raise ValidationError("Filename must end with .yaml or .yml", field="filename")

    return Path(value).name


def validate_workflow_content(filename: str, content: str) -> Tuple[str, Any]:
    safe_filename = validate_workflow_filename(filename, require_yaml_extension=True)

    try:
        yaml_content = yaml.safe_load(content)
        if yaml_content is None:
            raise ValidationError("YAML content is empty", field="content")

        errors = check_config(yaml_content)
        if errors:
            raise ValidationError(f"YAML validation errors:\n{errors}", field="content")
    except yaml.YAMLError as exc:
        logger = get_server_logger()
        logger.warning("Invalid YAML content in upload", details={"error": str(exc)})
        raise ValidationError(f"Invalid YAML syntax: {exc}", field="content")

    return safe_filename, yaml_content


def persist_workflow(
    safe_filename: str,
    content: str,
    yaml_content: Any,
    *,
    action: str,
    directory: Path,
) -> None:
    save_path = directory / safe_filename
    logger = get_server_logger()

    try:
        save_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        logger.log_exception(exc, f"Failed to save workflow file {safe_filename}")
        raise WorkflowExecutionError(
            "Failed to save workflow file", details={"filename": safe_filename}
        )

    logger.info(
        "Workflow file persisted",
        log_type=LogType.WORKFLOW,
        filename=safe_filename,
        action=action,
    )


def rename_workflow(source_filename: str, target_filename: str, *, directory: Path) -> None:
    source_safe = validate_workflow_filename(source_filename, require_yaml_extension=True)
    target_safe = validate_workflow_filename(target_filename, require_yaml_extension=True)

    if source_safe == target_safe:
        raise ValidationError("Source and target filenames must be different", field="new_filename")

    source_path = directory / source_safe
    target_path = directory / target_safe

    if not source_path.exists() or not source_path.is_file():
        raise ResourceNotFoundError(
            "Workflow file not found",
            resource_type="workflow",
            resource_id=source_safe,
        )

    if target_path.exists():
        raise ResourceConflictError(
            "Target workflow already exists",
            resource_type="workflow",
            resource_id=target_safe,
        )

    logger = get_server_logger()
    try:
        source_path.rename(target_path)
    except Exception as exc:
        logger.log_exception(exc, f"Failed to rename workflow file {source_safe} to {target_safe}")
        raise WorkflowExecutionError(
            "Failed to rename workflow file",
            details={"source": source_safe, "target": target_safe},
        )

    try:
        new_workflow_id = Path(target_safe).stem
        content = target_path.read_text(encoding="utf-8")
        updated = _update_workflow_id(content, new_workflow_id)
        if updated != content:
            target_path.write_text(updated, encoding="utf-8")
    except Exception as exc:
        logger.log_exception(exc, f"Failed to update workflow id after rename to {target_safe}")
        raise WorkflowExecutionError(
            "Failed to update workflow id after rename",
            details={"target": target_safe},
        )

    logger.info(
        "Workflow file renamed",
        log_type=LogType.WORKFLOW,
        source=source_safe,
        target=target_safe,
        action="rename",
    )


def copy_workflow(source_filename: str, target_filename: str, *, directory: Path) -> None:
    source_safe = validate_workflow_filename(source_filename, require_yaml_extension=True)
    target_safe = validate_workflow_filename(target_filename, require_yaml_extension=True)

    if source_safe == target_safe:
        raise ValidationError("Source and target filenames must be different", field="new_filename")

    source_path = directory / source_safe
    target_path = directory / target_safe

    if not source_path.exists() or not source_path.is_file():
        raise ResourceNotFoundError(
            "Workflow file not found",
            resource_type="workflow",
            resource_id=source_safe,
        )

    if target_path.exists():
        raise ResourceConflictError(
            "Target workflow already exists",
            resource_type="workflow",
            resource_id=target_safe,
        )

    logger = get_server_logger()
    try:
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception as exc:
        logger.log_exception(exc, f"Failed to copy workflow file {source_safe} to {target_safe}")
        raise WorkflowExecutionError(
            "Failed to copy workflow file",
            details={"source": source_safe, "target": target_safe},
        )

    logger.info(
        "Workflow file copied",
        log_type=LogType.WORKFLOW,
        source=source_safe,
        target=target_safe,
        action="copy",
    )
