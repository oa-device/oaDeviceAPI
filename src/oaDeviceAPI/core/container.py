"""
Dependency Injection Container for oaDeviceAPI.

Provides a service registry pattern for managing dependencies and enabling
loose coupling between components. Supports singleton and transient lifecycle
management with type-safe dependency resolution.
"""

import inspect
from typing import Any, Callable, Dict, Type, TypeVar, get_type_hints
from functools import wraps
from threading import Lock

from .exceptions import ServiceError, ErrorSeverity

T = TypeVar('T')


class ServiceContainer:
    """
    Dependency injection container supporting service registration,
    resolution, and automatic dependency injection via decorators.
    """

    def __init__(self):
        self._services: Dict[Type, Type] = {}
        self._singletons: Dict[Type, Any] = {}
        self._instances: Dict[Type, Any] = {}
        self._lock = Lock()

    def register(
        self,
        interface: Type[T],
        implementation: Type[T],
        singleton: bool = True
    ) -> 'ServiceContainer':
        """
        Register a service implementation for an interface.

        Args:
            interface: The interface or abstract base class
            implementation: The concrete implementation
            singleton: Whether to use singleton pattern (default: True)

        Returns:
            Self for chaining
        """
        with self._lock:
            self._services[interface] = implementation
            if singleton:
                self._singletons[interface] = True

        return self

    def register_instance(self, interface: Type[T], instance: T) -> 'ServiceContainer':
        """
        Register a specific instance for an interface.

        Args:
            interface: The interface type
            instance: The pre-created instance

        Returns:
            Self for chaining
        """
        with self._lock:
            self._instances[interface] = instance
            self._singletons[interface] = True

        return self

    def get(self, interface: Type[T]) -> T:
        """
        Resolve a service instance by interface type.

        Args:
            interface: The interface type to resolve

        Returns:
            The service instance

        Raises:
            ServiceError: If service is not registered or cannot be instantiated
        """
        try:
            with self._lock:
                # Check for pre-registered instances
                if interface in self._instances:
                    return self._instances[interface]

                # Check if registered
                if interface not in self._services:
                    raise ServiceError(
                        f"Service {interface.__name__} is not registered",
                        category="configuration",
                        severity=ErrorSeverity.HIGH
                    )

                implementation = self._services[interface]

                # Handle singleton pattern
                if interface in self._singletons:
                    if interface not in self._instances:
                        self._instances[interface] = self._create_instance(implementation)
                    return self._instances[interface]
                else:
                    # Transient - create new instance each time
                    return self._create_instance(implementation)

        except Exception as e:
            raise ServiceError(
                f"Failed to resolve service {interface.__name__}: {str(e)}",
                category="dependency_injection",
                severity=ErrorSeverity.HIGH
            ) from e

    def _create_instance(self, implementation: Type[T]) -> T:
        """
        Create an instance with automatic dependency injection.

        Args:
            implementation: The implementation class to instantiate

        Returns:
            The created instance with injected dependencies
        """
        # Get constructor signature
        signature = inspect.signature(implementation.__init__)
        type_hints = get_type_hints(implementation.__init__)

        # Resolve constructor parameters
        kwargs = {}
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue

            # Get parameter type from type hints
            param_type = type_hints.get(param_name)
            if param_type is None:
                continue

            # Try to resolve dependency
            if param_type in self._services or param_type in self._instances:
                kwargs[param_name] = self.get(param_type)
            elif param.default is not param.empty:
                # Use default value if available
                kwargs[param_name] = param.default

        return implementation(**kwargs)

    def inject(self, func: Callable) -> Callable:
        """
        Decorator for automatic dependency injection in functions.

        Args:
            func: The function to decorate

        Returns:
            Decorated function with dependency injection
        """
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Resolve missing parameters
            for param_name, param in signature.parameters.items():
                if param_name in kwargs:
                    continue

                param_type = type_hints.get(param_name)
                if param_type and (param_type in self._services or param_type in self._instances):
                    kwargs[param_name] = self.get(param_type)

            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Resolve missing parameters
            for param_name, param in signature.parameters.items():
                if param_name in kwargs:
                    continue

                param_type = type_hints.get(param_name)
                if param_type and (param_type in self._services or param_type in self._instances):
                    kwargs[param_name] = self.get(param_type)

            return await func(*args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(func) else wrapper

    def clear(self) -> None:
        """Clear all registrations and instances."""
        with self._lock:
            self._services.clear()
            self._singletons.clear()
            self._instances.clear()

    def is_registered(self, interface: Type) -> bool:
        """Check if a service is registered."""
        return interface in self._services or interface in self._instances

    def get_registered_services(self) -> Dict[Type, Type]:
        """Get all registered service mappings."""
        with self._lock:
            return self._services.copy()


# Global container instance
container = ServiceContainer()