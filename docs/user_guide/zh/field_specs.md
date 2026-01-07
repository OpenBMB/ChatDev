# FIELD_SPECS 定义指南

本文档解释如何在新增配置（Config）时正确编写 `FIELD_SPECS`，以便 Web UI 表单和 `python -m tools.export_design_template` 命令自动生成可视化表单与 YAML 模板。本指南适用于所有继承 `BaseConfig` 的配置类，例如节点、Memory、Thinking、Tooling 等。

## 1. 为什么需要 FIELD_SPECS
- UI 表单依赖 `FIELD_SPECS` 生成输入控件、默认值、提示文案。
- 设计模板导出脚本会读取 `FIELD_SPECS`，将字段元数据写入 `yaml_template/design*.yaml` 以及 `frontend/public/` 镜像文件。
- 没有 `FIELD_SPECS` 的字段在前端无法展示，也不会出现在导出的模板中。

## 2. 基本结构
`FIELD_SPECS` 是一个 `{字段名: ConfigFieldSpec}` 的字典，通常定义在 Config 类内：

```python
FIELD_SPECS = {
    "interpreter": ConfigFieldSpec(
        name="interpreter",
        display_name="解释器",
        type_hint="str",
        required=False,
        default="python3",
        description="Python 可执行文件路径",
    ),
    ...
}
```

核心字段说明：
- `name`：与 YAML 字段一致。
- `display_name`：可选的用户展示名称，前端表单优先显示；缺省时自动回退到 `name`。
- `type_hint`：供 UI/文档展示的类型描述，例如 `str`、`list[str]`、`dict[str, Any]`。
- `required`：是否必填；若有默认值通常设为 False。
- `default`：默认值（标量或 JSON 可序列化对象）。
- `description`：表单提示与文档说明。
- `enum`：可选值列表（字符串数组）。
- `enumOptions`：为枚举提供 label/description 等附加提示，推荐搭配 `enum` 一起返回，提升表单友好度。
- `child`：嵌套子配置类（引用另一个 `BaseConfig` 子类）。

## 3. 编写流程
1. **实现 `from_dict` 校验**：在解析 YAML 时确保类型正确、提供清晰错误（抛 `ConfigError`，见 `entity/configs/python_runner.py`）。
2. **定义 `FIELD_SPECS`**：覆盖所有公开字段，提供类型、描述、默认值等信息。
3. **动态字段处理**：若字段依赖注册表或目录扫描结果，重写 `field_specs()` 并使用 `replace()` 注入实时 `enum`/`description`（示例：`FunctionToolEntryConfig.field_specs()` 自动列出函数目录）。
4. **导出设计模板**：完成修改后运行：
   ```bash
   python -m tools.export_design_template --output yaml_template/design.yaml --mirror frontend/public/design.yaml
   ```
   该命令会根据最新的 `FIELD_SPECS` 生成 YAML 模板和前端镜像文件，无需手动编辑。

## 4. 常见模式示例
- **简单标量字段**：`entity/configs/python_runner.py` 中的 `timeout_seconds`，展示如何设置整数默认值和校验。
- **嵌套列表字段**：`entity/configs/memory.py` 的 `file_sources` 使用 `child=FileSourceConfig`，UI 自动渲染可重复子表单。
- **动态枚举**：`entity/configs/node.py:304` 的 `Node.field_specs()` 使用节点注册表填充 `type` 选项并附带 `enumOptions` 描述；`FunctionToolEntryConfig.field_specs()` 从函数目录生成带说明的枚举列表。
- **注册驱动描述**：调用 `register_node_type`/`register_memory_store`/`register_thinking_mode`/`register_tooling_type` 时提供的 `summary/description` 会自动写入 `enumOptions`，务必填写，避免前端看到没有含义的值。
- **可选区块**：通过 `required=False` + `default=...` 表示可选配置，`from_dict` 中需妥善处理。

## 5. 最佳实践
- 描述保持用户友好，明确单位（例如“超时时间（秒）”）。
- 默认值应与 `from_dict` 行为一致，避免 UI 默认与后端解析不符。
- 对嵌套配置提供精简示例或引用，以免 UI 难以理解字段含义。
- 修改或新增 `FIELD_SPECS` 后，记得同步导出设计模板。

如需更多例子，可查阅 `entity/configs/model.py`、`entity/configs/tooling.py` 等文件，或参考已有节点/Memory/Thinking 配置的实现。
