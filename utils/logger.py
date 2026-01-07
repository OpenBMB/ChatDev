import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import copy
import traceback

from entity.enums import CallStage, EventType, LogLevel
from utils.structured_logger import StructuredLogger, LogType, get_workflow_logger
from utils.exceptions import MACException


def _json_safe(value: Any) -> Any:
    """Recursively convert objects into JSON-encodable primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_safe(to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return _json_safe(vars(value))
        except Exception:
            pass
    return str(value)


@dataclass
class LogEntry:
    """Single log entry that captures execution details."""
    timestamp: str
    level: LogLevel
    node_id: Optional[str] = None
    event_type: Optional[EventType] = None
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    execution_path: List[str] = field(default_factory=list)  # Execution path for tracing
    duration: Optional[float] = None  # Duration in seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "node_id": self.node_id,
            "event_type": self.event_type,
            "message": self.message,
            "details": self.details,
            "execution_path": self.execution_path,
            "duration": self.duration
        }


class WorkflowLogger:
    """Workflow logger that tracks the entire execution lifecycle."""

    def __init__(self, workflow_id: str = None, log_level: LogLevel = LogLevel.DEBUG, use_structured_logging: bool = True, log_to_console: bool = True):
        self.workflow_id = workflow_id or f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.logs: List[LogEntry] = []
        self.start_time = datetime.now()
        self.current_path: List[str] = []
        self.log_level: LogLevel = log_level

        self.log_to_console: bool = log_to_console
        self.use_structured_logging = use_structured_logging
        self.structured_logger: Optional[StructuredLogger] = None
        if use_structured_logging:
            self.structured_logger = get_workflow_logger(self.workflow_id)

    def add_log(self, level: LogLevel, message: str = None, node_id: str = None,
                event_type: EventType = None, details: Dict[str, Any] = None,
                duration: float = None) -> LogEntry | None:
        """Add a log entry."""
        if level < self.log_level:
            return None

        timestamp = datetime.now().isoformat()
        execution_path = copy.deepcopy(self.current_path)

        safe_details = _json_safe(details or {})

        log_entry = LogEntry(
            timestamp=timestamp,
            level=level,
            node_id=node_id,
            event_type=event_type,
            message=message,
            details=safe_details,
            execution_path=execution_path,
            duration=duration
        )
        self.logs.append(log_entry)

        # Log to console if enabled
        if self.log_to_console:
            print(f"[{timestamp}] [{level.value}] "
                  f"{f'Node {node_id} - ' if node_id else ''}"
                  f"{f'Event {event_type} - ' if event_type else ''}"
                  f"{message} "
                  f"{f'Details: {details} ' if details else ''}"
                  f"{f'Duration: {duration}' if duration else ''}")
        
        # Log using structured logger if enabled
        if self.use_structured_logging and self.structured_logger:
            structured_details = {
                "workflow_id": self.workflow_id,
                "node_id": node_id,
                "event_type": event_type.value if event_type else None,
                "execution_path": execution_path,
                "duration": duration,
                **safe_details
            }
            
            if level == LogLevel.DEBUG:
                self.structured_logger.debug(message, **structured_details)
            elif level == LogLevel.INFO:
                self.structured_logger.info(message, **structured_details)
            elif level == LogLevel.WARNING:
                self.structured_logger.warning(message, **structured_details)
            elif level == LogLevel.ERROR:
                self.structured_logger.error(message, **structured_details)
            elif level == LogLevel.CRITICAL:
                self.structured_logger.critical(message, **structured_details)

        return log_entry

    def debug(self, message: str, node_id: str = None, event_type: EventType = None,
              details: Dict[str, Any] = None, duration: float | None = None) -> None:
        self.add_log(LogLevel.DEBUG, message, node_id, event_type, details, duration)

    def info(self, message: str, node_id: str = None, event_type: EventType = None,
             details: Dict[str, Any] = None, duration: float | None = None) -> None:
        self.add_log(LogLevel.INFO, message, node_id, event_type, details, duration)

    def warning(self, message: str, node_id: str = None, event_type: EventType = None,
                details: Dict[str, Any] = None, duration: float | None = None) -> None:
        self.add_log(LogLevel.WARNING, message, node_id, event_type, details, duration)

    def error(self, message: str, node_id: str = None, event_type: EventType = None,
              details: Dict[str, Any] = None, duration: float | None = None) -> None:
        self.add_log(LogLevel.ERROR, message, node_id, event_type, details, duration)

    def critical(self, message: str, node_id: str = None, event_type: EventType = None,
                 details: Dict[str, Any] = None) -> None:
        self.add_log(LogLevel.CRITICAL, message, node_id, event_type, details)

    def enter_node(self, node_id: str, inputs: List[Dict[str, str]], node_type: str = None,
                   details: Dict[str, Any] = None) -> None:
        """Record data when entering a node."""
        self.current_path.append(node_id)
        self.info(
            f"Entering node {node_id}",
            node_id=node_id,
            event_type=EventType.NODE_START,
            details={
                "inputs": inputs,
                # "combined_input": combined_input,
                "node_type": node_type,
                **(details or {})
            }
        )

    def exit_node(self, node_id: str, output: str, duration: float = None,
                  output_size: int = None, details: Dict[str, Any] = None) -> None:
        """Record data when exiting a node."""
        # Keep enter and exit logs separate so we can easily identify progress
        if self.current_path and self.current_path[-1] == node_id:
            self.current_path.pop()

        exit_details = {
            "output": output,
            "output_size": output_size,
            **(details or {})
        }

        self.info(
            f"Exiting node {node_id}",
            node_id=node_id,
            event_type=EventType.NODE_END,
            details=exit_details,
            duration=duration
        )

    def record_edge_process(self, from_node: str, to_node: str,
                            details: Dict[str, Any] = None) -> None:
        """Record an edge-processing event."""
        self.debug(
            f"Processing edge from {from_node} to {to_node}",
            node_id=from_node,
            event_type=EventType.EDGE_PROCESS,
            details={
                "to_node": to_node,
                **(details or {})
            }
        )

    def record_human_interaction(self, node_id: str, input_data: str = None, output: str = None,
                                 duration: float = None, details: Dict[str, Any] = None) -> None:
        """Record a human interaction."""
        call_details = {
            "input_data": input_data,
            "output": output,
            **(details or {})
        }

        self.info(
            f"Human interaction for node {node_id}",
            node_id=node_id,
            event_type=EventType.HUMAN_INTERACTION,
            details=call_details,
            duration=duration
        )

    def record_model_call(self, node_id: str, model_name: str,
                          input_data: str = None, output: str = None,
                          duration: float = None, details: Dict[str, Any] = None,
                          stage: CallStage | str | None = None) -> None:
        """Record a model invocation."""
        stage_value = stage.value if isinstance(stage, CallStage) else stage
        call_details = {
            "model_name": model_name,
            "input_data": input_data,
            "output": output,
            **(details or {})
        }
        if stage_value:
            call_details["stage"] = stage_value

        self.info(
            f"Model call for node {node_id}",
            node_id=node_id,
            event_type=EventType.MODEL_CALL,
            details=call_details,
            duration=duration
        )

    def record_tool_call(self, node_id: str, tool_name: str, tool_result: str,
                         duration: float = None, success: bool | None = True,
                         details: Dict[str, Any] = None,
                         stage: CallStage | str | None = None) -> None:
        """Record a tool invocation."""
        stage_value = stage.value if isinstance(stage, CallStage) else stage
        tool_details = {
            "tool_result": tool_result,
            "tool_name": tool_name,
            "success": success,
            **(details or {})
        }
        if stage_value:
            tool_details["stage"] = stage_value

        level = LogLevel.INFO if success is not False else LogLevel.ERROR
        self.add_log(
            level,
            f"Tool call {tool_name} for node {node_id}",
            node_id=node_id,
            event_type=EventType.TOOL_CALL,
            details=tool_details,
            duration=duration
        )

    def record_thinking_process(self, node_id: str, thinking_mode: str, thinking_result: str, stage: str,
                                duration: float = None, details: Dict[str, Any] = None) -> None:
        """Record a thinking-stage entry."""
        thinking_details = {
            "thinking_result": thinking_result,
            "thinking_mode": thinking_mode,
            "stage": stage,
            **(details or {})
        }

        self.info(
            f"Thinking process for node {node_id} ({thinking_mode} at {stage})",
            node_id=node_id,
            event_type=EventType.THINKING_PROCESS,
            details=thinking_details,
            duration=duration
        )

    def record_memory_operation(self, node_id: str, retrieved_memory: str, operation_type: str, stage: str,
                                duration: float = None, details: Dict[str, Any] = None) -> None:
        """Record a memory operation (retrieve/update)."""
        memory_details = {
            "retrieved_memory": retrieved_memory,
            "operation_type": operation_type,  # RETRIEVE or UPDATE
            "stage": stage,
            **(details or {})
        }

        self.info(
            f"Memory {operation_type} operation for node {node_id} at {stage}",
            node_id=node_id,
            event_type=EventType.MEMORY_OPERATION,
            details=memory_details,
            duration=duration
        )

    def record_workflow_start(self, workflow_config: Dict[str, Any] = None) -> None:
        """Record the workflow start event."""
        self.info(
            "Workflow execution started",
            event_type=EventType.WORKFLOW_START,
            details={
                "workflow_id": self.workflow_id,
                "node_count": workflow_config.get("node_count") if workflow_config else None,
                "edge_count": workflow_config.get("edge_count") if workflow_config else None,
            }
        )

    def record_workflow_end(self, success: bool = True,
                            duration: float = None, details: Dict[str, Any] = None) -> None:
        """Record the workflow end event."""
        end_details = {
            "success": success,
            "total_logs": len(self.logs),
            **(details or {})
        }

        level = LogLevel.INFO if success else LogLevel.ERROR
        self.add_log(
            level,
            "Workflow execution completed",
            event_type=EventType.WORKFLOW_END,
            details=end_details,
            duration=duration
        )

    def get_logs(self) -> List[Dict[str, Any]]:
        """Return all log entries as dictionaries."""
        return [log.to_dict() for log in self.logs]

    def get_logs_by_level(self, level: str) -> List[Dict[str, Any]]:
        """Return logs filtered by level."""
        return [log.to_dict() for log in self.logs if log.level == level]

    def get_logs_by_node(self, node_id: str) -> List[Dict[str, Any]]:
        """Return logs filtered by node id."""
        return [log.to_dict() for log in self.logs if log.node_id == node_id]

    def get_execution_summary(self) -> Dict[str, Any]:
        """Return an execution summary."""
        total_duration = (datetime.now() - self.start_time).total_seconds() * 1000

        node_durations = {}
        for log in self.logs:
            if log.node_id and log.duration:
                if log.node_id not in node_durations:
                    node_durations[log.node_id] = 0
                node_durations[log.node_id] += log.duration

        error_count = len([log for log in self.logs if log.level in ["ERROR", "CRITICAL"]])
        warning_count = len([log for log in self.logs if log.level == "WARNING"])

        return {
            "workflow_id": self.workflow_id,
            "start_time": self.start_time.isoformat(),
            "total_duration": total_duration,
            "total_logs": len(self.logs),
            "error_count": error_count,
            "warning_count": warning_count,
            "node_durations": node_durations,
            "execution_path": self.current_path
        }

    def to_dict(self) -> Dict[str, Any]:
        log_data = {
            "workflow_id": self.workflow_id,
            "start_time": self.start_time.isoformat(),
            "logs": self.get_logs(),
            "summary": self.get_execution_summary()
        }
        return log_data

    def to_json(self) -> str:
        """Serialize all logs to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def save_to_file(self, filepath: str) -> None:
        """Persist logs to a file on disk."""
        # with open(filepath, 'w', encoding='utf-8') as f:
        #     f.write(self.to_json())
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)  # Create any missing parent directories
        path.write_text(self.to_json(), encoding='utf-8')
    
    # ================================================================
    # Timer Context Managers (integrated from LogManager)
    # ================================================================
    
    def __init_timers__(self):
        """Initialize timer storage if not exists."""
        if not hasattr(self, '_timers'):
            self._timers: Dict[str, float] = {}
    
    @contextmanager
    def node_timer(self, node_id: str):
        """Context manager that times node execution."""
        self.__init_timers__()
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = (end_time - start_time)
            self._timers[node_id] = duration
    
    @contextmanager
    def model_timer(self, node_id: str):
        """Context manager that times model invocations."""
        self.__init_timers__()
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = (end_time - start_time)
            self._timers[f"model_{node_id}"] = duration
    
    @contextmanager
    def agent_timer(self, node_id: str):
        """Context manager that times agent invocations."""
        self.__init_timers__()
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = (end_time - start_time)
            self._timers[f"agent_{node_id}"] = duration
    
    @contextmanager
    def human_timer(self, node_id: str):
        """Context manager that times human interactions."""
        self.__init_timers__()
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = (end_time - start_time)
            self._timers[f"human_{node_id}"] = duration
    
    @contextmanager
    def tool_timer(self, node_id: str, tool_name: str):
        """Context manager that times tool invocations."""
        self.__init_timers__()
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = (end_time - start_time)
            self._timers[f"tool_{node_id}_{tool_name}"] = duration
    
    @contextmanager
    def thinking_timer(self, node_id: str, stage: str):
        """Context manager that times thinking stages."""
        self.__init_timers__()
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = (end_time - start_time)
            self._timers[f"thinking_{node_id}_{stage}"] = duration
    
    @contextmanager
    def memory_timer(self, node_id: str, operation_type: str, stage: str):
        """Context manager that times memory operations."""
        self.__init_timers__()
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = (end_time - start_time)
            self._timers[f"memory_{node_id}_{operation_type}_{stage}"] = duration
    
    def get_timer(self, timer_key: str) -> Optional[float]:
        """Return the elapsed time recorded by the timer key."""
        self.__init_timers__()
        return self._timers.get(timer_key)
