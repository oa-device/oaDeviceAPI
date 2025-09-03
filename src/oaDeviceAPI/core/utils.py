"""
Unified utilities module for oaDeviceAPI.

Consolidates shared functionality across platform-specific implementations
to eliminate code duplication and ensure consistent behavior.
"""

import subprocess
from functools import lru_cache
from time import time
from typing import Dict, List, Optional, Any, Callable, TypeVar, Tuple, Union
from pathlib import Path

F = TypeVar('F', bound=Callable[..., Any])


def run_command(cmd: List[str], env: Optional[Dict] = None, timeout: int = 30) -> str:
    """
    Run a shell command and return its output.
    
    Unified command execution with consistent error handling across platforms.
    
    Args:
        cmd: Command and arguments as list
        env: Optional environment variables
        timeout: Command timeout in seconds
        
    Returns:
        Command output as string, empty string on error
    """
    import os
    try:
        # Inherit parent environment and merge with provided env
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        
        result = subprocess.run(
            cmd,
            env=merged_env,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def run_command_detailed(command: List[str], timeout: int = 10) -> Dict[str, Any]:
    """
    Run a command with detailed result information.
    
    Used for cases requiring detailed execution information beyond just output.
    
    Args:
        command: Command and arguments as list
        timeout: Command timeout in seconds
        
    Returns:
        Dictionary with returncode, stdout, stderr, and success status
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out",
            "success": False
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False
        }


def cache_with_ttl(ttl_seconds: int) -> Callable[[F], F]:
    """
    Decorator that implements an LRU cache with time-based invalidation.
    
    Args:
        ttl_seconds: Time-to-live for cached values in seconds
        
    Returns:
        Decorated function with TTL cache
    """
    def decorator(func):
        # Use a cache of size 1 since we only need the latest value
        func = lru_cache(maxsize=1)(func)
        # Store the last refresh time
        func.last_refresh = 0

        def wrapper(*args, **kwargs):
            # Check if cache needs refresh
            now = time()
            if now - func.last_refresh > ttl_seconds:
                # Clear cache and update refresh time
                func.cache_clear()
                func.last_refresh = now
            
            return func(*args, **kwargs)
        
        # Preserve function attributes and cache methods
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.cache_info = func.cache_info
        wrapper.cache_clear = func.cache_clear
        return wrapper
    
    return decorator


def format_bytes(bytes_value: int) -> str:
    """
    Format byte count into human-readable string.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB", "512 MB")
    """
    if bytes_value == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    
    while bytes_value >= 1024 and i < len(size_names) - 1:
        bytes_value /= 1024.0
        i += 1
    
    return f"{bytes_value:.1f} {size_names[i]}"


def parse_version(version_string: str) -> Tuple[int, ...]:
    """
    Parse version string into comparable tuple.
    
    Args:
        version_string: Version string (e.g., "1.2.3", "2.0.0-beta")
        
    Returns:
        Tuple of version components for comparison
    """
    try:
        # Remove any non-numeric suffixes (like -beta, -rc1)
        clean_version = version_string.split('-')[0]
        return tuple(map(int, clean_version.split('.')))
    except (ValueError, AttributeError):
        return (0,)


def safe_dict_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get value from dictionary with nested key support.
    
    Args:
        dictionary: Target dictionary
        key: Key or dot-separated nested key path
        default: Default value if key not found
        
    Returns:
        Value from dictionary or default
    """
    try:
        if '.' not in key:
            return dictionary.get(key, default)
        
        # Handle nested keys like "system.memory.total"
        current = dictionary
        for key_part in key.split('.'):
            if isinstance(current, dict) and key_part in current:
                current = current[key_part]
            else:
                return default
        
        return current
    except (AttributeError, TypeError):
        return default


def validate_command_path(command: str) -> bool:
    """
    Validate that a command exists and is executable.
    
    Args:
        command: Command name or path
        
    Returns:
        True if command is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["which", command], 
            capture_output=True, 
            text=True, 
            check=False
        )
        return result.returncode == 0 and result.stdout.strip() != ""
    except Exception:
        return False