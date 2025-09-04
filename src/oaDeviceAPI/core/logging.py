"""
Structured logging system with request tracing for oaDeviceAPI.

This module provides structured logging with JSON output, request correlation IDs,
performance tracking, and integration with monitoring systems.
"""

import json
import logging
import logging.handlers
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .config_schema import AppConfig


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Converts log records to structured JSON format with consistent fields
    and proper handling of exceptions and extra data.
    """

    def __init__(
        self,
        *,
        service_name: str = "oaDeviceAPI",
        service_version: str = "1.0.0",
        include_extra: bool = True
    ):
        super().__init__()
        self.service_name = service_name
        self.service_version = service_version
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": {
                "name": self.service_name,
                "version": self.service_version
            }
        }

        # Add exception information
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info).split('\n')
            }

        # Add source location
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName
        }

        # Add process/thread info
        log_entry["process"] = {
            "pid": record.process,
            "thread_id": record.thread,
            "thread_name": record.threadName
        }

        # Add extra fields if enabled
        if self.include_extra and hasattr(record, '__dict__'):
            extra_fields = {}
            for key, value in record.__dict__.items():
                # Skip standard log record attributes
                if key not in [
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'message', 'exc_info',
                    'exc_text', 'stack_info', 'getMessage'
                ]:
                    # Handle non-serializable values
                    try:
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)

            if extra_fields:
                log_entry["extra"] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False)


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request correlation IDs and performance tracking.

    Adds unique request IDs, tracks request duration, and provides
    structured logging context for each request.
    """

    def __init__(self, app, logger_name: str = "oaDeviceAPI.requests"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with tracking and logging."""
        # Generate or extract request ID
        request_id = self._get_or_generate_request_id(request)

        # Add request ID to request state
        request.state.request_id = request_id

        # Log request start
        start_time = datetime.now(UTC)
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "event_type": "request_start"
            }
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate duration
            end_time = datetime.now(UTC)
            duration_ms = (end_time - start_time).total_seconds() * 1000

            # Log request completion
            self.logger.info(
                f"Request completed: {request.method} {request.url.path} - "
                f"{response.status_code} ({duration_ms:.2f}ms)",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "response_size": response.headers.get("content-length"),
                    "event_type": "request_complete"
                }
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            # Calculate duration
            end_time = datetime.now(UTC)
            duration_ms = (end_time - start_time).total_seconds() * 1000

            # Log request error
            self.logger.error(
                f"Request failed: {request.method} {request.url.path} - "
                f"Error: {str(exc)} ({duration_ms:.2f}ms)",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "event_type": "request_error"
                },
                exc_info=True
            )

            # Re-raise the exception
            raise

    def _get_or_generate_request_id(self, request: Request) -> str:
        """Get existing request ID or generate a new one."""
        # Check for existing request ID in headers
        request_id = request.headers.get("X-Request-ID")
        if request_id:
            return request_id

        # Check for trace ID (common in observability setups)
        trace_id = request.headers.get("X-Trace-ID")
        if trace_id:
            return trace_id

        # Generate new UUID-based request ID
        return str(uuid.uuid4())


class PerformanceLogger:
    """
    Logger for performance metrics and timing information.

    Provides decorators and context managers for tracking
    function execution times and performance metrics.
    """

    def __init__(self, logger_name: str = "oaDeviceAPI.performance"):
        self.logger = logging.getLogger(logger_name)

    def log_function_performance(
        self,
        function_name: str,
        duration_ms: float,
        context: dict[str, Any] | None = None
    ):
        """Log function performance metrics."""
        extra_data = {
            "function": function_name,
            "duration_ms": duration_ms,
            "event_type": "function_performance"
        }

        if context:
            extra_data["context"] = context

        # Determine log level based on duration
        if duration_ms > 5000:  # > 5 seconds
            log_level = logging.WARNING
            message = f"Slow function execution: {function_name} ({duration_ms:.2f}ms)"
        elif duration_ms > 1000:  # > 1 second
            log_level = logging.INFO
            message = f"Function execution: {function_name} ({duration_ms:.2f}ms)"
        else:
            log_level = logging.DEBUG
            message = f"Function execution: {function_name} ({duration_ms:.2f}ms)"

        self.logger.log(log_level, message, extra=extra_data)

    def performance_timer(self, function_name: str | None = None):
        """
        Decorator for timing function execution.

        Usage:
            @performance_logger.performance_timer()
            def my_function():
                pass
        """
        def decorator(func):
            import functools
            import time

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    duration_ms = (end_time - start_time) * 1000

                    name = function_name or func.__name__
                    self.log_function_performance(name, duration_ms)

            return wrapper
        return decorator


class LoggingManager:
    """
    Central logging configuration and management.

    Configures logging based on application settings,
    sets up formatters, handlers, and provides logging utilities.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.performance_logger = PerformanceLogger()

    def setup_logging(self) -> None:
        """Set up logging configuration based on app config."""
        # Get root logger
        root_logger = logging.getLogger()

        # Clear existing handlers
        root_logger.handlers.clear()

        # Set log level
        log_level = getattr(logging, self.config.logging.level.value)
        root_logger.setLevel(log_level)

        # Configure console handler
        self._setup_console_handler(root_logger)

        # Configure file handler if enabled
        if self.config.logging.log_to_file and self.config.logging.log_file_path:
            self._setup_file_handler(root_logger)

        # Set up third-party library log levels
        self._configure_third_party_loggers()

        # Log startup message
        app_logger = logging.getLogger("oaDeviceAPI")
        app_logger.info(
            f"Logging configured - Level: {self.config.logging.level.value}, "
            f"Structured: {self.config.logging.enable_structured_logging}",
            extra={
                "event_type": "logging_configured",
                "log_level": self.config.logging.level.value,
                "structured_logging": self.config.logging.enable_structured_logging,
                "file_logging": self.config.logging.log_to_file
            }
        )

    def _setup_console_handler(self, logger: logging.Logger) -> None:
        """Set up console logging handler."""
        console_handler = logging.StreamHandler(sys.stdout)

        if self.config.logging.enable_structured_logging:
            formatter = JSONFormatter(
                service_name=self.config.app_name,
                service_version=self.config.app_version
            )
        else:
            formatter = logging.Formatter(self.config.logging.format)

        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    def _setup_file_handler(self, logger: logging.Logger) -> None:
        """Set up file logging handler with rotation."""
        try:
            # Ensure log directory exists
            log_file = self.config.logging.log_file_path
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Create rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=self.config.logging.max_file_size_mb * 1024 * 1024,
                backupCount=self.config.logging.backup_count
            )

            # Always use JSON format for file logs
            formatter = JSONFormatter(
                service_name=self.config.app_name,
                service_version=self.config.app_version
            )
            file_handler.setFormatter(formatter)

            logger.addHandler(file_handler)

        except Exception as exc:
            # Log error but don't fail startup
            console_logger = logging.getLogger("oaDeviceAPI.logging")
            console_logger.error(
                f"Failed to set up file logging: {exc}",
                extra={"event_type": "logging_setup_error"}
            )

    def _configure_third_party_loggers(self) -> None:
        """Configure log levels for third-party libraries."""
        # Reduce noise from third-party libraries
        third_party_levels = {
            "uvicorn": logging.WARNING,
            "uvicorn.error": logging.INFO,
            "uvicorn.access": logging.WARNING,
            "fastapi": logging.WARNING,
            "httpx": logging.WARNING,
            "urllib3": logging.WARNING,
        }

        for logger_name, level in third_party_levels.items():
            logging.getLogger(logger_name).setLevel(level)


def get_request_id() -> str | None:
    """
    Get the current request ID from context.

    This function attempts to extract the request ID from the current
    context, useful for logging within request handlers.
    """
    try:
        # Try to get from asyncio context (requires contextvars)
        from contextvars import ContextVar
        request_id_var: ContextVar[str | None] = ContextVar('request_id', default=None)
        return request_id_var.get()
    except ImportError:
        # Fallback - return None if contextvars not available
        return None


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    request_id: str | None = None,
    **extra_context
) -> None:
    """
    Log with additional context information.

    Args:
        logger: Logger instance to use
        level: Log level (logging.INFO, etc.)
        message: Log message
        request_id: Optional request ID
        **extra_context: Additional context fields
    """
    extra_data = extra_context.copy()

    # Add request ID if provided or available
    if request_id:
        extra_data["request_id"] = request_id
    elif "request_id" not in extra_data:
        current_request_id = get_request_id()
        if current_request_id:
            extra_data["request_id"] = current_request_id

    logger.log(level, message, extra=extra_data)


# Global logging manager instance
_logging_manager: LoggingManager | None = None


def setup_logging(config: AppConfig) -> LoggingManager:
    """Set up global logging configuration."""
    global _logging_manager
    _logging_manager = LoggingManager(config)
    _logging_manager.setup_logging()
    return _logging_manager


def get_performance_logger() -> PerformanceLogger:
    """Get the global performance logger instance."""
    if _logging_manager:
        return _logging_manager.performance_logger
    return PerformanceLogger()
