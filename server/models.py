"""Pydantic models shared across server routes."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, constr


class WorkflowRequest(BaseModel):
    yaml_file: str
    task_prompt: str
    session_id: Optional[str] = None
    attachments: Optional[List[str]] = None
    log_level: Literal["INFO", "DEBUG"] = "INFO"


class WorkflowRunRequest(BaseModel):
    yaml_file: str
    task_prompt: str
    attachments: Optional[List[str]] = None
    session_name: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    log_level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]] = None


class WorkflowUploadContentRequest(BaseModel):
    filename: str
    content: str


class WorkflowUpdateContentRequest(BaseModel):
    content: str


class WorkflowRenameRequest(BaseModel):
    new_filename: str


class WorkflowCopyRequest(BaseModel):
    new_filename: str


class VueGraphContentPayload(BaseModel):
    filename: constr(strip_whitespace=True, min_length=1, max_length=255)
    content: str
