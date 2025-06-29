"""Configuration management CLI commands.

Provides commands for configuration debugging, validation, and management.
Implements the --dump-config quick win from Stage 3 acceptance criteria.
"""

import json
from typing import Optional

import typer
import yaml
from pydantic import ValidationError

from ...config.models import AppConfig
from ...config.loader import load_config
from ...config.detection import get_environment_info

# Create Typer app for config commands
config_app = typer.Typer(name="config", help="Configuration management commands")


@config_app.command(name="dump")
def dump_config(
    format: str = typer.Option(
        "yaml",
        "--format",
        help="Output format for configuration dump (yaml, json, env)"
    ),
    include_defaults: bool = typer.Option(
        False,
        "--include-defaults",
        help="Include default values in output"
    ),
    include_env_info: bool = typer.Option(
        False,
        "--include-env-info", 
        help="Include environment detection information"
    ),
    config_file: Optional[str] = typer.Option(
        None,
        "--config-file",
        help="Configuration file to load"
    )
):
    """Dump resolved configuration in specified format.
    
    This is the primary quick win indicator for Stage 3.
    Shows hierarchical configuration resolution: CLI > env > file > defaults.
    
    Examples:
        sboxctl config dump
        sboxctl config dump --format json
        sboxctl config dump --include-env-info
        SBOXMGR__LOGGING__LEVEL=DEBUG sboxctl config dump
    """
    try:
        # Load configuration with optional config file
        if config_file:
            config = load_config(config_file_path=config_file)
        else:
            config = AppConfig()
        
        # Prepare output data
        if include_defaults:
            config_data = config.model_dump(exclude_unset=False, exclude_none=False)
        else:
            config_data = config.model_dump(exclude_unset=True, exclude_none=True)
        
        # Add environment information if requested
        if include_env_info:
            config_data["_environment_info"] = get_environment_info()
        
        # Add metadata
        config_data["_metadata"] = {
            "config_file": config.config_file,
            "service_mode": config.service.service_mode,
            "container_mode": config.container_mode,
            "format_version": "1.0"
        }
        
        # Output in requested format
        if format == "yaml":
            yaml_output = yaml.dump(
                config_data,
                default_flow_style=False,
                sort_keys=True,
                indent=2
            )
            typer.echo(yaml_output)
        
        elif format == "json":
            json_output = json.dumps(
                config_data,
                indent=2,
                sort_keys=True,
                default=str
            )
            typer.echo(json_output)
        
        elif format == "env":
            # Output as environment variables
            _output_env_format(config_data, prefix="SBOXMGR")
        
        else:
            typer.echo(f"❌ Unsupported format: '{format}'", err=True)
            typer.echo("Supported formats: yaml, json, env", err=True)
            raise typer.Exit(1)
    
    except typer.Exit:
        # Re-raise typer.Exit without modification
        raise
    
    except ValidationError as e:
        typer.echo("❌ Configuration validation error:", err=True)
        for error in e.errors():
            field = " -> ".join(str(x) for x in error["loc"])
            typer.echo(f"  {field}: {error['msg']}", err=True)
        raise typer.Exit(1)
    
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {e}", err=True)
        raise typer.Exit(1)


@config_app.command(name="validate")
def validate_config(
    config_file: str = typer.Argument(..., help="Configuration file to validate")
):
    """Validate configuration file syntax and values.
    
    Checks configuration file for:
    - Valid TOML/YAML syntax
    - Schema compliance
    - Value validation
    - Environment variable resolution
    """
    try:
        config = load_config(config_file_path=config_file)
        typer.echo(f"✅ Configuration file '{config_file}' is valid")
        
        # Show key configuration values
        typer.echo("\nKey settings:")
        typer.echo(f"  Service mode: {config.service.service_mode}")
        typer.echo(f"  Log level: {config.logging.level}")
        typer.echo(f"  Log format: {config.logging.format}")
        typer.echo(f"  Log sinks: {', '.join(config.logging.sinks)}")
        
    except ValidationError as e:
        typer.echo("❌ Configuration validation failed:", err=True)
        for error in e.errors():
            field = " -> ".join(str(x) for x in error["loc"])
            typer.echo(f"  {field}: {error['msg']}", err=True)
        raise typer.Exit(1)
    
    except Exception as e:
        typer.echo(f"❌ Error validating configuration: {e}", err=True)
        raise typer.Exit(1)


@config_app.command(name="schema")
def generate_schema(
    output: Optional[str] = typer.Option(
        None,
        "--output",
        help="Output file for JSON schema (default: stdout)"
    )
):
    """Generate JSON schema for configuration validation.
    
    Useful for:
    - IDE autocompletion
    - Configuration file validation
    - Documentation generation
    """
    try:
        config = AppConfig()
        schema = config.model_json_schema()
        
        schema_json = json.dumps(schema, indent=2, sort_keys=True)
        
        if output:
            with open(output, 'w') as f:
                f.write(schema_json)
            typer.echo(f"✅ JSON schema written to {output}")
        else:
            typer.echo(schema_json)
    
    except Exception as e:
        typer.echo(f"❌ Error generating schema: {e}", err=True)
        raise typer.Exit(1)


@config_app.command(name="env-info")
def environment_info():
    """Show environment detection information.
    
    Displays detailed information about:
    - Service mode detection
    - Container environment
    - Systemd availability
    - Development environment
    """
    try:
        env_info = get_environment_info()
        
        typer.echo("🔍 Environment Detection Results:")
        typer.echo()
        
        # Service mode detection
        service_mode = "✅ Enabled" if env_info["service_mode"] else "❌ Disabled"
        typer.echo(f"Service Mode: {service_mode}")
        
        # Container detection
        container = "✅ Detected" if env_info["container_environment"] else "❌ Not detected"
        typer.echo(f"Container Environment: {container}")
        
        # Systemd detection
        systemd = "✅ Available" if env_info["systemd_environment"] else "❌ Not available"
        typer.echo(f"Systemd Environment: {systemd}")
        
        # Development detection
        dev = "✅ Detected" if env_info["development_environment"] else "❌ Not detected"
        typer.echo(f"Development Environment: {dev}")
        
        typer.echo()
        typer.echo("📋 Environment Variables:")
        for key, value in env_info["environment_variables"].items():
            if value:
                typer.echo(f"  {key}: {value}")
        
        typer.echo()
        typer.echo("🔧 Process Information:")
        for key, value in env_info["process_info"].items():
            typer.echo(f"  {key}: {value}")
        
        typer.echo()
        typer.echo("📁 File Indicators:")
        for path, exists in env_info["file_indicators"].items():
            status = "✅ Exists" if exists else "❌ Missing"
            typer.echo(f"  {path}: {status}")
    
    except Exception as e:
        typer.echo(f"❌ Error getting environment info: {e}", err=True)
        raise typer.Exit(1)


def _output_env_format(data: dict, prefix: str = "", parent_key: str = "") -> None:
    """Output configuration in environment variable format.
    
    Converts nested configuration to SBOXMGR__SECTION__KEY format.
    
    Args:
        data: Configuration dictionary to convert
        prefix: Environment variable prefix
        parent_key: Parent key for nested structures
    """
    for key, value in data.items():
        if key.startswith("_"):  # Skip metadata
            continue
            
        env_key = f"{prefix}__{key.upper()}" if prefix else key.upper()
        
        if isinstance(value, dict):
            _output_env_format(value, env_key, key)
        elif isinstance(value, list):
            # Convert lists to comma-separated strings
            env_value = ",".join(str(v) for v in value)
            typer.echo(f"{env_key}={env_value}")
        else:
            typer.echo(f"{env_key}={value}")


# For backward compatibility
config_group = config_app 