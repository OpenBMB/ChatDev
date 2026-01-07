"""Custom exceptions for the DevAll workflow system."""

from typing import Optional, Dict, Any
import json


class MACException(Exception):
    """Base exception for DevAll workflow system."""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "GENERIC_ERROR"
        self.details = details or {}
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format for JSON response."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }
    
    def to_json(self) -> str:
        """Convert exception to JSON string."""
        return json.dumps(self.to_dict())


class ValidationError(MACException):
    """Raised when validation fails."""
    
    def __init__(self, message: str, field: str = None, details: Dict[str, Any] = None):
        super().__init__(message, "VALIDATION_ERROR", details or {})
        if field:
            self.details["field"] = field


class SecurityError(MACException):
    """Raised when a security violation occurs."""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, "SECURITY_ERROR", details or {})


class ConfigurationError(MACException):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_key: str = None, details: Dict[str, Any] = None):
        super().__init__(message, "CONFIGURATION_ERROR", details or {})
        if config_key:
            self.details["config_key"] = config_key


class WorkflowExecutionError(MACException):
    """Raised when workflow execution fails."""
    
    def __init__(self, message: str, workflow_id: str = None, node_id: str = None, details: Dict[str, Any] = None):
        super().__init__(message, "WORKFLOW_EXECUTION_ERROR", details or {})
        if workflow_id:
            self.details["workflow_id"] = workflow_id
        if node_id:
            self.details["node_id"] = node_id


class WorkflowCancelledError(MACException):
    """Raised when a workflow execution is cancelled mid-flight."""

    def __init__(self, message: str, workflow_id: str = None, details: Dict[str, Any] = None):
        super().__init__(message, "WORKFLOW_CANCELLED", details or {})
        if workflow_id:
            self.details["workflow_id"] = workflow_id


class ResourceNotFoundError(MACException):
    """Raised when a requested resource is not found."""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None, details: Dict[str, Any] = None):
        super().__init__(message, "RESOURCE_NOT_FOUND", details or {})
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id:
            self.details["resource_id"] = resource_id


class ResourceConflictError(MACException):
    """Raised when there's a conflict with an existing resource."""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None, details: Dict[str, Any] = None):
        super().__init__(message, "RESOURCE_CONFLICT", details or {})
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id:
            self.details["resource_id"] = resource_id


class TimeoutError(MACException):
    """Raised when an operation times out."""
    
    def __init__(self, message: str, operation: str = None, timeout_duration: float = None, details: Dict[str, Any] = None):
        super().__init__(message, "TIMEOUT_ERROR", details or {})
        if operation:
            self.details["operation"] = operation
        if timeout_duration is not None:
            self.details["timeout_duration"] = timeout_duration


class ExternalServiceError(MACException):
    """Raised when an external service call fails."""
    
    def __init__(self, message: str, service_name: str = None, status_code: int = None, details: Dict[str, Any] = None):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details or {})
        if service_name:
            self.details["service_name"] = service_name
        if status_code is not None:
            self.details["status_code"] = status_code
