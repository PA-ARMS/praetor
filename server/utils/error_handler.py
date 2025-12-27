"""
Centralized Error Handling
Provides user-friendly error messages and proper error logging
"""
import traceback
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from server.utils.logger import setup_logger

logger = setup_logger("error_handler")


class AppError(Exception):
    """Base application error with user-friendly message"""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppError):
    """Validation error (400)"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status_code=400, details=details)


class AuthenticationError(AppError):
    """Authentication error (401)"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


class AuthorizationError(AppError):
    """Authorization error (403)"""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)


class NotFoundError(AppError):
    """Resource not found error (404)"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ServiceUnavailableError(AppError):
    """Service unavailable error (503)"""
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, status_code=503)


def handle_exception(exc: Exception, include_details: bool = False) -> JSONResponse:
    """
    Handle exceptions and return user-friendly error responses
    
    Args:
        exc: The exception that occurred
        include_details: Whether to include error details (for debugging)
    
    Returns:
        JSONResponse with error information
    """
    # Log the full error
    logger.error(f"Exception occurred: {exc}", exc_info=True)
    
    # Handle known application errors
    if isinstance(exc, AppError):
        status_code = exc.status_code
        message = exc.message
        details = exc.details if include_details else {}
    # Handle HTTP exceptions
    elif isinstance(exc, HTTPException):
        status_code = exc.status_code
        message = exc.detail
        details = {}
    # Handle Ollama connection errors
    elif "Ollama" in str(type(exc)) or "ollama" in str(exc).lower():
        status_code = 503
        message = "AI service is temporarily unavailable. Please try again in a moment."
        details = {"service": "ollama"} if include_details else {}
    # Handle database errors
    elif "database" in str(exc).lower() or "sql" in str(exc).lower():
        status_code = 503
        message = "Database error occurred. Please try again or contact support."
        details = {}  # Never expose database details
    # Handle generic errors
    else:
        status_code = 500
        message = "An unexpected error occurred. Please try again or contact support."
        details = {"error_type": type(exc).__name__} if include_details else {}
    
    # Build response
    response_data = {
        "error": True,
        "message": message,
        "status_code": status_code
    }
    
    if include_details and details:
        response_data["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def create_error_response(
    message: str,
    status_code: int = 500,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create a standardized error response
    
    Args:
        message: User-friendly error message
        status_code: HTTP status code
        details: Optional error details (only included in debug mode)
    
    Returns:
        JSONResponse with error information
    """
    logger.warning(f"Error response: {message} (status={status_code})")
    
    response_data = {
        "error": True,
        "message": message,
        "status_code": status_code
    }
    
    # Only include details in debug mode
    from server.config import settings
    if settings.DEBUG and details:
        response_data["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def log_error(error: Exception, context: Optional[Dict] = None):
    """
    Log error with context
    
    Args:
        error: The exception
        context: Additional context (user_id, endpoint, etc.)
    """
    error_info = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc()
    }
    
    if context:
        error_info["context"] = context
    
    logger.error(f"Error occurred: {error_info}")


# User-friendly error messages
ERROR_MESSAGES = {
    "ollama_unavailable": "AI service is temporarily unavailable. Please try again in a moment.",
    "database_error": "Database error occurred. Please try again or contact support.",
    "validation_error": "Invalid input. Please check your request and try again.",
    "authentication_required": "Please log in to access this resource.",
    "insufficient_permissions": "You don't have permission to perform this action.",
    "resource_not_found": "The requested resource was not found.",
    "rate_limit_exceeded": "Too many requests. Please wait a moment and try again.",
    "timeout": "The request took too long to process. Please try again with a simpler query.",
}

