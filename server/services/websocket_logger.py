import asyncio
from typing import Any, Dict

from entity.enums import LogLevel, EventType
from utils.logger import WorkflowLogger, LogEntry
from utils.structured_logger import get_workflow_logger


class WebSocketLogger(WorkflowLogger):
    """Workflow logger that also pushes entries via WebSocket."""

    def __init__(self, websocket_manager, session_id: str, workflow_id: str = None, log_level: LogLevel = LogLevel.DEBUG):
        super().__init__(workflow_id, log_level, log_to_console=False)
        self.websocket_manager = websocket_manager
        self.session_id = session_id

    def add_log(self, level: LogLevel, message: str = None, node_id: str = None,
                event_type: EventType = None, details: Dict[str, Any] = None,
                duration: float = None) -> LogEntry | None:
        log_entry = super().add_log(level, message, node_id, event_type, details, duration)
        if not log_entry:
            return None

        # Send the message using the sync method which handles event loop properly
        self.websocket_manager.send_message_sync(self.session_id, {
            "type": "log",
            "data": log_entry.to_dict()
        })
        
        return log_entry
