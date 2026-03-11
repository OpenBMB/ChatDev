from fastapi import APIRouter

from utils.function_catalog import get_function_catalog

router = APIRouter()


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