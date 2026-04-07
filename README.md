# MovieDev

<p align="center">
  <img src="frontend/public/media/logo.png" alt="MovieDev Logo" width="420"/>
</p>

<p align="center">
  <strong>一个正在改造中的“人类导演式”多智能体工作台</strong>
</p>

## 📖 项目说明

MovieDev 是基于上游多智能体工作流运行时做的一次二次改造。目前它更准确的状态是：**可运行的改造原型 / 半成品工作台**，而不是一个已经打磨完成的成熟 SaaS 产品。

这次改造的目标不是推翻原有运行时，也不是做一个 Dify 或 LangGraph 的完整替代品，而是把原来的“工作流引擎 + 原型 UI”推进成一个更接近 **人可以看见、干预、回溯和导演的多智能体控制台**。

这次改造主要集中在几件事：

1. 中文优先的工作台和更直接的主导航
2. 多模型命名配置，避免频繁改 API 地址和密钥
3. 团队状态、审批点、review 返工、replay 续跑
4. 模板化编排和本地模板资产管理
5. 更适合“人参与过程”的构建-运行闭环

## ⚠️ 当前状态

这个仓库现在适合：

* 本地运行和继续二次开发
* 验证多 agent 编排、人工审批、replay、接力和技能/MCP 集成思路
* 做内部原型、演示和小范围试用

暂时不建议直接当作生产级产品使用。当前仍然存在这些明显边界：

* UI 已做中文化和重排，但还没有完整设计系统，部分页面仍在持续收口
* `handoffs`、AI 路由接力、审批和 replay 已经有后端能力，但还需要更多实际 workflow 样例验证
* ClawHub 与 MCP 是“预设入口 + 安装/注入能力”，不是全量内置市场
* 外部触发接口默认面向本地或内网环境，公网使用前需要额外鉴权、签名校验和限流
* 工作流样例里仍可能有历史遗留配置，需要按实际用途继续整理

## 🎬 为什么做这次改造

上游引擎本身很强，但原始产品体验还有几个明显痛点：

1. 关键判断、回溯和协作过程埋在 prompt 与日志里
2. 一旦运行起来，人想插手并不顺畅
3. 多模型切换成本高
4. 默认 UI 更像内部原型，而不是一个导演控制台

MovieDev 的方向不是做“更黑盒的自动化”，而是把这些过程尽量外显，让人可以真正参与 agent team 的推进。

简单说：

* Dify 更像标准化 AI 应用流水线
* LangGraph 更像面向开发者的状态图 runtime
* MovieDev 这版更想做“导演台”：让人可以看到计划、记忆、审批、返工、接力和工具能力分布

这也是为什么它现在看起来不像一个“完成品”，而更像一个正在从工作流工具向 agent team cockpit 演进的项目。

## 🚀 快速开始

### 📋 环境要求

* **操作系统**：macOS / Linux / WSL / Windows
* **Python**：3.12+
* **Node.js**：18+
* **包管理器**：[uv](https://docs.astral.sh/uv/)

### 📦 安装

1. 安装后端依赖：
   ```bash
   uv sync
   ```
2. 安装前端依赖：
   ```bash
   cd frontend && npm install
   ```

### 🔑 配置

1. 复制环境变量模板：
   ```bash
   cp .env.example .env
   ```
2. 在 `.env` 中填写默认模型提供商的 `API_KEY` 和 `BASE_URL`。
3. 在 YAML 中使用 `${API_KEY}`、`${BASE_URL}` 这类占位符进行运行时注入。
4. 在 Web 设置页中，也可以维护多套命名模型配置，并在运行时切换。

## ⚡️ 一键本地启动

MovieDev 附带了按操作系统区分的启动脚本，会同时拉起后端和前端，并把日志写到 `logs/`。

### macOS / Linux / WSL

```bash
bash scripts/dev.sh
```

停止：

```bash
bash scripts/stop.sh
```

也可以使用：

```bash
make dev-local
```

### Windows PowerShell

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

停止：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

### Windows CMD

```bat
scripts\dev.bat
```

停止：

```bat
scripts\stop.bat
```

### 可选环境变量

启动脚本支持这些可选变量：

* `BACKEND_HOST` 默认：`127.0.0.1`
* `BACKEND_PORT` 默认：`6400`
* `FRONTEND_HOST` 默认：`127.0.0.1`
* `FRONTEND_PORT` 默认：`5173`
* `BACKEND_RELOAD` 默认：`0`

例如：

```bash
BACKEND_PORT=6401 FRONTEND_PORT=5174 BACKEND_RELOAD=1 bash scripts/dev.sh
```

启动后可访问：

* 前端：`http://127.0.0.1:5173`
* 后端健康检查：`http://127.0.0.1:6400/health`
* 后端就绪检查：`http://127.0.0.1:6400/health/ready`

日志文件：

* `logs/dev-backend.log`
* `logs/dev-frontend.log`

## 🧰 手动启动

1. 启动后端：
   ```bash
   uv run python server_main.py --host 127.0.0.1 --port 6400
   ```
2. 启动前端：
   ```bash
   cd frontend
   VITE_API_BASE_URL=http://127.0.0.1:6400 npm run dev -- --host 127.0.0.1 --port 5173
   ```

`--reload` 可以按需自行开启，但默认不打开，因为会生成文件的工作流很容易触发重启，打断当前任务。

## 🛠 常用命令

* 帮助命令：
  ```bash
  make help
  ```
* 停止 macOS / Linux 启动脚本：
  ```bash
  make stop-local
  ```
* 同步 YAML 工作流到前端：
  ```bash
  make sync
  ```
* 校验所有 YAML 工作流：
  ```bash
  make validate-yamls
  ```

## 💡 如何使用

### Web 控制台

MovieDev 更强调“人参与过程”的构建和运行闭环：

* **工作流工作台**：设计 agent team、套用模板、管理本地模板资产，并在需要时直接编辑 YAML。
<img src="assets/workflow.gif"/>

* **运行控制台**：启动工作流、查看团队状态、review 建议、审批门和 replay 返工链路。
<img src="assets/launch.gif"/>

* **批量实验室**：保留批处理入口，但不再作为默认主入口。

## 🧩 内置 Skills 与 MCP 预设

MovieDev 现在已经预置了一批更贴近实际使用场景的 skills 和模板，不再只保留最小示例。

### 已内置的 Skills

当前仓库内置 skill 位于 `.agents/skills/`，包括：

* `python-scratchpad`：适合快速计算、数据转换和脚本验证
* `rest-api-caller`：适合 REST API 调用与 JSON 结果提取
* `browser-researcher`：适合网页搜索、证据采集和研究摘要
* `repo-analyst`：适合代码仓结构分析、入口定位和风险梳理
* `report-orchestrator`：适合多章节报告的持续编排与导出
* `content-packager`：适合把研究结果整理成更适合发布的内容

当前仓库已经把上游遗留示例大幅精简。如果本地 `yaml_instance/` 里没有可直接运行的主工作流，可以先在 Web 工作台中新建工作流，或者从模板库套用一套 agent team 骨架后再运行。

### ClawHub 安装入口

MovieDev 现在也会自动发现工作区 `skills/` 目录中的技能。这意味着：

1. 仓库内置技能仍然放在 `.agents/skills/`
2. 通过 ClawHub CLI 安装到当前项目的技能，只要进入 `skills/`，MovieDev 也能直接识别

仓库已经附带了一份 ClawHub starter 清单：

* [tools/clawhub_featured_skills.json](./tools/clawhub_featured_skills.json)

并提供了一个安装脚本：

```bash
python scripts/install_clawhub_skills.py --list-packs
python scripts/install_clawhub_skills.py --pack starter --dry-run
python scripts/install_clawhub_skills.py --pack starter
```

如果你更希望走界面操作，也可以直接在：

* `设置 -> ClawHub 技能包`

里查看 starter packs、先做“试装预览”，再执行正式安装。安装后，MovieDev 会自动刷新当前可发现的 skills 列表；每个技能包也会附带推荐的 MCP 预设和团队模板，并支持一键跳转到工作流页查看推荐模板。

同一个设置面板里还提供了一组热门 MCP 预设目录，包含：

* 默认服务地址
* 适用场景说明
* 可直接复制的 `tooling` 片段
* 当前服务在线状态检测
* 一键跳到当前 workflow 并注入到指定 agent 节点
* 推荐 MCP 组合可一次性注入到同一个 agent
* 节点卡片上直接显示已挂载的 MCP 前缀徽标

适合在你手动配置 agent tooling 时直接粘贴使用。

可选安装包：

* `starter`
* `research`
* `coding`

如果你只想额外安装某几个技能，也可以：

```bash
python scripts/install_clawhub_skills.py --skill agent-browser --skill agent-brain
```

前提：

* 机器上已安装 `clawhub` CLI
* 当前项目根目录允许生成 `skills/` 目录

这条链路的目标不是把 ClawHub 全量 vendoring 进仓库，而是给 MovieDev 留一个稳定的“可安装热门技能入口”。

### 已预置的热门 MCP 模板方向

参考 ClawHub 的 skill bundle 思路，以及官方 MCP servers 常见组合，MovieDev 在模板库里新增了这几类预设团队：

* **浏览器研究 MCP 团队**：对应 `fetch / browser` 风格能力，适合网页调研与证据整理
* **仓库分析 MCP 团队**：对应 `filesystem / git / github` 风格能力，适合代码仓理解和修改前分析
* **技能驱动研究写作团队**：先用内置 skills 做研究和章节编排，再做最终内容包装

这些模板可以在工作流编辑页的模板弹窗里直接找到，分类位于 `Skills` 和 `MCP`。

### 推荐优先接入的 MCP 家族

如果你准备继续扩展，我建议优先接这些高频能力：

* `filesystem`
* `git`
* `github`
* `fetch`
* `memory`
* `postgres`

这几类能力对研究、编码、审阅和回溯都很有帮助，而且和 MovieDev 当前的人机协作工作台最契合。

## 🔔 触发点与外部应用接入

除了在运行控制台里手动对话执行，MovieDev 也支持把工作流作为外部应用或机器人消息的触发目标。

在工作流编辑页中，可以通过右上角菜单里的 **管理触发点** 维护 `graph.triggers`。它是一个轻量元数据区，用来记录这个工作流允许哪些入口触发，例如：

```yaml
graph:
  triggers:
    bot_message: "机器人消息转发到 /api/triggers/run"
    app_webhook: "业务系统事件通过 HTTP POST 触发"
```

外部应用可以直接调用：

```bash
curl -X POST http://127.0.0.1:6400/api/triggers/run \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_file": "your_workflow.yaml",
    "source": "bot_message",
    "event": "message.created",
    "message": "请把这条用户消息交给技能驱动研究写作团队处理",
    "payload": {
      "user_id": "u_001",
      "channel": "demo"
    }
  }'
```

这个接口适合先接：

* 机器人消息：企业微信、飞书、Telegram、Discord 等平台先把消息转成 HTTP 请求
* 业务应用事件：表单提交、工单创建、CRM 更新、内容发布任务
* 自动化系统：由 n8n、Zapier、GitHub Actions 或内部调度器发起

注意：当前触发接口默认面向本地或内网使用。如果要暴露到公网，请先加鉴权、签名校验和速率限制。

## 🔗 工作流接力

如果一个工作流跑完后的结果需要继续交给另一个工作流，可以在上游工作流的 `graph.handoffs` 中声明接力目标。

最小示例：

```yaml
graph:
  id: research_first
  handoffs:
    - target_workflow: writer_review.yaml
      input_from: final_message
```

更完整的示例：

```yaml
graph:
  id: research_first
  handoffs:
    - id: send_to_writer
      enabled: true
      target_workflow: writer_review.yaml
      input_from: final_message
      prompt_prefix: "请基于上游研究结果继续写作和审阅。"
      variables:
        MODEL_NAME: "${MODEL_NAME}"
```

支持的常用字段：

* `target_workflow`：下一个 workflow 文件名，支持省略 `.yaml`
* `input_from`：传递内容来源，常用 `final_message`、`results`、`json`、`token_usage`
* `prompt_prefix`：追加给下游工作流的说明
* `prompt_template`：自定义传递模板，可使用 `{final_message}`、`{source_workflow}`、`{results_json}`、`{token_usage_json}`、`{payload_json}`
* `variables`：传给下游工作流的变量覆盖
* `enabled`：是否启用这条接力

运行控制台里，WebSocket 会在接力时发出：

* `workflow_handoff_started`
* `workflow_handoff_completed`
* `workflow_handoff_failed`
* `workflow_handoffs_completed`

同步 API `/api/workflow/run` 和触发 API `/api/triggers/run` 也会在返回 JSON 中带上 `handoffs` 字段。这样你既可以在页面里观察接力状态，也可以用 API 把多个工作流串成一条自动化链路。

### AI 判断接力方向

如果不是固定传给某一个工作流，而是希望由 AI 判断“交给 B、交给 C，还是停止”，可以使用 `mode: route`：

```yaml
graph:
  id: workflow_a
  handoffs:
    - id: ai_router
      mode: route
      router_workflow: route_decider.yaml
      input_from: final_message
      routes:
        send_to_b: workflow_b.yaml
        send_to_c: workflow_c.yaml
        stop: ""
```

其中 `route_decider.yaml` 是一个轻量判断工作流。系统会把上游输出和可选路由发给它，并要求它输出类似：

```json
{"route": "send_to_b", "reason": "结果更适合进入写作流程"}
```

如果返回 `stop`，系统会记录接力状态为 `stopped`，不会继续触发下游工作流。

### Python SDK

对于自动化和批量处理，可以直接使用 SDK 调用运行时：

```python
from runtime.sdk import run_workflow

result = run_workflow(
    yaml_file="yaml_instance/demo.yaml",
    task_prompt="用一句话总结附件文档。",
    attachments=["/path/to/document.pdf"],
    variables={"API_KEY": "sk-xxxx"}
)

if result.final_message:
    print(result.final_message.text_content())
```

## ⚙️ 给开发者

如果你打算继续做二次开发，核心目录大致如下：

* `server/`：FastAPI 后端和会话执行链路
* `runtime/`：agent 抽象与工具执行
* `workflow/`：图编排和运行时逻辑
* `entity/`：配置 schema
* `frontend/`：Vue 3 工作台
* `functions/`：自定义 Python 工具

相关文档：

* 快速开始：[docs/user_guide/zh/index.md](./docs/user_guide/zh/index.md)
* 工作流编写：[docs/user_guide/zh/workflow_authoring.md](./docs/user_guide/zh/workflow_authoring.md)
* Memory 模块：[docs/user_guide/zh/modules/memory.md](./docs/user_guide/zh/modules/memory.md)
* Tooling 模块：[docs/user_guide/zh/modules/tooling/README.md](./docs/user_guide/zh/modules/tooling/README.md)
