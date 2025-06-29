"""Configuration validation utilities.

Provides validation for configuration files, values, and schemas.
Implements CONFIG-03 validation from ADR-0009.
"""

import os
from pathlib import Path
from typing import Dict, Any, List
import toml


class ConfigValidationError(Exception):
    """Configuration validation error.
    
    Raised when configuration validation fails at any level:
    - File syntax errors
    - Schema validation errors
    - Value validation errors
    """
    pass


def validate_config_file(file_path: str) -> None:
    """Validate configuration file exists and has valid syntax.
    
    Args:
        file_path: Path to configuration file
    
    Raises:
        ConfigValidationError: If file is invalid
    """
    path = Path(file_path)
    
    # Check file exists
    if not path.exists():
        raise ConfigValidationError(f"Configuration file not found: {file_path}")
    
    # Check it's a file
    if not path.is_file():
        raise ConfigValidationError(f"Configuration path is not a file: {file_path}")
    
    # Check readable
    if not os.access(path, os.R_OK):
        raise ConfigValidationError(f"Configuration file is not readable: {file_path}")
    
    # Determine file format and validate syntax
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            
        # Try to parse as JSON first (most common for sing-box configs)
        try:
            import json
            json.loads(content)
            return  # JSON is valid
        except json.JSONDecodeError:
            # Not JSON, try TOML
            try:
                import toml
                toml.loads(content)
                return  # TOML is valid
            except toml.TomlDecodeError as e:
                raise ConfigValidationError(f"Invalid TOML syntax in {file_path}: {e}")
            except ImportError:
                raise ConfigValidationError(f"TOML parser not available for {file_path}")
                
    except Exception as e:
        if "JSONDecodeError" in str(type(e)):
            raise ConfigValidationError(f"Invalid JSON syntax in {file_path}: {e}")
        else:
            raise ConfigValidationError(f"Error reading configuration file {file_path}: {e}")


def validate_log_level(level: str) -> str:
    """Validate log level value.
    
    Args:
        level: Log level string
        
    Returns:
        str: Normalized log level
        
    Raises:
        ConfigValidationError: If log level is invalid
    """
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    normalized_level = level.upper()
    
    if normalized_level not in valid_levels:
        raise ConfigValidationError(
            f"Invalid log level: {level}. Must be one of {valid_levels}"
        )
    
    return normalized_level


def validate_log_sinks(sinks: List[str]) -> List[str]:
    """Validate log sink configuration.
    
    Args:
        sinks: List of sink names
        
    Returns:
        List[str]: Validated sink names
        
    Raises:
        ConfigValidationError: If any sink is invalid
    """
    valid_sinks = ["auto", "stdout", "stderr", "journald", "syslog", "file"]
    
    for sink in sinks:
        if sink not in valid_sinks:
            raise ConfigValidationError(
                f"Invalid log sink: {sink}. Must be one of {valid_sinks}"
            )
    
    return sinks


def validate_port_number(port: int, name: str = "port") -> int:
    """Validate port number is in valid range.
    
    Args:
        port: Port number
        name: Port name for error messages
        
    Returns:
        int: Validated port number
        
    Raises:
        ConfigValidationError: If port is invalid
    """
    if not isinstance(port, int):
        raise ConfigValidationError(f"{name} must be an integer, got {type(port)}")
    
    if port < 1 or port > 65535:
        raise ConfigValidationError(f"{name} must be between 1 and 65535, got {port}")
    
    return port


def validate_file_path_writable(file_path: str, name: str = "file") -> str:
    """Validate file path is writable.
    
    Args:
        file_path: File path to validate
        name: File name for error messages
        
    Returns:
        str: Validated file path
        
    Raises:
        ConfigValidationError: If path is not writable
    """
    path = Path(file_path)
    
    # Check parent directory exists
    if not path.parent.exists():
        raise ConfigValidationError(f"{name} directory does not exist: {path.parent}")
    
    # Check parent directory is writable
    if not os.access(path.parent, os.W_OK):
        raise ConfigValidationError(f"{name} directory is not writable: {path.parent}")
    
    # If file exists, check it's writable
    if path.exists() and not os.access(path, os.W_OK):
        raise ConfigValidationError(f"{name} is not writable: {file_path}")
    
    return file_path


def validate_environment_variables(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validate environment variable configuration.
    
    Checks that environment variables are properly formatted and accessible.
    
    Args:
        config_dict: Configuration dictionary
        
    Returns:
        Dict[str, Any]: Validated configuration
        
    Raises:
        ConfigValidationError: If environment configuration is invalid
    """
    # Check for conflicting environment variables
    env_conflicts = []
    
    # Check for common conflicts
    if os.getenv("SBOXMGR_SERVICE_MODE") and os.getenv("SBOXMGR_DEBUG"):
        service_mode = os.getenv("SBOXMGR_SERVICE_MODE", "").lower() in ("true", "1", "yes")
        debug_mode = os.getenv("SBOXMGR_DEBUG", "").lower() in ("true", "1", "yes")
        
        if service_mode and debug_mode:
            env_conflicts.append("Service mode and debug mode are both enabled")
    
    if env_conflicts:
        raise ConfigValidationError(f"Environment variable conflicts: {'; '.join(env_conflicts)}")
    
    return config_dict


def validate_service_configuration(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validate service mode configuration.
    
    Args:
        config_dict: Configuration dictionary
        
    Returns:
        Dict[str, Any]: Validated configuration
        
    Raises:
        ConfigValidationError: If service configuration is invalid
    """
    service_config = config_dict.get("service", {})
    
    if not isinstance(service_config, dict):
        raise ConfigValidationError("Service configuration must be a dictionary")
    
    # Validate service mode dependencies
    if service_config.get("service_mode", False):
        # In service mode, certain combinations don't make sense
        logging_config = config_dict.get("logging", {})
        
        if logging_config.get("format") == "text" and logging_config.get("sinks") == ["journald"]:
            # Suggest JSON format for journald
            pass  # This is just a recommendation, not an error
    
    return config_dict


def get_validation_summary(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Get validation summary for configuration.
    
    Args:
        config_dict: Configuration dictionary.
        
    Returns:
        Dict containing validation results and recommendations.
    """
    summary: Dict[str, Any] = {
        "valid": True,
        "warnings": [],
        "recommendations": [],
        "errors": []
    }
    
    # Add explicit type annotations for lists
    warnings: List[str] = summary["warnings"]
    recommendations: List[str] = summary["recommendations"]
    errors: List[str] = summary["errors"]
    
    try:
        # Run all validations
        validate_environment_variables(config_dict)
        validate_service_configuration(config_dict)
        
        # Check for recommendations
        logging_config = config_dict.get("logging", {})
        service_config = config_dict.get("service", {})
        
        # Service mode recommendations
        if service_config.get("service_mode", False):
            if logging_config.get("format") == "text":
                recommendations.append(
                    "Consider using JSON log format in service mode for better parsing"
                )
            
            if logging_config.get("level") == "DEBUG":
                recommendations.append(
                    "Consider using INFO log level in service mode for better performance"
                )
        
        # Development mode recommendations
        if config_dict.get("debug", False):
            if not logging_config.get("enable_trace_id", True):
                recommendations.append(
                    "Enable trace ID in debug mode for better debugging"
                )
        
        # File logging recommendations
        if "file" in logging_config.get("sinks", []):
            if not logging_config.get("file_path"):
                warnings.append(
                    "File sink specified but no file path configured"
                )
    
    except ConfigValidationError as e:
        summary["valid"] = False
        errors.append(str(e))
    
    return summary 