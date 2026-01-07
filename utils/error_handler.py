"""Error handling utilities for the DevAll workflow system."""

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import traceback

from utils.structured_logger import get_server_logger
from utils.exceptions import MACException, ValidationError, SecurityError, ConfigurationError, \
    WorkflowExecutionError, ResourceNotFoundError, ResourceConflictError, TimeoutError, ExternalServiceError


# Error code mapping to HTTP status codes
ERROR_CODE_TO_STATUS = {
    "VALIDATION_ERROR": 400,
    "SECURITY_ERROR": 403,
    "CONFIGURATION_ERROR": 500,
    "WORKFLOW_EXECUTION_ERROR": 500,
    "RESOURCE_NOT_FOUND": 404,
    "RESOURCE_CONFLICT": 409,
    "TIMEOUT_ERROR": 408,
    "EXTERNAL_SERVICE_ERROR": 502,
    "GENERIC_ERROR": 500
}


async def handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle validation errors."""
    return await handle_mac_exception(request, exc)


async def handle_security_error(request: Request, exc: SecurityError) -> JSONResponse:
    """Handle security errors."""
    return await handle_mac_exception(request, exc)


async def handle_configuration_error(request: Request, exc: ConfigurationError) -> JSONResponse:
    """Handle configuration errors."""
    return await handle_mac_exception(request, exc)


async def handle_workflow_execution_error(request: Request, exc: WorkflowExecutionError) -> JSONResponse:
    """Handle workflow execution errors."""
    return await handle_mac_exception(request, exc)


async def handle_resource_not_found_error(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    """Handle resource not found errors."""
    return await handle_mac_exception(request, exc)


async def handle_resource_conflict_error(request: Request, exc: ResourceConflictError) -> JSONResponse:
    """Handle resource conflict errors."""
    return await handle_mac_exception(request, exc)


async def handle_timeout_error(request: Request, exc: TimeoutError) -> JSONResponse:
    """Handle timeout errors."""
    return await handle_mac_exception(request, exc)


async def handle_external_service_error(request: Request, exc: ExternalServiceError) -> JSONResponse:
    """Handle external service errors."""
    return await handle_mac_exception(request, exc)


async def handle_mac_exception(request: Request, exc: MACException) -> JSONResponse:
    """Handle DevAll exceptions and return standardized error response."""
    logger = get_server_logger()
    
    # Log the error
    logger.log_exception(
        exc,
        f"DevAll exception occurred: {exc.error_code} - {exc.message}",
        correlation_id=getattr(request.state, 'correlation_id', None),
        url=str(request.url),
        method=request.method
    )
    
    # Determine the HTTP status code
    status_code = ERROR_CODE_TO_STATUS.get(exc.error_code, 500)
    
    # Prepare response data
    response_data = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        },
        "timestamp": exc.__dict__.get('_timestamp', __import__('datetime').datetime.utcnow().isoformat())
    }
    
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(response_data)
    )


async def handle_general_exception(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions and return standardized error response."""
    logger = get_server_logger()
    
    # Log the error with traceback
    logger.log_exception(
        exc,
        f"General exception occurred: {type(exc).__name__} - {str(exc)}",
        correlation_id=getattr(request.state, 'correlation_id', None),
        url=str(request.url),
        method=request.method
    )
    
    # For security, don't expose internal error details to the client
    error_details = {
        "code": "INTERNAL_ERROR",
        "message": "An internal server error occurred",
        "details": {}  # Don't send internal details to client
    }
    
    # In development, we might want to include more details
    import os
    if os.getenv("ENVIRONMENT") == "development":
        error_details["details"]["debug_info"] = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc()
        }
    
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder({"error": error_details})
    )


def add_exception_handlers(app):
    """Add exception handlers to FastAPI app."""
    app.add_exception_handler(ValidationError, handle_validation_error)
    app.add_exception_handler(SecurityError, handle_security_error)
    app.add_exception_handler(ConfigurationError, handle_configuration_error)
    app.add_exception_handler(WorkflowExecutionError, handle_workflow_execution_error)
    app.add_exception_handler(ResourceNotFoundError, handle_resource_not_found_error)
    app.add_exception_handler(ResourceConflictError, handle_resource_conflict_error)
    app.add_exception_handler(TimeoutError, handle_timeout_error)
    app.add_exception_handler(ExternalServiceError, handle_external_service_error)
    app.add_exception_handler(MACException, handle_mac_exception)
    app.add_exception_handler(Exception, handle_general_exception)
    
    return app