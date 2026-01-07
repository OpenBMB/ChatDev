# 附件与工件 API 指南

**说明**：此文档面向高级用户，一般场景下无需直接调用附件/工件 API，前端会自行处理。

附件（Attachment）是 Session 生命周期内可上传、下载、由节点注册的文件；工件（Artifact）是对附件事件的抽象，用于实时监听。本文档汇总 REST/WS 接口及存储策略，填补旧版 `frontend_attachment_api.md` 的缺口。

## 1. 上传与列举
### 1.1 上传文件
`POST /api/uploads/{session_id}`
- **Headers**：`Content-Type: multipart/form-data`
- **Form 字段**：`file`（单个文件）。
- **响应**：
  ```json
  {
    "attachment_id": "att_bxabcd",
    "name": "spec.md",
    "mime": "text/markdown",
    "size": 12345
  }
  ```
- 文件保存到 `WareHouse/<session>/code_workspace/attachments/`，并记录在 `attachments_manifest.json`。

### 1.2 列举附件
`GET /api/uploads/{session_id}`
- 返回该 Session 当前所有附件的元数据（ID、文件名、mime、大小、来源）。

### 1.3 在执行请求中引用
- `POST /api/workflow/execute` 或 WebSocket `human_input` 消息中可带 `attachments: ["att_xxx"]`，并必须同时提供 `task_prompt`（即便只想上传文件）。

## 2. 工件事件与下载
### 2.1 实时事件
`GET /api/sessions/{session_id}/artifact-events`
- Query：`after`, `wait_seconds`, `include_mime`, `include_ext`, `max_size`, `limit`。
- 响应含 `events[]`, `next_cursor`, `has_more`, `timed_out`。
- 每条事件：
  ```json
  {
    "artifact_id": "art_123",
    "attachment_id": "att_456",
    "node_id": "python_runner",
    "path": "code_workspace/result.json",
    "size": 2048,
    "mime": "application/json",
    "hash": "sha256:...",
    "timestamp": 1732699900
  }
  ```
- WebSocket 会镜像此事件（类型 `artifact_created`），前端可直接订阅。

### 2.2 下载单个工件
`GET /api/sessions/{session_id}/artifacts/{artifact_id}`
- Query：`mode=meta|stream`, `download=true|false`。
- **meta**：仅返回元数据。
- **stream**：返回文件内容；`download=true` 时附带 `Content-Disposition`。
- 小文件可选择 `data_uri` 内联（若服务器启用）。

### 2.3 打包下载 Session
`GET /api/sessions/{session_id}/download`
- 将 `WareHouse/<session>/` 打包为 zip，供一次性下载。

## 3. 文件生命周期
1. 上传：写入 `code_workspace/attachments/`，manifest 记录 `source`、`workspace_path`、`storage` 等字段。
2. Python 节点或工具可调用 `AttachmentStore.register_file()` 把 workspace 文件注册为附件；`WorkspaceArtifactHook` 会将其同步到事件流。
3. 默认保留所有附件，便于运行结束后下载。如果希望自动清理，设置 `MAC_AUTO_CLEAN_ATTACHMENTS=1`（只在 Session 完成后删除 `attachments/` 目录）。
4. WareHouse 打包下载不会删除原文件，需要额外策略（cron/job）做归档或清空。

## 4. 大小与安全建议
- **大小限制**：后端未硬编码，可在反向代理设置 `client_max_body_size`、`max_request_body_size`，或在自定义分支的 `AttachmentService.save_upload_file` 中添加校验。
- **文件类型**：基于 MIME 推断 `MessageBlockType`（image/audio/video/file）；可结合 `include_mime` 过滤。
- **病毒/敏感信息**：上传前由客户端自查；必要时在保存后触发扫描服务。
- **权限**：Attachment API 依赖 Session ID；生产部署应在代理层或 JWT 内部校验调用者身份，避免越权下载。

## 5. 常见问题
| 问题 | 排查步骤 |
| --- | --- |
| 上传 413/413 Payload Too Large | 调整反向代理或 FastAPI `client_max_size`，确认磁盘配额 |
| 下载链接 404 | 确认 `session_id` 拼写（仅允许字母/数字/`_-`），检查 Session 是否已被清理 |
| 工件事件缺失 | 确认 WebSocket 是否连接，或在 REST 事件接口中使用 `after` 游标重拉 |
| 附件未在 Python 节点可见 | 检查 `code_workspace/attachments/` 是否被清理、或 `_context['python_workspace_root']` 是否正确 |

## 6. 客户端实现建议
- Web UI：使用 `artifact-events` 长轮询或 WebSocket，实时刷新附件列表；在节点成功后提供“下载全部”按钮。
- CLI/自动化：在运行结束后调用 `/download` 拉取 zip；若仅需部分文件，可结合 `artifact-events` 的 `include_ext` 精准过滤。
- 测试环境：可通过脚本模拟上传/下载流程，确保反向代理和 CORS 配置正确。
