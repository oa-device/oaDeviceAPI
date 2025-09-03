"""
Configuration schema and validation for oaDeviceAPI.

This module provides structured configuration with validation,
environment-specific settings, and platform-specific configurations.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Union, List
from pydantic import BaseModel, Field, validator, root_validator, model_validator
from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Platform(str, Enum):
    """Supported platforms."""
    MACOS = "macos"
    ORANGEPI = "orangepi"
    LINUX = "linux"
    UNKNOWN = "unknown"


class ServiceManager(str, Enum):
    """Supported service managers."""
    LAUNCHCTL = "launchctl"
    SYSTEMCTL = "systemctl"
    UNKNOWN = "unknown"


class NetworkConfig(BaseModel):
    """Network-related configuration."""
    host: str = Field(default="0.0.0.0", description="API host address")
    port: int = Field(default=9090, ge=1, le=65535, description="API port number")
    tailscale_subnet: str = Field(
        default="100.64.0.0/10",
        description="Tailscale subnet for access control"
    )
    
    @validator('tailscale_subnet')
    def validate_subnet(cls, v):
        """Validate subnet format."""
        import ipaddress
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError:
            raise ValueError(f"Invalid subnet format: {v}")
        return v


class SecurityConfig(BaseModel):
    """Security-related configuration."""
    enable_cors: bool = Field(default=True, description="Enable CORS middleware")
    cors_origins: List[str] = Field(default=["*"], description="Allowed CORS origins")
    enable_tailscale_restriction: bool = Field(
        default=True, 
        description="Restrict access to Tailscale subnet"
    )
    api_key: Optional[str] = Field(default=None, description="Optional API key for authentication")
    rate_limiting: bool = Field(default=False, description="Enable rate limiting")
    max_requests_per_minute: int = Field(
        default=60, 
        ge=1, 
        description="Max requests per minute per IP"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    enable_structured_logging: bool = Field(
        default=False, 
        description="Enable structured JSON logging"
    )
    log_to_file: bool = Field(default=False, description="Enable file logging")
    log_file_path: Optional[Path] = Field(default=None, description="Log file path")
    max_file_size_mb: int = Field(default=100, ge=1, description="Max log file size in MB")
    backup_count: int = Field(default=5, ge=1, description="Number of backup log files")
    
    @validator('log_file_path', pre=True)
    def validate_log_path(cls, v):
        """Validate and expand log file path."""
        if v is None:
            return None
        path = Path(v).expanduser().resolve()
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class CacheConfig(BaseModel):
    """Caching configuration."""
    enable_caching: bool = Field(default=True, description="Enable response caching")
    default_ttl: int = Field(default=30, ge=1, description="Default cache TTL in seconds")
    max_cache_size: int = Field(default=1000, ge=1, description="Maximum cache entries")
    
    # Specific TTL settings for different operations
    health_metrics_ttl: int = Field(default=30, ge=1, description="Health metrics cache TTL")
    service_status_ttl: int = Field(default=60, ge=1, description="Service status cache TTL")
    system_info_ttl: int = Field(default=300, ge=1, description="System info cache TTL")


class PlatformSpecificConfig(BaseModel):
    """Platform-specific configuration."""
    platform: Platform = Field(description="Detected or overridden platform")
    service_manager: ServiceManager = Field(description="Service management system")
    bin_paths: List[Path] = Field(default_factory=list, description="Binary search paths")
    temp_dir: Path = Field(default=Path("/tmp"), description="Temporary directory")
    
    # macOS specific
    macos_bin_dir: Path = Field(default=Path("/usr/local/bin"))
    macos_service_dir: Path = Field(default=Path.home() / "Library/LaunchAgents")
    
    # OrangePi specific
    orangepi_display_config: Path = Field(default=Path("/etc/orangead/display.conf"))
    orangepi_player_service: str = Field(default="slideshow-player.service")
    
    @validator('bin_paths', pre=True)
    def expand_bin_paths(cls, v):
        """Expand and validate binary paths."""
        if not v:
            return []
        return [Path(path).expanduser().resolve() for path in v]


class ServiceConfig(BaseModel):
    """Service-specific configuration."""
    service_timeout: int = Field(default=30, ge=1, description="Service operation timeout")
    health_check_interval: int = Field(
        default=60, 
        ge=10, 
        description="Health check interval in seconds"
    )
    
    # Tracker service
    tracker_root_dir: Path = Field(
        default=Path("~/orangead/tracker"), 
        description="Tracker root directory"
    )
    tracker_api_url: str = Field(
        default="http://localhost:8080", 
        description="Tracker API URL"
    )
    
    # Screenshot settings
    screenshot_dir: Path = Field(default=Path("/tmp/screenshots"))
    screenshot_quality: int = Field(default=85, ge=1, le=100, description="Screenshot quality")
    
    @validator('tracker_root_dir', pre=True)
    def expand_tracker_path(cls, v):
        """Expand tracker root directory path."""
        return Path(v).expanduser().resolve()
    
    @validator('screenshot_dir', pre=True)
    def expand_screenshot_dir(cls, v):
        """Expand and create screenshot directory."""
        path = Path(v).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @validator('tracker_api_url')
    def validate_tracker_url(cls, v):
        """Validate tracker API URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Tracker API URL must start with http:// or https://")
        return v


class HealthConfig(BaseModel):
    """Health monitoring configuration."""
    enable_health_scoring: bool = Field(default=True, description="Enable health scoring")
    
    # Health score weights (must sum to 1.0)
    cpu_weight: float = Field(default=0.25, ge=0, le=1, description="CPU health weight")
    memory_weight: float = Field(default=0.25, ge=0, le=1, description="Memory health weight")
    disk_weight: float = Field(default=0.25, ge=0, le=1, description="Disk health weight")
    tracker_weight: float = Field(default=0.25, ge=0, le=1, description="Tracker health weight")
    
    # Health thresholds (percentages)
    cpu_warning_threshold: float = Field(default=80, ge=0, le=100)
    cpu_critical_threshold: float = Field(default=95, ge=0, le=100)
    
    memory_warning_threshold: float = Field(default=80, ge=0, le=100)
    memory_critical_threshold: float = Field(default=95, ge=0, le=100)
    
    disk_warning_threshold: float = Field(default=85, ge=0, le=100)
    disk_critical_threshold: float = Field(default=95, ge=0, le=100)
    
    @model_validator(mode='before')
    def validate_weights(cls, values):
        """Ensure health weights sum to 1.0."""
        weight_sum = (
            values.get('cpu_weight', 0) +
            values.get('memory_weight', 0) +
            values.get('disk_weight', 0) +
            values.get('tracker_weight', 0)
        )
        
        if abs(weight_sum - 1.0) > 0.001:  # Allow small floating point errors
            raise ValueError(f"Health weights must sum to 1.0, got {weight_sum}")
        
        return values
    
    @model_validator(mode='before')
    @classmethod
    def validate_thresholds(cls, values):
        """Ensure critical thresholds are higher than warning thresholds."""
        for component in ['cpu', 'memory', 'disk']:
            warning_key = f'{component}_warning_threshold'
            critical_key = f'{component}_critical_threshold'
            
            warning = values.get(warning_key, 0)
            critical = values.get(critical_key, 100)
            
            if warning >= critical:
                raise ValueError(
                    f"{component} warning threshold ({warning}) must be less than "
                    f"critical threshold ({critical})"
                )
        
        return values


class DevConfig(BaseModel):
    """Development and debugging configuration."""
    debug: bool = Field(default=False, description="Enable debug mode")
    include_traceback: bool = Field(default=False, description="Include tracebacks in responses")
    enable_profiling: bool = Field(default=False, description="Enable performance profiling")
    mock_external_services: bool = Field(default=False, description="Mock external services")
    enable_test_endpoints: bool = Field(default=False, description="Enable test endpoints")
    
    @validator('include_traceback')
    def sync_with_debug(cls, v, values):
        """Auto-enable traceback in debug mode."""
        if values.get('debug', False):
            return True
        return v


class AppConfig(BaseSettings):
    """
    Main application configuration.
    
    Combines all configuration sections with validation and environment variable support.
    """
    
    # Configuration sections
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    platform: PlatformSpecificConfig = Field(default_factory=PlatformSpecificConfig)
    services: ServiceConfig = Field(default_factory=ServiceConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    dev: DevConfig = Field(default_factory=DevConfig)
    
    # App metadata
    app_name: str = Field(default="oaDeviceAPI")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="production", description="Environment name")
    
    # Legacy compatibility fields (will be deprecated)
    host: Optional[str] = Field(default=None, deprecated=True)
    port: Optional[int] = Field(default=None, deprecated=True)
    log_level: Optional[str] = Field(default=None, deprecated=True)
    tailscale_subnet: Optional[str] = Field(default=None, deprecated=True)
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False
        extra = "ignore"
        
        # Environment variable prefixes for nested configs
        fields = {
            'network': {'env_prefix': 'NETWORK_'},
            'security': {'env_prefix': 'SECURITY_'},
            'logging': {'env_prefix': 'LOG_'},
            'cache': {'env_prefix': 'CACHE_'},
            'platform': {'env_prefix': 'PLATFORM_'},
            'services': {'env_prefix': 'SERVICE_'},
            'health': {'env_prefix': 'HEALTH_'},
            'dev': {'env_prefix': 'DEV_'},
        }
    
    @root_validator
    def handle_legacy_fields(cls, values):
        """Handle legacy configuration fields for backward compatibility."""
        # Map legacy fields to new structure
        if values.get('host') is not None:
            if 'network' not in values:
                values['network'] = {}
            values['network']['host'] = values['host']
        
        if values.get('port') is not None:
            if 'network' not in values:
                values['network'] = {}
            values['network']['port'] = values['port']
        
        if values.get('log_level') is not None:
            if 'logging' not in values:
                values['logging'] = {}
            values['logging']['level'] = values['log_level'].upper()
        
        if values.get('tailscale_subnet') is not None:
            if 'network' not in values:
                values['network'] = {}
            values['network']['tailscale_subnet'] = values['tailscale_subnet']
        
        return values
    
    def get_cache_ttl(self, cache_type: str) -> int:
        """Get cache TTL for a specific type."""
        ttl_map = {
            'health_metrics': self.cache.health_metrics_ttl,
            'service_status': self.cache.service_status_ttl,
            'system_info': self.cache.system_info_ttl,
        }
        return ttl_map.get(cache_type, self.cache.default_ttl)
    
    def get_health_weights(self) -> Dict[str, float]:
        """Get health score weights as a dictionary."""
        return {
            'cpu': self.health.cpu_weight,
            'memory': self.health.memory_weight,
            'disk': self.health.disk_weight,
            'tracker': self.health.tracker_weight,
        }
    
    def get_health_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Get health thresholds as a nested dictionary."""
        return {
            'cpu': {
                'warning': self.health.cpu_warning_threshold,
                'critical': self.health.cpu_critical_threshold,
            },
            'memory': {
                'warning': self.health.memory_warning_threshold,
                'critical': self.health.memory_critical_threshold,
            },
            'disk': {
                'warning': self.health.disk_warning_threshold,
                'critical': self.health.disk_critical_threshold,
            },
        }
    
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.dev.debug or self.environment.lower() in ['dev', 'development', 'debug']
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() in ['prod', 'production']