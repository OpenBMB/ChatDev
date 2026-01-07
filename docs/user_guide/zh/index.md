# DevAll 后端用户文档

本目录作为导航页，面向需要部署、编排或扩展 DevAll 后端的读者。详尽步骤与示例请在下表中找到目标子文档。

## 1. 文档地图

| 主题 | 内容提要                                                      |
| --- |-----------------------------------------------------------|
| [Web UI 快速入门](web_ui_guide.md) | 前端界面操作、工作流执行、人工审阅、故障排查                                  |
| [工作流编排](workflow_authoring.md) | YAML 结构、节点类型、Provider/边条件、设计模板导出、CLI 运行                   |
| [图执行逻辑](execution_logic.md) | DAG/循环图执行策略、Tarjan 环路检测、超级节点构建、递归式环路执行                   |
| [Dynamic 并行执行](dynamic_execution.md) | Map/Tree 模式、Split 拆分策略、并行处理与层级归约                          |
| [Memory 模块](modules/memory.md) | Memory 列表架构、内置 `simple`/`file`/`blackboard` 行为、嵌入配置、排障 |
| [Thinking 模块](modules/thinking.md) | 思考增强机制、自我反思模式、扩展自定义思考模式 |
| [Tooling 模块](modules/tooling/README.md) | Function / MCP 模式、上下文注入、内置函数清单、MCP 启动方式                   |
| [节点类型详解](nodes/) | Agent、Python、Human、Subgraph、Passthrough、Literal、Loop Counter 等节点配置 |
| [附件与工件 API](attachments.md) | 上传/列举/下载接口、manifest 结构、清理策略、安全限制                          |
| [FIELD_SPECS 规范](field_specs.md) | UI 表单与模板导出的字段元数据标准（如果您希望自定义模块，请务必阅读此文档）                   |
| [配置 Schema API 契约](config_schema_contract.md) | `/api/config/schema(*)` 请求示例、breadcrumbs 协议（用户可忽略）        |

## 2. 产品概览（后端视角）
- **工作流调度引擎**：解析 YAML DAG，在统一上下文中协调 `model`、`python`、`tooling`、`human` 等节点，并把节点输出写入 `WareHouse/<session>/`。
- **多 Provider 抽象**：`runtime/node/agent/providers/` 层封装 OpenAI、Gemini 等 API，可在节点级别切换模型与鉴权，亦支持额外 `thinking` 与 `memories` 配置。
- **实时可观测性**：FastAPI + WebSocket 将节点状态、stdout/stderr、工件事件推送至 Web UI；结构化日志写入 `logs/`，便于集中收集。
- **运行资产管理**：每次运行创建独立 Session，附件、Python workspace、context snapshot、输出摘要等均可下载。

## 3. 架构与运行流概览
1. **入口**：Web UI 与 CLI 调用 `server_main.py` 暴露的 FastAPI（如 `/api/workflow/execute`）。
2. **验证/入队**：`WorkflowRunService` 校验 YAML、创建 Session、准备 `code_workspace/attachments/`，随后调度器在 `workflow/` 中运行 DAG。
3. **执行阶段**：节点执行器负责依赖解析、上下文传递、工具调用、memory 检索；`MemoryManager`、`ToolingConfig`、`ThinkingManager` 会在模型节点内按需触发。
4. **可观测性**：WebSocket 推送状态、日志、artifact 事件；`logs/` 存储 JSON 日志，`WareHouse/` 保存运行资产。
5. **清理与下载**：Session 结束后可选择打包下载或通过附件 API 逐项获取；保留策略由部署者自定。

## 4. 角色导航
- **解决方案工程师/Prompt 工程师**：从 [工作流编排](workflow_authoring.md) 入手，若需要上下文记忆或工具扩展，分别阅读 Memory 与 Tooling 模块文档。
- **扩展开发者**：结合 [FIELD_SPECS](field_specs.md) 与 [Tooling 模块](modules/tooling/README.md) 了解注册流程，必要时参照 [配置 Schema API 契约](config_schema_contract.md) 调试 UI 交互（英文版见 `docs/en/config_schema_contract.md`）。

## 5. 常用术语
- **Session**：一次完整运行的 ID（由时间戳+名称组成），贯穿 Web UI、后端和 `WareHouse/`。
- **code_workspace**：Python 节点共享的目录，位于 `WareHouse/<session>/code_workspace/`，包含自动同步的附件。
- **Attachment**：用户上传或运行期间注册的文件，通过 REST/WS API 可查询/下载。
- **Memory Store / Attachment**：Memory Store 定义存储实现；Memory Attachment 是模型节点引用 Memory Store 的规则（检索阶段、读写策略等）。
- **Tooling**：模型节点绑定的工具执行环境（Function 或 MCP）。

如发现内容缺失或过时，请在仓库提交 Issue/PR，或在 docs 目录内直接补充并同步至前端模板。
