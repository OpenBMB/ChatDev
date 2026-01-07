# DevAll Backend User Guide (English)

This landing page helps operators, workflow authors, and extension developers find the right documentation for DevAll backend components. Use the table below as your navigation map; drill into the linked chapters for full procedures and examples.

## 1. Documentation Map

| Topic | Highlights |
| --- | --- |
| [Web UI Quick Start](web_ui_guide.md) | Frontend interface operations, workflow execution, human review, troubleshooting. |
| [Workflow Authoring](workflow_authoring.md) | YAML structure, node types, provider/edge conditions, template export, CLI execution. |
| [Graph Execution Logic](execution_logic.md) | DAG/cyclic graph execution, Tarjan cycle detection, super node construction, recursive cycle execution. |
| [Dynamic Parallel Execution](dynamic_execution.md) | Map/Tree modes, split strategies, parallel processing and hierarchical reduction. |
| [Memory Module](modules/memory.md) | Memory list architecture, built-in `simple`/`file`/`blackboard` behaviors, embedding config, troubleshooting. |
| [Thinking Module](modules/thinking.md) | Reasoning enhancement, self-reflection mode, extending custom thinking modes. |
| [Tooling Module](modules/tooling/README.md) | Function/MCP modes, context injection, built-in function catalog, MCP launch patterns. |
| [Node Types Reference](nodes/) | Agent, Python, Human, Subgraph, Passthrough, Literal, Loop Counter node configurations. |
| [Attachment & Artifact APIs](attachments.md) | Upload/list/download endpoints, manifest schema, cleanup strategies, security constraints. |
| [`FIELD_SPECS` Standard](field_specs.md) | Field metadata contract that powers UI forms and template export—required reading before customizing modules. |
| [Config Schema API Contract](config_schema_contract.md) | `/api/config/schema(*)` request examples and breadcrumbs protocol (mostly for frontend/IDE integrations). |

## 2. Product Overview (Backend Focus)
- **Workflow orchestration engine**: Parses YAML DAGs, coordinates `model`, `python`, `tooling`, and `human` nodes inside a shared context, and writes node outputs into `WareHouse/<session>/`.
- **Provider abstraction**: The `runtime/node/agent/providers/` layer encapsulates OpenAI, Gemini, and other APIs so each node can swap models, base URLs, credentials, plus optional `thinking` and `memories` settings.
- **Real-time observability**: FastAPI + WebSocket streams node states, stdout/stderr, and artifact events to the Web UI, while structured logs land in `logs/` for centralized collection.
- **Run asset management**: Every execution creates an isolated session; attachments, Python workspace, context snapshots, and summary outputs are downloadable for later review.

## 3. Architecture & Execution Flow
1. **Entry**: Web UI and CLI call the FastAPI server exposed via `server_main.py` (e.g., `/api/workflow/execute`).
2. **Validation/queueing**: `WorkflowRunService` validates YAML, creates a session, prepares `code_workspace/attachments/`, then hands the DAG to the scheduler in `workflow/`.
3. **Execution**: Node executors resolve dependencies, propagate context, call tools, and retrieve memories; `MemoryManager`, `ToolingConfig`, and `ThinkingManager` trigger inside agent nodes as needed.
4. **Observability**: WebSocket pushes states, logs, and artifact events; JSON logs stay in `logs/`, and `WareHouse/` stores run assets.
5. **Cleanup & download**: After completion you can bundle the session for download or fetch files individually via the attachment APIs; retention policies are deployment-specific.

## 4. Role-based Navigation
- **Solutions/Prompt Engineers**: Begin with [Workflow Authoring](workflow_authoring.md); read the Memory and Tooling module docs when you need context memories or custom tools.
- **Extension Developers**: Combine [`FIELD_SPECS`](field_specs.md) with the [Tooling module guide](modules/tooling/README.md) to register new components; reference [config_schema_contract.md](config_schema_contract.md) if you need to debug schema-driven UI.

## 5. Glossary
- **Session**: Unique ID (timestamp + name) for a single run, used across the Web UI, backend, and `WareHouse/`.
- **code_workspace**: Shared directory for Python nodes at `WareHouse/<session>/code_workspace/`, synchronized with relevant attachments.
- **Attachment**: Files uploaded by users or generated during runs; list/download via REST or WebSocket APIs.
- **Memory Store / Attachment**: Stores define persistence backends; memory attachments describe how agent nodes read/write those stores across phases.
- **Tooling**: Execution environment bound to agent nodes (Function or MCP implementations).

If you spot gaps or outdated instructions, open an issue/PR or edit the docs directly (remember to keep Chinese and English versions in sync).
