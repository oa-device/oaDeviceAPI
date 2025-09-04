"""
Unified exception classes for oaDeviceAPI.

This module provides standardized exceptions with proper typing,
structured error information, and consistent error handling across platforms.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    """Categories for error classification."""
    SYSTEM = "system"
    SERVICE = "service"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    PERMISSION = "permission"
    VALIDATION = "validation"
    EXTERNAL_SERVICE = "external_service"
    PLATFORM = "platform"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BaseDeviceAPIException(Exception):
    """
    Base exception class for all oaDeviceAPI errors.

    Provides structured error information with context, severity,
    and recovery suggestions for better debugging and monitoring.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        recovery_suggestion: str | None = None,
        platform_specific: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.error_code = error_code or self._generate_error_code()
        self.details = details or {}
        self.recovery_suggestion = recovery_suggestion
        self.platform_specific = platform_specific
        self.timestamp = datetime.now(UTC)

    def _generate_error_code(self) -> str:
        """Generate a unique error code based on category and class name."""
        class_name = self.__class__.__name__
        category_prefix = self.category.value.upper()[:3]
        return f"{category_prefix}_{class_name.upper()}"

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.message,
            "error_code": self.error_code,
            "category": self.category.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "recovery_suggestion": self.recovery_suggestion,
            "platform_specific": self.platform_specific
        }

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class SystemError(BaseDeviceAPIException):
    """Errors related to system operations and resources."""

    def __init__(
        self,
        message: str,
        system_component: str | None = None,
        **kwargs
    ):
        kwargs.setdefault('category', ErrorCategory.SYSTEM)
        if system_component:
            kwargs.setdefault('details', {})['system_component'] = system_component
        super().__init__(message, **kwargs)


class ServiceError(BaseDeviceAPIException):
    """Errors related to service management and operations."""

    def __init__(
        self,
        message: str,
        service_name: str | None = None,
        service_status: str | None = None,
        **kwargs
    ):
        kwargs.setdefault('category', ErrorCategory.SERVICE)
        details = kwargs.setdefault('details', {})
        if service_name:
            details['service_name'] = service_name
        if service_status:
            details['service_status'] = service_status
        super().__init__(message, **kwargs)


class ConfigurationError(BaseDeviceAPIException):
    """Errors related to configuration and settings."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        config_value: Any | None = None,
        **kwargs
    ):
        kwargs.setdefault('category', ErrorCategory.CONFIGURATION)
        details = kwargs.setdefault('details', {})
        if config_key:
            details['config_key'] = config_key
        if config_value is not None:
            details['config_value'] = str(config_value)
        super().__init__(message, **kwargs)


class NetworkError(BaseDeviceAPIException):
    """Errors related to network operations and connectivity."""

    def __init__(
        self,
        message: str,
        endpoint: str | None = None,
        status_code: int | None = None,
        **kwargs
    ):
        kwargs.setdefault('category', ErrorCategory.NETWORK)
        details = kwargs.setdefault('details', {})
        if endpoint:
            details['endpoint'] = endpoint
        if status_code:
            details['status_code'] = status_code
        super().__init__(message, **kwargs)


class PermissionError(BaseDeviceAPIException):
    """Errors related to permissions and access control."""

    def __init__(
        self,
        message: str,
        required_permission: str | None = None,
        resource: str | None = None,
        **kwargs
    ):
        kwargs.setdefault('category', ErrorCategory.PERMISSION)
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        details = kwargs.setdefault('details', {})
        if required_permission:
            details['required_permission'] = required_permission
        if resource:
            details['resource'] = resource
        super().__init__(message, **kwargs)


class ValidationError(BaseDeviceAPIException):
    """Errors related to data validation."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        **kwargs
    ):
        kwargs.setdefault('category', ErrorCategory.VALIDATION)
        details = kwargs.setdefault('details', {})
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)
        super().__init__(message, **kwargs)


class ExternalServiceError(BaseDeviceAPIException):
    """Errors related to external service communication."""

    def __init__(
        self,
        message: str,
        service_name: str | None = None,
        endpoint: str | None = None,
        **kwargs
    ):
        kwargs.setdefault('category', ErrorCategory.EXTERNAL_SERVICE)
        details = kwargs.setdefault('details', {})
        if service_name:
            details['service_name'] = service_name
        if endpoint:
            details['endpoint'] = endpoint
        super().__init__(message, **kwargs)


class PlatformError(BaseDeviceAPIException):
    """Errors related to platform-specific operations."""

    def __init__(
        self,
        message: str,
        platform: str | None = None,
        **kwargs
    ):
        kwargs.setdefault('category', ErrorCategory.PLATFORM)
        kwargs['platform_specific'] = True
        if platform:
            kwargs.setdefault('details', {})['platform'] = platform
        super().__init__(message, **kwargs)


# Specific error subclasses for common scenarios
class TrackerError(ExternalServiceError):
    """Specific error for tracker service issues."""

    def __init__(self, message: str, **kwargs):
        kwargs['service_name'] = 'tracker'
        kwargs.setdefault('recovery_suggestion',
                         'Check tracker service status and restart if necessary')
        super().__init__(message, **kwargs)


class CamGuardError(ExternalServiceError):
    """Specific error for CamGuard service issues."""

    def __init__(self, message: str, **kwargs):
        kwargs['service_name'] = 'camguard'
        kwargs.setdefault('recovery_suggestion',
                         'Check CamGuard service status and configuration')
        super().__init__(message, **kwargs)


class HealthCheckError(SystemError):
    """Specific error for health check failures."""

    def __init__(self, message: str, component: str | None = None, **kwargs):
        kwargs['system_component'] = component
        kwargs.setdefault('recovery_suggestion',
                         'Check system resources and service status')
        super().__init__(message, **kwargs)


class MetricsCollectionError(SystemError):
    """Specific error for metrics collection failures."""

    def __init__(self, message: str, metric_type: str | None = None, **kwargs):
        if metric_type:
            kwargs.setdefault('details', {})['metric_type'] = metric_type
        kwargs.setdefault('recovery_suggestion',
                         'Verify system monitoring tools and permissions')
        super().__init__(message, **kwargs)


# Exception mapping for converting standard exceptions
EXCEPTION_MAPPING = {
    ConnectionRefusedError: NetworkError,
    ConnectionError: NetworkError,
    TimeoutError: NetworkError,
    FileNotFoundError: SystemError,
    PermissionError: PermissionError,
    ValueError: ValidationError,
    KeyError: ValidationError,
    AttributeError: ConfigurationError,
}


def convert_exception(
    exc: Exception,
    default_message: str | None = None,
    **kwargs
) -> BaseDeviceAPIException:
    """
    Convert standard exceptions to our unified exception format.

    Args:
        exc: The exception to convert
        default_message: Default message if none can be extracted
        **kwargs: Additional arguments for the exception constructor

    Returns:
        Converted BaseDeviceAPIException
    """
    exc_type = type(exc)
    message = default_message or str(exc) or f"Unexpected {exc_type.__name__}"

    # Use mapping to convert to appropriate exception type
    target_exception_class = EXCEPTION_MAPPING.get(exc_type, SystemError)

    # Add original exception details
    kwargs.setdefault('details', {}).update({
        'original_exception_type': exc_type.__name__,
        'original_exception_message': str(exc)
    })

    return target_exception_class(message, **kwargs)
