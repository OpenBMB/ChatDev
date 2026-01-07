"""Log manager compatibility shim.

LogManager now wraps WorkflowLogger for backward compatibility.
All timing helpers live inside WorkflowLogger; prefer using it directly.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, List

from entity.enums import CallStage, LogLevel
from utils.logger import WorkflowLogger


class LogManager:
    """Backward-compatible wrapper that delegates to ``WorkflowLogger``."""

    def __init__(self, logger: WorkflowLogger = None):
        self.logger = logger

    def get_logger(self) -> WorkflowLogger:
        """Return the underlying ``WorkflowLogger`` instance."""
        return self.logger

    # ================================================================
    # Timer context managers delegated to WorkflowLogger
    # ================================================================

    @contextmanager
    def node_timer(self, node_id: str):
        """Context manager that times node execution."""
        with self.logger.node_timer(node_id):
            yield

    @contextmanager
    def model_timer(self, node_id: str):
        """Context manager that times model invocations."""
        with self.logger.model_timer(node_id):
            yield

    @contextmanager
    def agent_timer(self, node_id: str):
        """Context manager that times agent invocations."""
        with self.logger.agent_timer(node_id):
            yield

    @contextmanager
    def human_timer(self, node_id: str):
        """Context manager that times human interactions."""
        with self.logger.human_timer(node_id):
            yield

    @contextmanager
    def tool_timer(self, node_id: str, tool_name: str):
        """Context manager that times tool invocations."""
        with self.logger.tool_timer(node_id, tool_name):
            yield

    @contextmanager
    def thinking_timer(self, node_id: str, stage: str):
        """Context manager that times thinking workflows."""
        with self.logger.thinking_timer(node_id, stage):
            yield

    @contextmanager
    def memory_timer(self, node_id: str, operation_type: str, stage: str):
        """Context manager that times memory operations."""
        with self.logger.memory_timer(node_id, operation_type, stage):
            yield

    @contextmanager
    def operation_timer(self, operation_name: str):
        """Context manager that times custom operations."""
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = (end_time - start_time)
            self.logger._timers[operation_name] = duration

    # ================================================================
    # Logging methods delegated to WorkflowLogger
    # ================================================================

    def record_node_start(self, node_id: str, inputs: List[Dict[str, str]], node_type: str = None,
                          details: Dict[str, Any] = None) -> None:
        """Record the start of a node."""
        self.logger.enter_node(node_id, inputs, node_type, details)

    def record_node_end(self, node_id: str, output: str = None,
                        details: Dict[str, Any] = None) -> None:
        """Record the end of a node."""
        output_size = len(str(output)) if output is not None else 0
        duration = self.logger.get_timer(node_id)
        self.logger.exit_node(node_id, output, duration, output_size, details)

    def record_edge_process(self, from_node: str, to_node: str,
                            details: Dict[str, Any] = None) -> None:
        """Record an edge processing event."""
        self.logger.record_edge_process(from_node, to_node, details)

    def record_human_interaction(self, node_id: str, input_data: Any = None, output: Any = None,
                                 details: Dict[str, Any] = None) -> None:
        """Record a human interaction."""
        input_size = len(str(input_data)) if input_data is not None else 0
        output_size = len(str(output)) if output is not None else 0
        duration = self.logger.get_timer(f"human_{node_id}")
        call_details = {
            "input_size": input_size,
            "output_size": output_size,
            **(details or {})
        }
        self.logger.record_human_interaction(
            node_id, input_data, output, duration, call_details
        )

    def record_model_call(self, node_id: str, model_name: str,
                          input_data: Any = None, output: Any = None,
                          details: Dict[str, Any] = None,
                          stage: CallStage = CallStage.AFTER) -> None:
        """Record a model invocation."""
        input_size = len(str(input_data)) if input_data is not None else 0
        output_size = len(str(output)) if output is not None else 0
        duration = self.logger.get_timer(f"model_{node_id}")

        call_details = {
            "input_size": input_size,
            "output_size": output_size,
            **(details or {})
        }

        self.logger.record_model_call(
            node_id, model_name, input_data, output, duration, call_details, stage
        )

    def record_tool_call(self, node_id: str, tool_name: str,
                         success: bool | None = True, tool_result: Any = None,
                         details: Dict[str, Any] = None,
                         stage: CallStage = CallStage.AFTER) -> None:
        """Record a tool invocation."""
        duration = self.logger.get_timer(f"tool_{node_id}_{tool_name}")
        tool_details = {
            "result_size": len(str(tool_result)) if tool_result is not None else 0,
            **(details or {})
        }
        self.logger.record_tool_call(node_id, tool_name, tool_result, duration, success, tool_details, stage)

    def record_thinking_process(self, node_id: str, thinking_mode: str, thinking_result: str,
                                stage: str, details: Dict[str, Any] = None) -> None:
        """Record a thinking stage."""
        duration = self.logger.get_timer(f"thinking_{node_id}_{stage}")
        self.logger.record_thinking_process(node_id, thinking_mode, thinking_result, stage, duration, details)

    def record_memory_operation(self, node_id: str, operation_type: str,
                                stage: str, retrieved_memory: Any = None,
                                details: Dict[str, Any] = None) -> None:
        """Record a memory operation."""
        duration = self.logger.get_timer(f"memory_{node_id}_{operation_type}_{stage}")
        memory_details = {
            "result_size": len(str(retrieved_memory)) if retrieved_memory is not None else 0,
            **(details or {})
        }
        self.logger.record_memory_operation(node_id, retrieved_memory, operation_type, stage, duration, memory_details)

    def record_workflow_start(self, workflow_config: Dict[str, Any] = None) -> None:
        """Record the workflow start event."""
        self.logger.record_workflow_start(workflow_config)

    def record_workflow_end(self, success: bool = True,
                            details: Dict[str, Any] = None) -> None:
        """Record the workflow end event."""
        workflow_duration = (time.time() - self.logger.start_time.timestamp())
        self.logger.record_workflow_end(success, workflow_duration, details)

    def debug(self, message: str, node_id: str = None,
              details: Dict[str, Any] = None) -> None:
        """Record debug information."""
        self.logger.debug(message, node_id, details=details)

    def info(self, message: str, node_id: str = None,
             details: Dict[str, Any] = None) -> None:
        """Record general information."""
        self.logger.info(message, node_id, details=details)

    def warning(self, message: str, node_id: str = None,
                details: Dict[str, Any] = None) -> None:
        """Record warning information."""
        self.logger.warning(message, node_id, details=details)

    def error(self, message: str, node_id: str = None,
              details: Dict[str, Any] = None) -> None:
        """Record error information."""
        self.logger.error(message, node_id, details=details)

    def critical(self, message: str, node_id: str = None,
                 details: Dict[str, Any] = None) -> None:
        """Record critical error information."""
        self.logger.critical(message, node_id, details=details)

    def get_execution_summary(self) -> Dict[str, Any]:
        """Return the execution summary."""
        return self.logger.get_execution_summary()

    def get_all_logs(self) -> list:
        """Return all logs."""
        return self.logger.get_logs()

    def logs_to_dict(self) -> Dict[str, Any]:
        """Convert the logs to dictionary form."""
        return self.logger.to_dict()

    def save_logs(self, filepath: str) -> None:
        """Persist logs to a file."""
        self.logger.save_to_file(filepath)
