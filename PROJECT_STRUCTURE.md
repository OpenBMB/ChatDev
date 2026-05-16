# ChatDev 2.0 (DevAll) 项目目录结构说明

> ChatDev 2.0 (DevAll) 是一个面向"开发一切"的零代码多智能体编排平台，支持 Web 可视化画布拖拽编排与 Python SDK 两种交互方式。

## 顶层结构

```
ChatDev/
├── run.py                  # 应用入口脚本
├── server_main.py          # 服务端启动入口
├── start.bat / start.ps1   # Windows 一键启动脚本
├── Dockerfile              # Docker 镜像构建文件
├── compose.yml             # Docker Compose 编排配置
├── Makefile                # 构建与运维命令
├── pyproject.toml          # Python 项目元数据与依赖声明
├── requirements.txt        # Python 依赖清单
├── package.json            # 前端/Node.js 依赖声明
├── .env / .env.example     # 环境变量配置（含示例模板）
├── .env.docker             # Docker 环境专用变量
├── LICENSE                 # 开源许可协议
└── README.md / README-zh.md # 项目文档（中英文）
```

## 核心模块

### `entity/` — 数据实体与配置模型

定义整个平台的数据结构、枚举、消息格式和配置加载逻辑。

```
entity/
├── __init__.py
├── config_loader.py        # 配置文件加载器
├── enum_options.py         # 枚举选项定义
├── enums.py                # 枚举类型定义
├── graph_config.py         # 图（工作流）配置模型
├── messages.py             # 消息结构定义（对话、系统提示等）
├── tool_spec.py            # 工具规格描述
└── configs/                # 节点/边的配置模型
    ├── base.py             # 配置基类
    ├── dynamic_base.py     # 动态配置基类
    ├── graph.py            # 图配置
    ├── node/               # 节点配置模型
    │   ├── agent.py        #   Agent 节点配置
    │   ├── human.py        #   人工交互节点配置
    │   ├── literal.py      #   字面量节点配置
    │   ├── loop_counter.py #   循环计数器节点配置
    │   ├── loop_timer.py   #   循环计时器节点配置
    │   ├── memory.py       #   记忆模块配置
    │   ├── node.py         #   节点通用配置基类
    │   ├── passthrough.py  #   透传节点配置
    │   ├── python_runner.py#   Python 运行器节点配置
    │   ├── skills.py       #   技能节点配置
    │   ├── subgraph.py     #   子图节点配置
    │   ├── thinking.py     #   推理节点配置
    │   └── tooling.py      #   工具链配置
    └── edge/               # 边配置模型
        ├── edge.py             # 边通用配置基类
        ├── edge_condition.py   # 边条件配置
        ├── edge_processor.py   # 边处理器配置
        └── dynamic_edge_config.py # 动态边配置
```

### `workflow/` — 工作流引擎

工作流的核心执行引擎，负责图构建、拓扑分析、执行调度和循环管理。

```
workflow/
├── __init__.py
├── graph.py                # 图结构定义与操作（核心，38KB）
├── graph_context.py        # 图执行上下文
├── graph_manager.py        # 图生命周期管理
├── topology_builder.py     # 拓扑排序与构建
├── cycle_manager.py        # 循环/迭代控制管理
├── subgraph_loader.py      # 子图加载器
├── executor/               # 执行器
│   ├── cycle_executor.py       # 循环执行器
│   ├── dag_executor.py         # DAG 执行器
│   ├── dynamic_edge_executor.py# 动态边执行器
│   ├── parallel_executor.py    # 并行执行器
│   └── resource_manager.py     # 资源管理器
├── runtime/                # 运行时
│   ├── execution_strategy.py   # 执行策略
│   ├── result_archiver.py      # 结果归档
│   ├── runtime_builder.py      # 运行时构建器
│   └── runtime_context.py      # 运行时上下文
└── hooks/                  # 钩子机制
    └── workspace_artifact.py   # 工作空间产物钩子
```

### `runtime/` — 运行时环境

节点和边的运行时实现，包含各类执行器和 Agent 子系统。

```
runtime/
├── __init__.py
├── sdk.py                  # Python SDK 入口
├── bootstrap/              # 启动引导
│   └── schema.py               # 启动模式定义
├── node/                   # 节点运行时
│   ├── builtin_nodes.py        # 内置节点注册
│   ├── registry.py             # 节点注册表
│   ├── splitter.py             # 输出分割器
│   ├── agent/                  # Agent 子系统
│   │   ├── memory/             #   记忆管理（10个模块）
│   │   ├── providers/          #   LLM 提供商适配（7个模块）
│   │   ├── skills/             #   技能系统（3个模块）
│   │   ├── thinking/           #   推理模式（6个模块）
│   │   └── tool/               #   工具调用（3个模块）
│   └── executor/               # 节点执行器
│       ├── agent_executor.py       # Agent 节点执行器（核心，53KB）
│       ├── human_executor.py       # 人工交互执行器
│       ├── literal_executor.py     # 字面量执行器
│       ├── loop_counter_executor.py# 循环计数执行器
│       ├── loop_timer_executor.py  # 循环计时执行器
│       ├── passthrough_executor.py # 透传执行器
│       ├── python_executor.py      # Python 代码执行器
│       ├── subgraph_executor.py    # 子图执行器
│       ├── base.py                 # 执行器基类
│       └── factory.py              # 执行器工厂
└── edge/                   # 边运行时
    ├── conditions/              # 条件判断
    │   ├── base.py                  # 条件基类
    │   ├── builtin_types.py         # 内置条件类型
    │   ├── keyword_manager.py       # 关键词条件管理
    │   ├── function_manager.py      # 函数条件管理
    │   └── registry.py              # 条件注册表
    └── processors/              # 数据处理
        ├── base.py                  # 处理器基类
        ├── builtin_types.py         # 内置处理器类型
        ├── regex_processor.py       # 正则处理器
        ├── function_processor.py    # 函数处理器
        └── registry.py              # 处理器注册表
```

### `server/` — Web 服务端

FastAPI 后端服务，提供 REST API、WebSocket 通信和工作流执行服务。

```
server/
├── __init__.py
├── app.py                  # FastAPI 应用实例
├── bootstrap.py            # 服务启动引导
├── models.py               # Pydantic 请求/响应模型
├── settings.py             # 服务配置
├── state.py                # 应用状态管理
├── config_schema_router.py # 配置 Schema 路由
├── routes/                 # API 路由
│   ├── workflows.py            # 工作流 CRUD 与操作
│   ├── execute.py              # 异步执行入口
│   ├── execute_sync.py         # 同步执行入口
│   ├── sessions.py             # 会话管理
│   ├── websocket.py            # WebSocket 通信
│   ├── vuegraphs.py            # 可视化图数据接口
│   ├── artifacts.py            # 产物管理
│   ├── batch.py                # 批量运行
│   ├── tools.py                # 工具管理
│   ├── uploads.py              # 文件上传
│   └── health.py               # 健康检查
└── services/               # 业务逻辑层
    ├── workflow_run_service.py # 工作流运行服务
    ├── workflow_storage.py     # 工作流持久化
    ├── session_execution.py    # 会话执行管理
    ├── session_store.py        # 会话存储
    ├── websocket_executor.py   # WebSocket 执行器
    ├── websocket_manager.py    # WebSocket 连接管理
    ├── websocket_logger.py     # WebSocket 日志
    ├── batch_run_service.py    # 批量运行服务
    ├── batch_parser.py         # 批量运行解析
    ├── artifact_dispatcher.py  # 产物分发
    ├── artifact_events.py      # 产物事件
    ├── attachment_service.py   # 附件服务
    ├── message_handler.py      # 消息处理
    ├── prompt_channel.py       # 提示词通道
    └── vuegraphs_storage.py    # 可视化图存储
```

### `frontend/` — Web 前端

Vue 3 + Vite 构建的可视化画布编辑器，支持拖拽式节点编排。

```
frontend/
├── index.html              # 入口 HTML
├── package.json            # 前端依赖
├── vite.config.js          # Vite 构建配置
├── eslint.config.js        # ESLint 配置
├── Dockerfile              # 前端 Docker 构建
└── src/
    ├── main.js             # 应用入口
    ├── App.vue             # 根组件
    ├── style.css           # 全局样式
    ├── i18n.js             # 国际化配置
    ├── router/             # 路由
    ├── locales/            # 国际化语言包
    ├── components/         # 公共组件
    │   ├── FormGenerator.vue        # 动态表单生成器
    │   ├── DynamicFormField.vue     # 动态表单字段
    │   ├── WorkflowNode.vue         # 工作流节点组件
    │   ├── WorkflowEdge.vue         # 工作流边组件
    │   ├── StartNode.vue            # 起始节点组件
    │   ├── Sidebar.vue              # 侧边栏
    │   ├── SettingsModal.vue        # 设置弹窗
    │   ├── CollapsibleMessage.vue   # 可折叠消息
    │   ├── InlineConfigRenderer.vue # 内联配置渲染
    │   └── RichTooltip.vue          # 富文本提示
    ├── pages/              # 页面视图
    │   ├── HomeView.vue             # 首页
    │   ├── WorkflowView.vue         # 工作流编辑页
    │   ├── WorkflowList.vue         # 工作流列表页
    │   ├── WorkflowWorkbench.vue    # 工作流工作台
    │   ├── LaunchView.vue           # 启动/运行页
    │   ├── BatchRunView.vue         # 批量运行页
    │   └── TutorialView.vue         # 教程页
    └── utils/              # 工具函数
        ├── apiFunctions.js          # API 调用封装
        ├── yamlFunctions.js         # YAML 解析工具
        ├── formUtils.js             # 表单工具
        ├── configStore.js           # 配置状态管理
        ├── colorUtils.js            # 颜色工具
        ├── helpContent.js           # 帮助内容
        ├── spriteFetcher.js         # 精灵图获取
        └── vueflow.css              # VueFlow 样式
```

## 功能模块

### `functions/` — 内置函数/工具

平台内置的工具函数，供 Agent 节点调用。

```
functions/
├── function_calling/       # 函数调用实现
│   ├── file.py                 # 文件操作（读写、搜索等，37KB）
│   ├── deep_research.py        # 深度研究
│   ├── web.py                  # 网页请求
│   ├── code_executor.py        # 代码执行
│   ├── video.py                # 视频处理
│   ├── uv_related.py           # UV 包管理相关
│   ├── weather.py              # 天气查询
│   ├── user.py                 # 用户交互
│   └── utils.py                # 工具函数
├── edge/                   # 边函数
└── edge_processor/         # 边处理器函数
```

### `utils/` — 通用工具库

跨模块复用的工具函数和服务。

```
utils/
├── logger.py               # 日志系统（18.9KB）
├── structured_logger.py    # 结构化日志
├── log_manager.py          # 日志管理器
├── attachments.py          # 附件处理
├── function_catalog.py     # 函数目录
├── function_manager.py     # 函数管理器
├── error_handler.py        # 全局错误处理
├── exceptions.py           # 自定义异常
├── middleware.py           # 中间件
├── human_prompt.py         # 人工提示处理
├── task_input.py           # 任务输入
├── vars_resolver.py        # 变量解析器
├── workspace_scanner.py    # 工作空间扫描
├── schema_exporter.py      # Schema 导出
├── registry.py             # 通用注册表
├── env_loader.py           # 环境变量加载
├── io_utils.py             # IO 工具
├── strs.py                 # 字符串工具
└── token_tracker.py        # Token 用量追踪
```

## 工作流定义

### `yaml_instance/` — 工作流 YAML 实例

存放可运行的工作流定义文件。

```
yaml_instance/
├── ai-project-make.yaml    # AI 项目制作主工作流（74.4KB）
├── demo/                   # 示例工作流（42个 YAML）
└── subgraphs/              # 子图定义（3个 YAML）
```

### `yaml_template/` — 工作流 YAML 模板

```
yaml_template/
└── design.yaml             # 设计模板
```

## 其他模块

### `check/` — 校验模块

```
check/
├── check.py                # 通用校验
├── check_workflow.py       # 工作流校验
└── check_yaml.py           # YAML 格式校验
```

### `schema_registry/` — Schema 注册中心

```
schema_registry/
└── registry.py             # Schema 注册与管理
```

### `tools/` — 命令行工具

```
tools/
├── export_design_template.py   # 导出设计模板
├── sync_vuegraphs.py           # 同步可视化图数据
└── validate_all_yamls.py       # 批量校验 YAML 文件
```

### `WareHouse/` — 产物仓库

工作流运行产生的会话数据、执行日志和代码产物。

```
WareHouse/
└── session_<uuid>/         # 每个运行会话一个目录
    ├── code_workspace/     #   代码工作空间
    │   └── attachments/   #     附件文件
    ├── execution_logs.json #   执行日志
    ├── node_outputs.yaml   #   节点输出
    ├── token_usage_*.json  #   Token 用量统计
    └── workflow_summary.yaml #  工作流摘要
```

### `data/` — 数据存储

```
data/
└── vuegraphs.db            # 可视化图 SQLite 数据库
```

### `docs/` — 用户文档

```
docs/user_guide/
├── en/                     # 英文文档（9个文件）
└── zh/                     # 中文文档（8个文件）
```

### `assets/` — 静态资源

```
assets/
├── cases/                  # 案例资源
└── *.png / *.gif           # README 用图片与动图
```

### `logs/` — 运行日志

```
logs/
└── server.log              # 服务运行日志
```

### `mcp_example/` — MCP 示例

```
mcp_example/
└── mcp_server.py           # MCP 服务器示例
```

### `tests/` — 测试

```
tests/
├── test_mem0_memory.py              # Mem0 记忆测试
├── test_memory_embedding_consistency.py # 记忆嵌入一致性测试
├── test_server_main_reload.py       # 服务热重载测试
└── test_websocket_send_message_sync.py  # WebSocket 同步消息测试
```

### `.agents/skills/` — Agent 技能定义

```
.agents/skills/
├── greeting-demo/          # 问候演示技能
├── python-scratchpad/      # Python 代码草稿本技能
└── rest-api-caller/        # REST API 调用技能
```

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3)                      │
│          可视化画布 / 工作流编辑 / 批量运行              │
└────────────────────────┬────────────────────────────────┘
                         │ REST / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                   Server (FastAPI)                       │
│     路由层 ── 服务层 ── 状态管理                         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                Workflow Engine                           │
│  图构建 ── 拓扑分析 ── 执行调度 ── 循环控制             │
└──────────┬──────────────┬──────────────┬────────────────┘
           │              │              │
┌──────────▼──────┐ ┌────▼─────────┐ ┌──▼────────────────┐
│  Node Runtime   │ │ Edge Runtime │ │   Functions       │
│  Agent/Human/   │ │ 条件判断/    │ │ 文件/网页/代码/   │
│  Python/Subgraph│ │ 数据处理     │ │ 研究/视频/天气    │
└─────────────────┘ └──────────────┘ └───────────────────┘
```
