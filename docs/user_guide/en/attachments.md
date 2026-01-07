# Attachment & Artifact API Guide

> Audience: operators integrating directly with backend REST/WS endpoints. The Web UI already handles most scenarios.

Attachments are files that can be uploaded, downloaded, or registered during a session. Artifacts are events emitted when attachments change so clients can listen in real time. This guide summarizes the REST endpoints, WebSocket mirrors, and storage policies.

## 1. Upload & List
### 1.1 Upload file
`POST /api/uploads/{session_id}`
- Headers: `Content-Type: multipart/form-data`
- Form field: `file`
- Response:
  ```json
  {
    "attachment_id": "att_bxabcd",
    "name": "spec.md",
    "mime": "text/markdown",
    "size": 12345
  }
  ```
- Files land in `WareHouse/<session>/code_workspace/attachments/` and are recorded in `attachments_manifest.json`.

### 1.2 List attachments
`GET /api/uploads/{session_id}`
- Returns metadata for all attachments in the session (ID, file name, mime, size, source).

### 1.3 Reference in execution requests
- `POST /api/workflow/execute` or WebSocket `human_input` payloads can include `attachments: ["att_xxx"]`. You still must supply `task_prompt`, even when you only want file uploads.

## 2. Artifact Events & Downloads
### 2.1 Real-time artifact events
`GET /api/sessions/{session_id}/artifact-events`
- Query params: `after`, `wait_seconds`, `include_mime`, `include_ext`, `max_size`, `limit`.
- Response includes `events[]`, `next_cursor`, `has_more`, `timed_out`.
- Event sample:
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
- WebSocket emits the same data via `artifact_created`, so dashboard clients can subscribe live.

### 2.2 Download a single artifact
`GET /api/sessions/{session_id}/artifacts/{artifact_id}`
- Query: `mode=meta|stream`, `download=true|false`.
- `meta` → metadata only; `stream` → file content. Add `download=true` to include `Content-Disposition`.
- Small files may be returned as `data_uri` when the server enables it.

### 2.3 Download an entire session
`GET /api/sessions/{session_id}/download`
- Packages `WareHouse/<session>/` into a zip for batch download.

## 3. File Lifecycle
1. Upload stage: files go under `code_workspace/attachments/`, and the manifest records `source`, `workspace_path`, `storage`, etc.
2. Python nodes/tools can call `AttachmentStore.register_file()` to turn workspace files into attachments; `WorkspaceArtifactHook` syncs events.
3. By default we retain all attachments for post-run downloads. Set `MAC_AUTO_CLEAN_ATTACHMENTS=1` to delete the `attachments/` directory after the session completes.
4. WareHouse zip downloads do **not** delete originals; schedule your own archival/cleanup jobs.

## 4. Size & Security
- **Size limits**: No hard cap in backend; enforce via reverse proxy (`client_max_body_size`, `max_request_body_size`) or customize `AttachmentService.save_upload_file`.
- **File types**: MIME detection controls `MessageBlockType` (image/audio/video/file); filter via `include_mime` as needed.
- **Virus/sensitive data**: Clients should pre-scan uploads; you can also trigger scanning services after save.
- **Permissions**: Attachment APIs require the session ID. In production guard with proxy-layer auth or internal JWT checks to prevent unauthorized downloads.

## 5. FAQ
| Issue | Mitigation |
| --- | --- |
| Upload 413 Payload Too Large | Raise proxy limits or FastAPI `client_max_size`; confirm disk quota. |
| Download link 404 | Check `session_id` spelling (allowed chars: letters/digits/`_-`) and confirm the session hasn’t been purged. |
| Missing artifact events | Ensure WebSocket is connected or use `artifact-events` REST polling with the `after` cursor. |
| Attachment not visible in Python node | Verify `code_workspace/attachments/` hasn’t been cleaned and `_context[python_workspace_root]` is correct. |

## 6. Client Patterns
- **Web UI**: Use artifact long-polling or WebSocket to refresh lists in real time; offer a “download all” button once nodes finish.
- **CLI/automation**: After runs complete, call `/download` for the zip; if you need just a subset, combine `artifact-events` with `include_ext` filters.
- **Test rigs**: Script the upload/download flow to validate proxy limits and CORS before shipping.
