"""WebSocket endpoint routing."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.state import get_websocket_manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    manager = get_websocket_manager()
    session_id = await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await manager.handle_message(session_id, message)
    except WebSocketDisconnect:
        manager.disconnect(session_id)
