import importlib.util
import inspect
import random
import uuid
from pathlib import Path
from typing import Any, Iterable

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool
from starlette.requests import Request
from starlette.responses import JSONResponse

# Repo root (for loading built-in function tools).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_FUNCTION_CALLING_DIR = _REPO_ROOT / "functions" / "function_calling"

# MCP server for production use (supports hot-updated tools).
mcp = FastMCP(
    "DevAll MCP Server",
    debug=True,
)

_DYNAMIC_TOOLS_DIR = Path(__file__).parent / "dynamic_tools"
_DYNAMIC_TOOLS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_tool_filename(filename: str) -> str:
    name = Path(filename).name
    if not name.endswith(".py"):
        raise ValueError("filename must end with .py")
    return name


def _load_module_from_path(path: Path) -> Any:
    module_name = f"_dynamic_mcp_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError("failed to create module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _select_functions(module: Any, allowlist: Iterable[str] | None) -> list[Any]:
    allowset = {name.strip() for name in allowlist} if allowlist else None
    selected = []
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if name.startswith("_"):
            continue
        if getattr(obj, "__module__", None) != module.__name__:
            continue
        if allowset is not None and name not in allowset:
            continue
        selected.append(obj)
    if allowset:
        missing = sorted(allowset - {fn.__name__ for fn in selected})
        if missing:
            raise ValueError(f"functions not found in module: {', '.join(missing)}")
    return selected


def _register_functions(functions: Iterable[Any], *, replace: bool, source: str) -> list[str]:
    added: list[str] = []
    for fn in functions:
        tool = FunctionTool.from_function(fn, meta={"source": source})
        if replace:
            try:
                mcp.remove_tool(tool.name)
            except Exception:
                pass
        mcp.add_tool(tool)
        added.append(tool.name)
    return added


def register_tools_from_payload(payload: dict) -> dict:
    filename = payload.get("filename")
    content = payload.get("content")
    function_names = payload.get("functions")
    replace = payload.get("replace", True)

    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename is required")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content is required")
    if function_names is not None and not isinstance(function_names, list):
        raise ValueError("functions must be a list of strings")

    safe_name = _safe_tool_filename(filename.strip())

    file_path = _DYNAMIC_TOOLS_DIR / safe_name
    file_path.write_text(content, encoding="utf-8")

    module = _load_module_from_path(file_path)
    functions = _select_functions(module, function_names)
    if not functions:
        raise ValueError("no functions found to register")

    added = _register_functions(functions, replace=bool(replace), source="dynamic_tools")

    return {"status": "ok", "added": added, "file": str(file_path)}


@mcp.custom_route("/admin/tools/upload", methods=["POST"])
async def upload_tool(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        result = register_tools_from_payload(payload)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": f"failed to load tools: {exc}"}, status_code=400)

    return JSONResponse(result)


@mcp.custom_route("/admin/tools/reload", methods=["POST"])
async def reload_tools(request: Request) -> JSONResponse:
    replace = True
    try:
        payload = await request.json()
        if isinstance(payload, dict) and "replace" in payload:
            replace = bool(payload["replace"])
    except Exception:
        replace = True
    result = load_tools_from_directory(replace=replace)
    return JSONResponse(result)


@mcp.custom_route("/admin/tools/list", methods=["GET"])
async def list_tools(request: Request) -> JSONResponse:
    tools = await mcp.get_tools()
    items = []
    for key in sorted(tools.keys()):
        tool = tools[key]
        meta = tool.meta or {}
        source = meta.get("source", "unknown")
        call_methods = ["mcp_remote"]
        if source == "function_calling":
            call_methods.append("function")
        payload = {
            "key": key,
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "enabled": tool.enabled,
            "source": source,
            "call_methods": call_methods,
        }
        if meta:
            payload["meta"] = meta
        if tool.output_schema is not None:
            payload["output_schema"] = tool.output_schema
        items.append(payload)
    return JSONResponse({"tools": items})


def load_tools_from_directory(*, replace: bool = True) -> dict:
    added: list[str] = []
    errors: list[str] = []
    for directory in (_FUNCTION_CALLING_DIR, _DYNAMIC_TOOLS_DIR):
        if not directory.exists():
            continue
        source = "local_tools" if directory == _FUNCTION_CALLING_DIR else "mcp_tools"
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_") or path.name == "__init__.py":
                continue
            try:
                module = _load_module_from_path(path)
                functions = _select_functions(module, None)
                if not functions:
                    continue
                added.extend(_register_functions(functions, replace=replace, source=source))
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
    return {"added": added, "errors": errors}


_bootstrap = load_tools_from_directory(replace=True)
if _bootstrap["errors"]:
    print(f"Dynamic tool load errors: {_bootstrap['errors']}")


if __name__ == "__main__":
    print("Starting MCP server...")
    print("Run standalone with: fastmcp run server/mcp_server.py --transport streamable-http --port 8010")
    mcp.run()