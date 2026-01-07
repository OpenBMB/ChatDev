# Function Tooling Configuration Guide

`FunctionToolConfig` lets agent nodes call Python functions defined in the repo. Implementation lives in `entity/configs/tooling.py`, `utils/function_catalog.py`, and `functions/function_calling/`.

## 1. Config Fields
| Field | Description |
| --- | --- |
| `tools` | List of `FunctionToolEntryConfig`. Each entry requires `name`. |
| `timeout` | Tool execution timeout (seconds). |

`FunctionToolEntryConfig` specifics:
- `name`: top-level function name in `functions/function_calling/`.

### Function picker (`module_name:function_name`) & `module_name:All`
- The dropdown displays each function as `module_name:function_name`, where `module_name` is the relative Python file under `functions/function_calling/` (without `.py`, nested folders joined by `/`). This preserves semantic grouping for large catalogs.
- Every module automatically prepends a `module_name:All` entry, and all `All` entries are sorted lexicographically ahead of concrete functions. Choosing it expands to all functions in that module during config parsing, preserving alphabetical order.
- `module_name:All` is strictly for bulk imports; overriding `description`/`parameters`/`auto_fill` alongside it raises a validation error. Customize individual functions after expansion if needed.
- Both modules and functions are sorted alphabetically, and YAML still stores the plain function names; `module_name:All` is merely an input shortcut.

## 2. Function Directory Requirements
- Path: `functions/function_calling/` (override with `MAC_FUNCTIONS_DIR`).
- Functions must live at module top level.
- Provide Python type hints; for enums/descriptions use `typing.Annotated[..., ParamMeta(...)]`.
- Parameters beginning with `_` or splats (`*args`/`**kwargs`) are hidden from the agent call.
- The docstring’s first paragraph becomes the description (truncated to ~600 chars).
- `utils/function_catalog.py` builds JSON Schemas at startup for the frontend/CLI.

## 3. Context Injection
The executor passes `_context` into each function:
| Key | Value |
| --- | --- |
| `attachment_store` | `utils.attachments.AttachmentStore` for querying/registering attachments. |
| `python_workspace_root` | Session `code_workspace/` shared by Python nodes. |
| `graph_directory` | Session root directory for relative path helpers. |
| others | Environment-specific extras (session/node IDs, etc.). |
Functions can declare `_context: dict | None = None` and parse it (see `functions/function_calling/file.py`’s `FileToolContext`).

## 4. Example: Read Text File
```python
from typing import Annotated
from utils.function_catalog import ParamMeta


def read_text_file(
    path: Annotated[str, ParamMeta(description="workspace-relative path")],
    *,
    encoding: str = "utf-8",
    _context: dict | None = None,
) -> str:
    ctx = FileToolContext(_context)
    target = ctx.resolve_under_workspace(path)
    return target.read_text(encoding=encoding)
```
YAML usage:
```yaml
nodes:
  - id: summarize
    type: agent
    config:
      tooling:
        type: function
        config:
          tools:
            - name: describe_available_files
            - name: read_text_file
```

## 5. Extension Flow
1. Add your function under `functions/function_calling/`.
2. Supply type hints + `ParamMeta`; set `auto_fill: false` with custom `parameters` if you need manual JSON Schema.
3. If the function needs extra packages, declare them in `pyproject.toml`/`requirements.txt`, or use the bundled `install_python_packages` sparingly.
4. Run `python -m tools.export_design_template ...` so the frontend picks up new enums.

## 6. Debugging
- If the frontend/CLI reports function `foo` not found, double-check the name and ensure it resides under `MAC_FUNCTIONS_DIR`.
- When `function_catalog` fails to load, `FunctionToolEntryConfig.field_specs()` includes the error—fix syntax or dependencies first.
- Tool timeouts bubble up to the agent; raise `timeout` or handle exceptions inside the function for friendlier responses.
