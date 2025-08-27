"""
OrangePi-specific utilities module.

This module now imports shared utilities from core.utils and provides
OrangePi-specific utility functions only.
"""

from typing import Dict, List, Optional
from oaDeviceAPI.core.utils import (
    run_command,
    cache_with_ttl,
    format_bytes,
    parse_version,
    safe_dict_get
) 