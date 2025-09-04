"""
Unified error handling middleware and utilities for oaDeviceAPI.

This module provides centralized error handling, logging, and response
formatting to ensure consistent error responses across all endpoints.
"""

import logging
import traceback
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .exceptions import (
    BaseDeviceAPIException,
    ErrorSeverity,
    SystemError,
    convert_exception,
)

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware that catches and formats all exceptions.

    Provides structured error responses with proper HTTP status codes,
    logging, and monitoring integration.
    """

    def __init__(self, app, include_traceback: bool = False):
        super().__init__(app)
        self.include_traceback = include_traceback

    async def dispatch(self, request: Request, call_next):
        """Handle all requests and catch any exceptions."""
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            # Let FastAPI handle its own exceptions
            raise
        except BaseDeviceAPIException as exc:
            # Handle our unified exceptions
            return await self._handle_device_api_exception(request, exc)
        except Exception as exc:
            # Handle all other exceptions
            return await self._handle_generic_exception(request, exc)

    async def _handle_device_api_exception(
        self,
        request: Request,
        exc: BaseDeviceAPIException
    ) -> JSONResponse:
        """Handle BaseDeviceAPIException with structured response."""
        # Log the error with appropriate level
        log_level = self._get_log_level(exc.severity)
        logger.log(
            log_level,
            f"API Error [{exc.error_code}]: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "category": exc.category.value,
                "severity": exc.severity.value,
                "endpoint": str(request.url),
                "method": request.method,
                "details": exc.details
            }
        )

        # Determine HTTP status code
        status_code = self._get_http_status_code(exc)

        # Create response data
        response_data = exc.to_dict()
        response_data.update({
            "status": "error",
            "timestamp_epoch": int(exc.timestamp.timestamp()),
            "request_id": getattr(request.state, 'request_id', None)
        })

        # Add traceback in development
        if self.include_traceback:
            response_data["traceback"] = traceback.format_exc().split('\n')

        return JSONResponse(
            status_code=status_code,
            content=response_data
        )

    async def _handle_generic_exception(
        self,
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Handle generic exceptions by converting them."""
        # Convert to our exception format
        device_exc = convert_exception(
            exc,
            default_message="An unexpected error occurred",
            severity=ErrorSeverity.HIGH,
            details={
                "endpoint": str(request.url),
                "method": request.method
            }
        )

        # Log as critical since it's unhandled
        logger.critical(
            f"Unhandled exception [{device_exc.error_code}]: {device_exc.message}",
            extra={
                "error_code": device_exc.error_code,
                "endpoint": str(request.url),
                "method": request.method,
                "traceback": traceback.format_exc()
            }
        )

        return await self._handle_device_api_exception(request, device_exc)

    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """Map error severity to logging level."""
        severity_mapping = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        return severity_mapping.get(severity, logging.ERROR)

    def _get_http_status_code(self, exc: BaseDeviceAPIException) -> int:
        """Map exception category to HTTP status code."""
        from .exceptions import (
            ConfigurationError,
            ExternalServiceError,
            NetworkError,
            PermissionError,
            ValidationError,
        )

        # Map exception types to status codes
        if isinstance(exc, ValidationError):
            return 400  # Bad Request
        elif isinstance(exc, PermissionError):
            return 403  # Forbidden
        elif isinstance(exc, ConfigurationError):
            return 500  # Internal Server Error (configuration issues)
        elif isinstance(exc, NetworkError | ExternalServiceError):
            return 503  # Service Unavailable
        elif exc.severity == ErrorSeverity.CRITICAL:
            return 500  # Internal Server Error
        else:
            return 500  # Default to Internal Server Error


class ErrorHandler:
    """
    Utility class for handling errors in sync/async contexts.

    Provides decorators and context managers for consistent
    error handling across the application.
    """

    @staticmethod
    def handle_errors(
        default_return: Any = None,
        log_errors: bool = True,
        convert_exceptions: bool = True
    ):
        """
        Decorator to handle errors in functions.

        Args:
            default_return: Value to return on error
            log_errors: Whether to log errors
            convert_exceptions: Whether to convert exceptions to our format
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except BaseDeviceAPIException:
                    # Re-raise our exceptions as-is
                    raise
                except Exception as exc:
                    if log_errors:
                        logger.error(f"Error in {func.__name__}: {exc}", exc_info=True)

                    if convert_exceptions:
                        raise convert_exception(exc)
                    elif default_return is not None:
                        return default_return
                    else:
                        raise
            return wrapper
        return decorator

    @staticmethod
    def handle_errors_async(
        default_return: Any = None,
        log_errors: bool = True,
        convert_exceptions: bool = True
    ):
        """Async version of the error handling decorator."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except BaseDeviceAPIException:
                    # Re-raise our exceptions as-is
                    raise
                except Exception as exc:
                    if log_errors:
                        logger.error(f"Error in {func.__name__}: {exc}", exc_info=True)

                    if convert_exceptions:
                        raise convert_exception(exc)
                    elif default_return is not None:
                        return default_return
                    else:
                        raise
            return wrapper
        return decorator


def create_error_response(
    error: str | BaseDeviceAPIException,
    status_code: int = 500,
    request_id: str | None = None
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        error: Error message or exception
        status_code: HTTP status code
        request_id: Optional request ID for tracing

    Returns:
        JSONResponse with error details
    """
    if isinstance(error, str):
        # Create exception from string
        exc = SystemError(error)
    elif isinstance(error, BaseDeviceAPIException):
        exc = error
    else:
        # Convert generic exception
        exc = convert_exception(error)

    response_data = exc.to_dict()
    response_data.update({
        "status": "error",
        "timestamp_epoch": int(exc.timestamp.timestamp()),
        "request_id": request_id
    })

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def log_error_context(
    exc: BaseDeviceAPIException,
    context: dict[str, Any] | None = None
) -> None:
    """
    Log error with additional context information.

    Args:
        exc: The exception to log
        context: Additional context information
    """
    log_data = {
        "error_code": exc.error_code,
        "category": exc.category.value,
        "severity": exc.severity.value,
        "details": exc.details
    }

    if context:
        log_data["context"] = context

    log_level = {
        ErrorSeverity.LOW: logging.INFO,
        ErrorSeverity.MEDIUM: logging.WARNING,
        ErrorSeverity.HIGH: logging.ERROR,
        ErrorSeverity.CRITICAL: logging.CRITICAL
    }.get(exc.severity, logging.ERROR)

    logger.log(
        log_level,
        f"Error [{exc.error_code}]: {exc.message}",
        extra=log_data
    )
