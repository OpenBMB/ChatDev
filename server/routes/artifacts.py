import asyncio
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from server.state import get_websocket_manager
from utils.attachments import encode_file_to_data_uri

router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def _split_csv(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    filtered = [part for part in parts if part]
    return filtered or None


def _get_session_and_queue(session_id: str):
    manager = get_websocket_manager()
    session = manager.session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    queue = session.artifact_queue
    if queue is None:
        raise HTTPException(status_code=404, detail="Artifact stream not available")
    return manager, queue


@router.get("/api/sessions/{session_id}/artifact-events")
async def poll_artifact_events(
    session_id: str,
    wait_seconds: float = Query(25.0, ge=0.0, le=60.0),
    after: Optional[int] = Query(None, ge=0),
    include_mime: Optional[str] = Query(None),
    include_ext: Optional[str] = Query(None),
    max_size: Optional[int] = Query(None, gt=0),
    limit: int = Query(25, ge=1, le=100),
):
    manager, queue = _get_session_and_queue(session_id)
    include_mime_list = _split_csv(include_mime)
    include_ext_list = _split_csv(include_ext)

    events, next_cursor, timed_out = await asyncio.to_thread(
        queue.wait_for_events,
        after=after,
        include_mime=include_mime_list,
        include_ext=include_ext_list,
        max_size=max_size,
        limit=limit,
        timeout=wait_seconds,
    )

    payload = {
        "events": [event.to_dict() for event in events],
        "next_cursor": next_cursor,
        "timed_out": timed_out,
        "has_more": queue.last_sequence > (next_cursor or 0),
    }
    return payload


@router.get("/api/sessions/{session_id}/artifacts/{artifact_id}")
async def get_artifact(
    session_id: str,
    artifact_id: str,
    mode: str = Query("meta", pattern="^(meta|stream)$"),
    download: bool = Query(False),
):
    manager, _ = _get_session_and_queue(session_id)
    store = manager.attachment_service.get_attachment_store(session_id)
    record = store.get(artifact_id)
    if not record:
        raise HTTPException(status_code=404, detail="Artifact not found")

    ref = record.ref
    if mode == "stream":
        local_path = ref.local_path
        if not local_path:
            raise HTTPException(status_code=404, detail="Artifact content unavailable")
        path = Path(local_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Artifact file missing")
        media_type = ref.mime_type or "application/octet-stream"
        disposition = "attachment" if download else "inline"
        headers = {"Content-Disposition": f'{disposition}; filename="{ref.name}"'}
        return StreamingResponse(path.open("rb"), media_type=media_type, headers=headers)

    data_uri = ref.data_uri
    if not data_uri and ref.local_path and (ref.size or 0) <= MAX_FILE_SIZE:
        local_path = Path(ref.local_path)
        if local_path.exists():
            data_uri = encode_file_to_data_uri(local_path, ref.mime_type or "application/octet-stream")
    return {
        "artifact_id": artifact_id,
        "name": ref.name,
        "mime_type": ref.mime_type,
        "size": ref.size,
        "sha256": ref.sha256,
        "data_uri": data_uri,
        "local_path": ref.local_path,
        "extra": record.extra,
    }
