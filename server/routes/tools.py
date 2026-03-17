import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, constr

from utils.function_catalog import get_function_catalog
from utils.function_manager import FUNCTION_CALLING_DIR

router = APIRouter()


class LocalToolCreateRequest(BaseModel):
    filename: constr(strip_whitespace=True, min_length=1, max_length=255)
    content: str
    overwrite: bool = False


@router.get("/api/tools/local")
def list_local_tools():
    catalog = get_function_catalog()
    metadata = catalog.list_metadata()
    tools = []
    for name, meta in metadata.items():
        tools.append(
            {
                "name": name,
                "description": meta.description,
                "parameters": meta.parameters_schema,
                "module": meta.module_name,
                "file_path": meta.file_path,
            }
        )
    tools.sort(key=lambda item: item["name"])
    return {
        "success": True,
        "count": len(tools),
        "tools": tools,
        "load_error": str(catalog.load_error) if catalog.load_error else None,
    }


@router.post("/api/tools/local")
def create_local_tool(payload: LocalToolCreateRequest):
    raw_name = payload.filename.strip()
    if not raw_name:
        raise HTTPException(status_code=400, detail="filename is required")

    if not re.match(r"^[A-Za-z0-9_-]+(\.py)?$", raw_name):
        raise HTTPException(status_code=400, detail="filename must be alphanumeric with optional .py extension")

    filename = raw_name if raw_name.endswith(".py") else f"{raw_name}.py"
    tools_dir = Path(FUNCTION_CALLING_DIR).resolve()
    tools_dir.mkdir(parents=True, exist_ok=True)

    target_path = (tools_dir / filename).resolve()
    try:
        target_path.relative_to(tools_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="filename resolves outside function tools directory")

    if target_path.exists() and not payload.overwrite:
        raise HTTPException(status_code=409, detail="tool file already exists")

    target_path.write_text(payload.content, encoding="utf-8")

    catalog = get_function_catalog()
    catalog.refresh()
    return {
        "success": True,
        "filename": filename,
        "path": str(target_path),
        "load_error": str(catalog.load_error) if catalog.load_error else None,
    }
