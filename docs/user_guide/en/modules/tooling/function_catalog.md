# Built-in Function Tool Catalog

This document lists all preset tools in the `functions/function_calling/` directory for Agent nodes to use via Function Tooling.

## Quick Import

Reference tools in YAML as follows:

```yaml
tooling:
  - type: function
    config:
      tools:
        - name: file:All           # Import entire module
        - name: save_file          # Import single function
        - name: deep_research:All
```

---

## File Operations (file.py)

Tools for file and directory management within `code_workspace/`.

| Function | Description |
|----------|-------------|
| `describe_available_files` | List available files in attachment store and code_workspace |
| `list_directory` | List contents of a directory |
| `create_folder` | Create a folder (supports nested directories) |
| `delete_path` | Delete a file or directory |
| `load_file` | Load a file and register as attachment, supports multimodal (text/image/audio) |
| `save_file` | Save text content to a file |
| `read_text_file_snippet` | Read text snippet (offset + limit), suitable for large files |
| `read_file_segment` | Read file by line range, supports line number metadata |
| `apply_text_edits` | Apply multiple text edits while preserving newlines and encoding |
| `rename_path` | Rename a file or directory |
| `copy_path` | Copy a file or directory tree |
| `move_path` | Move a file or directory |
| `search_in_files` | Search for text or regex patterns in workspace files |

**Example YAML**: [ChatDev_v1.yaml](../../../../../yaml_instance/ChatDev_v1.yaml), [file_tool_use_case.yaml](../../../../../yaml_instance/file_tool_use_case.yaml)

---

## Python Environment Management (uv_related.py)

Manage Python environments and dependencies using uv.

| Function | Description |
|----------|-------------|
| `install_python_packages` | Install Python packages using `uv add` |
| `init_python_env` | Initialize Python environment (uv lock + venv) |
| `uv_run` | Execute uv run in workspace to run modules or scripts |

**Example YAML**: [ChatDev_v1.yaml](../../../../../yaml_instance/ChatDev_v1.yaml)

---

## Deep Research (deep_research.py)

Search result management and report generation tools for automated research workflows.

### Search Result Management

| Function | Description |
|----------|-------------|
| `search_save_result` | Save or update a search result (URL, title, abstract, details) |
| `search_load_all` | Load all saved search results |
| `search_load_by_url` | Load a specific search result by URL |
| `search_high_light_key` | Save highlighted keywords for a search result |

### Report Management

| Function | Description |
|----------|-------------|
| `report_read` | Read full report content |
| `report_read_chapter` | Read a specific chapter (supports multi-level paths like `Intro/Background`) |
| `report_outline` | Get report outline (header hierarchy) |
| `report_create_chapter` | Create a new chapter |
| `report_rewrite_chapter` | Rewrite chapter content |
| `report_continue_chapter` | Append content to an existing chapter |
| `report_reorder_chapters` | Reorder chapters |
| `report_del_chapter` | Delete a chapter |
| `report_export_pdf` | Export report to PDF |

**Example YAML**: [deep_research_v1.yaml](../../../../../yaml_instance/deep_research_v1.yaml)

---

## Web Tools (web.py)

Web search and webpage content retrieval.

| Function | Description |
|----------|-------------|
| `web_search` | Perform web search using Serper.dev, supports pagination and multiple languages |
| `read_webpage_content` | Read webpage content using Jina Reader, supports rate limiting |

**Environment Variables**:
- `SERPER_DEV_API_KEY`: Serper.dev API key
- `JINA_API_KEY`: Jina API key (optional, auto rate-limited to 20 RPM without key)

**Example YAML**: [deep_research_v1.yaml](../../../../../yaml_instance/deep_research_v1.yaml)

---

## Video Tools (video.py)

Manim animation rendering and video processing.

| Function | Description |
|----------|-------------|
| `render_manim` | Render Manim script, auto-detects scene class and outputs video |
| `concat_videos` | Concatenate multiple video files using FFmpeg |

**Example YAML**: [teach_video.yaml](../../../../../yaml_instance/teach_video.yaml), [teach_video.yaml](../../../../../yaml_instance/teach_video.yaml)

---

## Code Execution (code_executor.py)

| Function | Description |
|----------|-------------|
| `execute_code` | Execute Python code string, returns stdout and stderr |

> ⚠️ **Security Note**: This tool has elevated privileges and should only be used in trusted workflows.

---

## User Interaction (user.py)

| Function | Description |
|----------|-------------|
| `call_user` | Send instructions to the user and get a response, for scenarios requiring human input |

---

## Weather Query (weather.py)

Demo tools to illustrate Function Calling workflow.

| Function | Description |
|----------|-------------|
| `get_city_num` | Return city code (hardcoded example) |
| `get_weather` | Return weather info by city code (hardcoded example) |

---

## Adding Custom Tools

1. Create a Python file in `functions/function_calling/` directory
2. Define parameters using type annotations:

```python
from typing import Annotated
from utils.function_catalog import ParamMeta

def my_tool(
    param1: Annotated[str, ParamMeta(description="Parameter description")],
    *,
    _context: dict | None = None,  # Optional, auto-injected by system
) -> str:
    """Function description (shown to LLM)"""
    return "result"
```

3. Restart the backend server
4. Reference in Agent node via `name: my_tool` or `name: my_module:All`
