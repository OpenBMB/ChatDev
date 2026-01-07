# 内置 Function 工具目录

本文档列出 `functions/function_calling/` 目录中预置的所有工具，供 Agent 节点通过 Function Tooling 调用。

## 快速导入

在 YAML 中可通过以下方式引用：

```yaml
tooling:
  - type: function
    config:
      tools:
        - name: file:All           # 导入整个模块
        - name: save_file          # 导入单个函数
        - name: deep_research:All
```

---

## 文件操作 (file.py)

文件与目录操作工具集，用于在 `code_workspace/` 中进行文件管理。

| 函数 | 说明 |
|------|------|
| `describe_available_files` | 列出附件仓库和 code_workspace 中的可用文件 |
| `list_directory` | 列出指定目录内容 |
| `create_folder` | 创建文件夹（支持多级目录） |
| `delete_path` | 删除文件或目录 |
| `load_file` | 加载文件并注册为附件，支持多模态（文本/图片/音频） |
| `save_file` | 保存文本内容到文件 |
| `read_text_file_snippet` | 读取文本片段（offset + limit），适合大文件 |
| `read_file_segment` | 按行范围读取文件，支持行号元数据 |
| `apply_text_edits` | 应用多处文本编辑，保留换行符和编码 |
| `rename_path` | 重命名文件或目录 |
| `copy_path` | 复制文件或目录树 |
| `move_path` | 移动文件或目录 |
| `search_in_files` | 在工作区文件中搜索文本或正则模式 |

**示例 YAML**：[ChatDev_v1.yaml](../../../../../yaml_instance/ChatDev_v1.yaml)、[file_tool_use_case.yaml](../../../../../yaml_instance/file_tool_use_case.yaml)

---

## Python 环境管理 (uv_related.py)

使用 uv 管理 Python 环境和依赖。

| 函数 | 说明 |
|------|------|
| `install_python_packages` | 使用 `uv add` 安装 Python 包 |
| `init_python_env` | 初始化 Python 环境（uv lock + venv） |
| `uv_run` | 在工作区内执行 uv run，运行模块或脚本 |

**示例 YAML**：[ChatDev_v1.yaml](../../../../../yaml_instance/ChatDev_v1.yaml)

---

## 深度研究 (deep_research.py)

搜索结果管理与报告生成工具，适用于自动化研究场景。

### 搜索结果管理

| 函数 | 说明 |
|------|------|
| `search_save_result` | 保存或更新搜索结果（URL、标题、摘要、详情） |
| `search_load_all` | 加载所有已保存的搜索结果 |
| `search_load_by_url` | 按 URL 加载特定搜索结果 |
| `search_high_light_key` | 为搜索结果保存高亮关键词 |

### 报告管理

| 函数 | 说明 |
|------|------|
| `report_read` | 读取报告完整内容 |
| `report_read_chapter` | 读取特定章节（支持多级路径如 `Intro/Background`） |
| `report_outline` | 获取报告大纲（标题层级结构） |
| `report_create_chapter` | 创建新章节 |
| `report_rewrite_chapter` | 重写章节内容 |
| `report_continue_chapter` | 追加内容到现有章节 |
| `report_reorder_chapters` | 重新排序章节 |
| `report_del_chapter` | 删除章节 |
| `report_export_pdf` | 导出报告为 PDF |

**示例 YAML**：[deep_research_v1.yaml](../../../../../yaml_instance/deep_research_v1.yaml)

---

## 网络工具 (web.py)

网络搜索与网页内容获取。

| 函数 | 说明 |
|------|------|
| `web_search` | 使用 Serper.dev 执行网络搜索，支持分页和多语言 |
| `read_webpage_content` | 使用 Jina Reader 读取网页内容，支持速率限制 |

**环境变量**：
- `SERPER_DEV_API_KEY`：Serper.dev API 密钥
- `JINA_API_KEY`：Jina API 密钥（可选，无密钥时自动限速 20 RPM）

**示例 YAML**：[deep_research_v1.yaml](../../../../../yaml_instance/deep_research_v1.yaml)

---

## 视频工具 (video.py)

Manim 动画渲染与视频处理。

| 函数 | 说明 |
|------|------|
| `render_manim` | 渲染 Manim 脚本，自动检测场景类并输出视频 |
| `concat_videos` | 使用 FFmpeg 拼接多个视频文件 |

**示例 YAML**：[teach_video.yaml](../../../../../yaml_instance/teach_video.yaml)、[teach_video.yaml](../../../../../yaml_instance/teach_video.yaml)

---

## 代码执行 (code_executor.py)

| 函数 | 说明 |
|------|------|
| `execute_code` | 执行 Python 代码字符串，返回 stdout 和 stderr |

> ⚠️ **安全提示**：此工具具有高权限，应仅在可信工作流内使用。

---

## 用户交互 (user.py)

| 函数 | 说明 |
|------|------|
| `call_user` | 向用户发送指令并获取响应，用于需要人工输入的场景 |

---

## 天气查询 (weather.py)

示例工具，用于演示 Function Calling 流程。

| 函数 | 说明 |
|------|------|
| `get_city_num` | 返回城市编号（硬编码示例） |
| `get_weather` | 根据城市编号返回天气信息（硬编码示例） |

---

## 添加自定义工具

1. 在 `functions/function_calling/` 目录下创建 Python 文件
2. 使用类型注解定义参数：

```python
from typing import Annotated
from utils.function_catalog import ParamMeta

def my_tool(
    param1: Annotated[str, ParamMeta(description="参数描述")],
    *,
    _context: dict | None = None,  # 可选，系统自动注入
) -> str:
    """函数描述（会显示给 LLM）"""
    return "result"
```

3. 重启后端服务器
4. 在 Agent 节点中通过 `name: my_tool` 或 `name: my_module:All` 引用
