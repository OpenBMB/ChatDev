"""Structured logging utilities for the DevAll workflow system."""

import json
import logging
import sys
import traceback
import datetime
from enum import Enum
from pathlib import Path
import os

from entity.enums import LogLevel
from utils.exceptions import MACException


class LogType(str, Enum):
    """Types of structured logs."""
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    WORKFLOW = "workflow"
    SECURITY = "security"
    PERFORMANCE = "performance"


class StructuredLogger:
    """A structured logger that outputs JSON format logs with consistent fields."""
    
    def __init__(self, name: str, log_level: LogLevel = LogLevel.INFO, log_file: str = None):
        self.name = name
        self.log_level = log_level
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self._get_logging_level(log_level))
        
        # Create formatter
        formatter = logging.Formatter('%(message)s')
        
        # Create handler
        if log_file:
            # Ensure log directory exists
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(log_file)
        else:
            handler = logging.StreamHandler(sys.stdout)
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # For correlation IDs
        self.correlation_id = None
    
    def _get_logging_level(self, log_level: LogLevel) -> int:
        """Convert LogLevel enum to logging module level."""
        level_map = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL
        }
        return level_map.get(log_level, logging.INFO)
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if a log level should be logged based on configured level."""
        return level >= self.log_level
    
    def _format_log(self, log_type: LogType, level: LogLevel, message: str, 
                    correlation_id: str = None, **kwargs) -> str:
        """Format log entry as JSON string."""
        log_entry = {
            "timestamp": datetime.datetime.now(datetime.UTC),
            "log_type": log_type.value,
            "level": level.value,
            "logger": self.name,
            "message": message,
            "correlation_id": correlation_id or self.correlation_id,
            **kwargs
        }
        return json.dumps(log_entry, default=str)
    
    def _log(self, log_type: LogType, level: LogLevel, message: str, 
             correlation_id: str = None, **kwargs):
        """Internal logging method."""
        if self._should_log(level):
            formatted_log = self._format_log(log_type, level, message, correlation_id, **kwargs)
            log_level = self._get_logging_level(level)
            self.logger.log(log_level, formatted_log)
    
    def info(self, message: str, correlation_id: str = None, log_type: LogType = LogType.WORKFLOW, **kwargs):
        """Log information."""
        self._log(log_type, LogLevel.INFO, message, correlation_id, **kwargs)
    
    def debug(self, message: str, correlation_id: str = None, log_type: LogType = LogType.WORKFLOW, **kwargs):
        """Log debug information."""
        self._log(log_type, LogLevel.DEBUG, message, correlation_id, **kwargs)
    
    def warning(self, message: str, correlation_id: str = None, log_type: LogType = LogType.WORKFLOW, **kwargs):
        """Log warning."""
        self._log(log_type, LogLevel.WARNING, message, correlation_id, **kwargs)
    
    def error(self, message: str, correlation_id: str = None, log_type: LogType = LogType.ERROR, **kwargs):
        """Log error with details."""
        self._log(log_type, LogLevel.ERROR, message, correlation_id, **kwargs)
    
    def critical(self, message: str, correlation_id: str = None, log_type: LogType = LogType.ERROR, **kwargs):
        """Log critical error."""
        self._log(log_type, LogLevel.CRITICAL, message, correlation_id, **kwargs)
    
    def log_exception(self, exception: Exception, message: str = None, 
                      correlation_id: str = None, **kwargs) -> None:
        """Log an exception with its traceback."""
        if message is None:
            message = str(exception)
        
        # Include exception info
        exception_info = {
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "traceback": traceback.format_exc()
        }
        
        if isinstance(exception, MACException):
            exception_info["error_code"] = exception.error_code
            exception_info["exception_details"] = exception.details
        
        self._log(LogType.ERROR, LogLevel.ERROR, message, correlation_id, 
                 exception=exception_info, **kwargs)
    
    def log_request(self, method: str, url: str, correlation_id: str = None, **kwargs):
        """Log incoming request."""
        self._log(LogType.REQUEST, LogLevel.INFO, f"Incoming {method} request to {url}", 
                 correlation_id, method=method, url=url, **kwargs)
    
    def log_response(self, status_code: int, response_time: float, correlation_id: str = None, **kwargs):
        """Log outgoing response."""
        self._log(LogType.RESPONSE, LogLevel.INFO, 
                 f"Response with status {status_code} in {response_time:.3f}s", 
                 correlation_id, status_code=status_code, response_time=response_time, **kwargs)
    
    def log_security_event(self, event_type: str, message: str, correlation_id: str = None, **kwargs):
        """Log security-related events."""
        self._log(LogType.SECURITY, LogLevel.WARNING, message, correlation_id, 
                 event_type=event_type, **kwargs)
    
    def log_performance(self, operation: str, duration: float, correlation_id: str = None, **kwargs):
        """Log performance metrics."""
        self._log(LogType.PERFORMANCE, LogLevel.INFO, 
                 f"Operation {operation} completed in {duration:.3f}s", 
                 correlation_id, operation=operation, duration=duration, **kwargs)
    
    def log_workflow_event(self, workflow_id: str, event_type: str, message: str, 
                          correlation_id: str = None, **kwargs):
        """Log workflow-specific events."""
        self._log(LogType.WORKFLOW, LogLevel.INFO, message, correlation_id,
                 workflow_id=workflow_id, event_type=event_type, **kwargs)
    
    def set_correlation_id(self, correlation_id: str):
        """Set the correlation ID for this logger instance."""
        self.correlation_id = correlation_id


# Global logger instances
_server_logger = None
_workflow_logger = None


def get_server_logger() -> StructuredLogger:
    """Get the global server logger instance."""
    global _server_logger
    if _server_logger is None:
        log_file = os.getenv('SERVER_LOG_FILE', 'logs/server.log')
        log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_level = LogLevel[log_level_str]
        _server_logger = StructuredLogger('server', log_level, log_file)
    return _server_logger


def get_workflow_logger(name: str = 'workflow') -> StructuredLogger:
    """Get a workflow logger instance."""
    global _workflow_logger
    if _workflow_logger is None:
        log_file = os.getenv('WORKFLOW_LOG_FILE', f'logs/{name}.log')
        log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_level = LogLevel[log_level_str]
        _workflow_logger = StructuredLogger(name, log_level, log_file)
    return _workflow_logger