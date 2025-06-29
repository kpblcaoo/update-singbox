"""Configuration loading utilities.

Implements multi-layer configuration loading from files, environment variables,
and CLI arguments with proper precedence handling.
"""

from pathlib import Path
from typing import Optional, Dict, Any

import toml
import yaml
from pydantic import ValidationError

from .models import AppConfig


def load_config(config_file_path: Optional[str] = None) -> AppConfig:
    """Load configuration from file and environment variables.
    
    Args:
        config_file_path: Optional path to configuration file
        
    Returns:
        AppConfig: Loaded and validated configuration
        
    Raises:
        ValidationError: If configuration validation fails
        FileNotFoundError: If specified config file doesn't exist
    """
    config_data = {}
    
    # Load from file if specified
    if config_file_path:
        config_data = load_config_file(config_file_path)
    
    # Create config with file data (environment variables handled by Pydantic)
    try:
        # Include config_file in initialization to trigger validation
        if config_file_path:
            config_data['config_file'] = config_file_path
        config = AppConfig(**config_data)
        return config
    except ValidationError:
        # Re-raise original ValidationError to preserve structured error details
        raise


def load_config_file(file_path: str) -> Dict[str, Any]:
    """Load configuration from TOML or YAML file.
    
    Args:
        file_path: Path to configuration file
        
    Returns:
        Dict containing configuration data
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is unsupported or invalid
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    if not path.is_file():
        raise ValueError(f"Configuration path is not a file: {file_path}")
    
    # Determine file format
    suffix = path.suffix.lower()
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            if suffix in ['.toml']:
                return toml.load(f)
            elif suffix in ['.yaml', '.yml']:
                return yaml.safe_load(f)
            elif suffix in ['.json']:
                import json
                return json.load(f)
            else:
                # Try to auto-detect format
                content = f.read()
                
                # Try TOML first
                try:
                    return toml.loads(content)
                except toml.TomlDecodeError:
                    pass
                
                # Try YAML
                try:
                    return yaml.safe_load(content)
                except yaml.YAMLError:
                    pass
                
                # Try JSON
                try:
                    import json
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass
                
                raise ValueError(f"Unsupported configuration file format: {suffix}")
    
    except Exception as e:
        raise ValueError(f"Error reading configuration file {file_path}: {e}")


def find_config_file() -> Optional[str]:
    """Find configuration file in standard locations.
    
    Searches for configuration files in:
    1. Current directory
    2. ~/.sboxmgr/
    3. /etc/sboxmgr/
    
    Returns:
        Optional path to found configuration file
    """
    search_paths = [
        Path.cwd(),
        Path.home() / ".sboxmgr",
        Path("/etc/sboxmgr")
    ]
    
    config_names = [
        "config.toml",
        "config.yaml", 
        "config.yml",
        "config.json",
        "sboxmgr.toml",
        "sboxmgr.yaml",
        "sboxmgr.yml"
    ]
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
            
        for config_name in config_names:
            config_file = search_path / config_name
            if config_file.exists() and config_file.is_file():
                return str(config_file)
    
    return None


def save_config(config: AppConfig, file_path: str) -> None:
    """Save configuration to file.
    
    Args:
        config: Configuration to save
        file_path: Path to save configuration file
        
    Raises:
        ValueError: If file format is unsupported
        OSError: If file cannot be written
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get configuration data
    config_data = config.model_dump(exclude_unset=True, exclude_none=True)
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            if suffix in ['.toml']:
                toml.dump(config_data, f)
            elif suffix in ['.yaml', '.yml']:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            elif suffix in ['.json']:
                import json
                json.dump(config_data, f, indent=2)
            else:
                raise ValueError(f"Unsupported configuration file format: {suffix}")
    
    except Exception as e:
        raise OSError(f"Error writing configuration file {file_path}: {e}")


def create_default_config_file(output_path: str) -> None:
    """Create a default configuration file template.
    
    Args:
        output_path: Path where to create the config file
        
    Raises:
        ConfigValidationError: If file cannot be created
    """
    default_config = {
        "debug": False,
        "verbose": False,
        
        "logging": {
            "level": "INFO",
            "format": "text",
            "sinks": ["auto"],
            "enable_trace_id": True,
        },
        
        "service": {
            "service_mode": False,
            "health_check_enabled": True,
            "health_check_port": 8080,
            "metrics_enabled": True,
            "metrics_port": 9090,
        }
    }
    
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            toml.dump(default_config, f)
            
    except Exception as e:
        raise OSError(f"Cannot create config file {output_path}: {e}")


def merge_cli_args_to_config(
    base_config: AppConfig,
    log_level: Optional[str] = None,
    debug: Optional[bool] = None,
    verbose: Optional[bool] = None,
    service_mode: Optional[bool] = None,
    config_file: Optional[str] = None
) -> AppConfig:
    """Merge CLI arguments into configuration.
    
    Helper function for CLI integration to override configuration
    with command-line arguments.
    
    Args:
        base_config: Base configuration object
        log_level: Override log level
        debug: Override debug mode
        verbose: Override verbose mode
        service_mode: Override service mode
        config_file: Override config file path
        
    Returns:
        AppConfig: Updated configuration object
    """
    config_dict = base_config.model_dump()
    
    # Apply CLI overrides
    if log_level is not None:
        config_dict["logging"]["level"] = log_level.upper()
    
    if debug is not None:
        config_dict["app"]["debug"] = debug
        if debug:
            config_dict["logging"]["level"] = "DEBUG"
    
    if verbose is not None:
        config_dict["app"]["verbose"] = verbose
    
    if service_mode is not None:
        config_dict["service"]["service_mode"] = service_mode
    
    if config_file is not None:
        config_dict["config_file"] = config_file
    
    # Create new configuration with overrides
    return AppConfig(**config_dict) 