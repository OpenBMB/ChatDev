# Function Tooling 配置指南

`FunctionToolConfig` 允许 Agent 节点调用仓库中的 Python 函数。相关代码位于 `entity/configs/tooling.py`、`utils/function_catalog.py` 以及 `functions/function_calling/`。

## 1. 配置字段
| 字段 | 说明 |
| --- | --- |
| `tools` | 列表，元素为 `FunctionToolEntryConfig`。每个条目至少包含 `name`。|
| `timeout` | 单次工具执行的超时时间（秒）。|

`FunctionToolEntryConfig` 字段：
- `name`：函数名，来自 `functions/function_calling/` 文件的顶级函数。

### 函数列表展示与 `module_name:All`
- UI 下拉列表会将每个函数展示为 `module_name:function_name`。`module_name` 等于函数文件相对于 `functions/function_calling/` 的路径（去掉 `.py`，子目录使用 `/` 连接），便于快速定位语义相关模块。
- 每个模块顶部都会自动插入 `module_name:All` 选项，并且所有模块的 `All` 条目按照字典序排在列表最前。选择该项时会在解析阶段展开为该模块下的所有函数，顺序同样遵循字典序。
- `module_name:All` 只能批量引入函数，禁止同时填写 `description`、`parameters` 或 `auto_fill` 等覆盖字段；若需要自定义，请展开后针对具体函数单独配置。
- 函数与模块都采用全局字典序排列，使长列表更易检索；YAML 中仍然以真实函数名落盘，`module_name:All` 仅作为输入辅助。

## 2. 函数目录要求
- 路径：`functions/function_calling/`（可通过 `MAC_FUNCTIONS_DIR` 覆盖）。
- 每个函数：
  - 必须位于模块顶层。
  - 使用 Python 类型注解；若需枚举或描述，可使用 `typing.Annotated[..., ParamMeta(...)]`。
  - 不允许以 `_` 开头的参数暴露给 Agent；`*_args`、`**kwargs` 会被过滤。
  - 可以通过 docstring 的首段提供描述（自动截断为 600 字符）。
- `utils/function_catalog.py` 会在启动时生成 JSON Schema，并向前端/CLI 暴露。

## 3. 上下文注入
执行器会对被调用的函数提供 `_context` 关键字参数，包含：
| 键 | 值 |
| --- | --- |
| `attachment_store` | `utils.attachments.AttachmentStore` 实例，可查询/注册附件。|
| `python_workspace_root` | 当前 Session 的 `code_workspace/`。|
| `graph_directory` | Session 根目录，可推导相对路径。|
| `human_prompt` | `utils.human_prompt.HumanPromptService`，可调用 `request()` 触发人工反馈。|
| 其他 | 视运行环境扩展，例如 `session_id`、`node_id`。|

函数可声明 `_context: dict | None = None` 并自行解析（参考 `functions/function_calling/file.py` 中的 `FileToolContext`，还可参考 `functions/function_calling/user.py`）。

## 4. 示例：文件读取工具
```python
from typing import Annotated
from utils.function_catalog import ParamMeta


def read_text_file(
    path: Annotated[str, ParamMeta(description="workspace 相对路径")],
    *,
    encoding: str = "utf-8",
    _context: dict | None = None,
) -> str:
    ctx = FileToolContext(_context)
    target = ctx.resolve_under_workspace(path)
    return target.read_text(encoding=encoding)
```
在 YAML 中引用：
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

## 5. 扩展流程
1. 在 `functions/function_calling/` 新建模块或函数。
2. 使用类型注解 + `ParamMeta` 描述参数；如需禁止自动 Schema，可设置 `auto_fill: false` 并提供手写 `parameters`。
3. 若函数依赖额外第三方库，可在仓库 `requirements.txt`/`pyproject.toml` 中声明，或在函数内调用 `install_python_packages`（同目录提供）动态安装。
4. 运行 `python -m tools.export_design_template ...` 以刷新前端枚举。

## 6. 调试与排错
- 若前端/CLI 报告 “function 'xxx' not found”，检查函数名称与文件是否位于 `MAC_FUNCTIONS_DIR`（默认 `functions/function_calling/`）。
- `function_catalog` 加载失败时，`FunctionToolEntryConfig.field_specs()` 会在描述中提示错误，请先修复函数语法或依赖。
- 工具运行超时会向 Agent 返回异常文本；可通过 `timeout` 扩大限额，或在函数内部自行捕获并返回友好错误。
