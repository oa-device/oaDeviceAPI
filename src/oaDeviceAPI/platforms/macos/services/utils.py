"""
macOS-specific utilities module.

This module now imports shared utilities from core.utils and provides
macOS-specific utility functions only.
"""

from typing import Dict, List, Optional
from oaDeviceAPI.core.utils import (
    run_command,
    cache_with_ttl,
    format_bytes,
    parse_version,
    safe_dict_get
)


def get_system_profiler_info(data_type: str) -> Dict:
    """
    Get system information using system_profiler command.
    
    Args:
        data_type: Type of data to retrieve (e.g., 'SPHardwareDataType')
        
    Returns:
        Parsed system profiler data
    """
    try:
        output = run_command(['system_profiler', '-json', data_type])
        if output:
            import json
            return json.loads(output)
    except Exception:
        pass
    return {}


def get_launchd_service_status(service_name: str) -> Dict:
    """
    Get macOS LaunchAgent/LaunchDaemon service status.
    
    Args:
        service_name: Name of the service to check
        
    Returns:
        Service status information
    """
    try:
        output = run_command(['launchctl', 'list', service_name])
        if output:
            # Parse launchctl output into structured data
            lines = output.strip().split('\n')
            if len(lines) >= 1:
                parts = lines[0].split('\t')
                if len(parts) >= 3:
                    return {
                        'pid': parts[0] if parts[0] != '-' else None,
                        'status': int(parts[1]) if parts[1] != '-' else 0,
                        'label': parts[2],
                        'running': parts[0] != '-'
                    }
    except Exception:
        pass
    
    return {
        'pid': None,
        'status': -1,
        'label': service_name,
        'running': False
    }