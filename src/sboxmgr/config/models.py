"""Configuration models using Pydantic BaseSettings.

Implements ADR-0009 Configuration System Architecture with:
- Hierarchical configuration (CLI > env > file > defaults)
- Service mode auto-detection
- Type-safe validation with clear error messages
- Environment variable support with nested delimiter
"""

import os
from pathlib import Path
from typing import Dict, List, Literal, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from .detection import detect_service_mode, detect_container_environment


class LoggingConfig(BaseSettings):
    """Logging configuration with multi-sink support.
    
    Implements LOG-01, LOG-02, LOG-03 from ADR-0010.
    Supports hierarchical log levels and automatic sink detection.
    """
    
    # Core logging settings
    level: str = Field(
        default="INFO",
        description="Global logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    format: Literal["text", "json"] = Field(
        default="text",
        description="Log output format (text for CLI, json for service)"
    )
    
    # Sink configuration  
    sinks: List[str] = Field(
        default=["auto"],
        description="Logging sinks (auto, stdout, journald, syslog, file)"
    )
    sink_levels: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-sink log level overrides"
    )
    
    # File logging settings
    file_path: Optional[str] = Field(
        default=None,
        description="Log file path (when file sink is used)"
    )
    max_file_size: int = Field(
        default=10_000_000,
        description="Maximum log file size in bytes"
    )
    backup_count: int = Field(
        default=5,
        description="Number of backup log files to keep"
    )
    
    # Advanced settings
    enable_trace_id: bool = Field(
        default=True,
        description="Enable trace ID generation and propagation"
    )
    structured_metadata: bool = Field(
        default=True,
        description="Include structured metadata in log entries"
    )
    
    model_config = {
        "env_prefix": "SBOXMGR_LOGGING_",
        "env_nested_delimiter": "__",
        "case_sensitive": False
    }
    
    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is one of the standard levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()
    
    @field_validator('sinks')
    @classmethod
    def validate_sinks(cls, v):
        """Validate sink names are recognized."""
        valid_sinks = ["auto", "stdout", "stderr", "journald", "syslog", "file"]
        for sink in v:
            if sink not in valid_sinks:
                raise ValueError(f"Invalid sink: {sink}. Must be one of {valid_sinks}")
        return v
    
    @field_validator('sink_levels')
    @classmethod
    def validate_sink_levels(cls, v):
        """Validate per-sink log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for sink, level in v.items():
            if level.upper() not in valid_levels:
                raise ValueError(f"Invalid log level for sink {sink}: {level}")
        return {k: v.upper() for k, v in v.items()}
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        """Validate file path is writable when specified."""
        if v is not None:
            path = Path(v)
            # Check if parent directory exists and is writable
            if not path.parent.exists():
                raise ValueError(f"Log file directory does not exist: {path.parent}")
            if not os.access(path.parent, os.W_OK):
                raise ValueError(f"Log file directory is not writable: {path.parent}")
        return v


class ServiceConfig(BaseSettings):
    """Service mode configuration.
    
    Implements CONFIG-02 service mode detection and daemon settings.
    """
    
    # Service mode detection
    service_mode: bool = Field(
        default_factory=detect_service_mode,
        description="Enable service/daemon mode"
    )
    
    # Daemon settings
    pid_file: Optional[str] = Field(
        default=None,
        description="PID file path for daemon mode"
    )
    user: Optional[str] = Field(
        default=None,
        description="User to run service as"
    )
    group: Optional[str] = Field(
        default=None,
        description="Group to run service as"
    )
    
    # Health check settings
    health_check_port: int = Field(
        default=8080,
        description="Port for health check endpoint"
    )
    health_check_enabled: bool = Field(
        default=True,
        description="Enable health check endpoint"
    )
    
    # Metrics settings
    metrics_port: int = Field(
        default=9090,
        description="Port for metrics endpoint"
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Enable metrics collection and endpoint"
    )
    
    model_config = {
        "env_prefix": "SBOXMGR_SERVICE_",
        "env_nested_delimiter": "__",
        "case_sensitive": False
    }


class AppSettings(BaseSettings):
    """Core application settings section."""
    
    name: str = Field(
        default="sboxmgr",
        description="Application name"
    )
    version: str = Field(
        default="0.2.0",
        description="Application version"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output"
    )
    
    model_config = {
        "env_prefix": "SBOXMGR_APP_",
        "env_nested_delimiter": "__",
        "case_sensitive": False
    }


class AppConfig(BaseSettings):
    """Main application configuration.
    
    Implements ADR-0009 hierarchical configuration with Pydantic BaseSettings.
    Combines all configuration sections with proper validation.
    """
    
    # Configuration file
    config_file: Optional[str] = Field(
        default=None,
        description="Path to configuration file (TOML format)"
    )
    
    # Container/environment detection
    container_mode: bool = Field(
        default_factory=detect_container_environment,
        description="Detected container environment"
    )
    
    # Nested configuration sections
    app: AppSettings = Field(
        default_factory=AppSettings,
        description="Core application settings"
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration"
    )
    service: ServiceConfig = Field(
        default_factory=ServiceConfig,
        description="Service mode configuration"
    )
    
    model_config = {
        "env_prefix": "SBOXMGR_",
        "env_nested_delimiter": "__",
        "env_file": ".env",
        "case_sensitive": False,
        # Allow population by field name for CLI integration
        "validate_by_name": True,
        # Allow extra fields for backward compatibility
        "extra": "allow"
    }
        
    def __init__(self, **kwargs):
        """Initialize with proper environment variable handling for nested models."""
        # Don't override nested configs if they're provided
        # Let Pydantic handle environment variables for nested models
        super().__init__(**kwargs)
    
    @field_validator('config_file')
    @classmethod
    def validate_config_file_exists(cls, v):
        """Validate configuration file exists and is readable."""
        if v is not None:
            path = Path(v)
            if not path.exists():
                raise ValueError(f"Configuration file not found: {v}")
            if not path.is_file():
                raise ValueError(f"Configuration path is not a file: {v}")
            if not os.access(path, os.R_OK):
                raise ValueError(f"Configuration file is not readable: {v}")
        return v
    
    @model_validator(mode='after')
    def adjust_for_service_mode(self):
        """Adjust configuration based on service mode.
        
        When in service mode:
        - Use JSON logging format
        - Prefer journald sink
        - Keep explicit DEBUG settings (don't downgrade)
        """
        if self.service.service_mode:
            # Create new instances with updated values to preserve validation
            updates = {}
            
            # Service mode optimizations - use model_copy to maintain validation
            if self.logging.format == "text":
                updates['logging'] = self.logging.model_copy(update={'format': 'json'})
            
            # Prefer journald in service mode
            if self.logging.sinks == ["auto"]:
                current_logging = updates.get('logging', self.logging)
                updates['logging'] = current_logging.model_copy(update={'sinks': ['journald']})
            
            # BUG FIX: Don't downgrade explicit DEBUG settings
            # Only adjust level if it wasn't explicitly set by user
            # This preserves troubleshooting capability in service mode
            
            # Apply updates using model_copy to maintain validation
            if updates:
                # Update self with new validated instances
                for key, value in updates.items():
                    setattr(self, key, value)
        
        return self
    
    def dump_config(self) -> Dict:
        """Export configuration as dictionary for debugging.
        
        Used by --dump-config command to show resolved configuration.
        """
        return self.dict(exclude_unset=False, exclude_none=False)
    
    def generate_json_schema(self) -> Dict:
        """Generate JSON schema for configuration documentation."""
        return self.schema()


def create_default_config() -> AppConfig:
    """Create default configuration instance.
    
    This is the primary factory function for creating configuration objects.
    Uses environment variables and auto-detection for initial setup.
    """
    return AppConfig()


def create_config_from_dict(data: Dict) -> AppConfig:
    """Create configuration from dictionary data.
    
    Used for loading configuration from files or CLI arguments.
    """
    return AppConfig(**data) 