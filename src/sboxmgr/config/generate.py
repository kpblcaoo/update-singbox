"""Configuration generation and validation.

This module handles the generation of sing-box configuration files from
templates and server lists. It includes functions for merging templates with
outbound configurations, validating the resulting configuration using internal
Pydantic schemas, and writing configurations to disk with backup support.
"""
import os
import json
from logging import info, error
import tempfile
from typing import List
import copy

from ..events import emit_event, EventType, EventPriority
from .config_validator import validate_temp_config_json
from .validation import ConfigValidationError

def generate_config(outbounds, template_file, config_file, backup_file, excluded_ips):
    """Generate sing-box configuration from template."""
    if not os.path.exists(template_file):
        error(f"Template file not found: {template_file}")
        raise FileNotFoundError(f"Template file not found: {template_file}")

    with open(template_file) as f:
        template = json.load(f)  # Load as JSON to manipulate

    # Prepare outbound tags for urltest
    outbound_tags = [outbound["tag"] for outbound in outbounds] if outbounds else []

    # Update the urltest's outbounds
    for outbound in template["outbounds"]:
        if outbound.get("type") == "urltest" and outbound.get("tag") == "auto":
            outbound["outbounds"] = outbound_tags
            break

    # Insert provider outbounds after urltest but before direct
    urltest_idx = next(
        (i for i, o in enumerate(template["outbounds"]) if o.get("tag") == "auto"),
        0
    )
    template["outbounds"] = (
        template["outbounds"][:urltest_idx + 1] +
        outbounds +
        template["outbounds"][urltest_idx + 1:]
    )

    # Ensure excluded_ips are in CIDR format
    excluded_ips_cidr = [f"{ip}/32" for ip in excluded_ips]

    # Debug log for excluded_ips
    info(f"Excluded IPs: {excluded_ips_cidr}")

    # Replace $excluded_servers with actual IPs in CIDR format
    for rule in template["route"]["rules"]:
        if rule.get("ip_cidr") == "$excluded_servers":
            rule["ip_cidr"] = excluded_ips_cidr

    # Write the temporary configuration using tempfile
    config = json.dumps(template, indent=2)
    
    # Ensure config_file directory exists
    config_dir = os.path.dirname(config_file)
    if not os.path.isdir(config_dir):
        error(f"Config directory does not exist: {config_dir}. "
              f"Set SBOXMGR_CONFIG_FILE to a writable path if your sing-box is installed elsewhere.")
        raise FileNotFoundError(f"Config directory does not exist: {config_dir}")

    if os.path.exists(config_file):
        with open(config_file, "r") as current_config_file:
            current_config = current_config_file.read()
            if current_config.strip() == config.strip():
                info("Configuration has not changed. Skipping update.")
                return False

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
        temp_config_file = tmp.name
        tmp.write(config)
    info(f"Temporary configuration written to {temp_config_file}")

    try:
        # Comprehensive validation - check JSON syntax and sing-box semantics
        validate_temp_config_json(config)
        info("Temporary configuration validated successfully")
    except (ValueError, ConfigValidationError) as e:
        error(f"Temporary configuration is invalid: {e}")
        os.unlink(temp_config_file)
        raise

    if os.path.exists(config_file):
        os.rename(config_file, backup_file)
        info(f"Created backup: {backup_file}")

    os.rename(temp_config_file, config_file)
    info(f"Configuration updated with {len(outbounds)} outbounds")
    return True

def generate_temp_config(template_data: dict, servers: List[dict], user_routes: List[dict] = None) -> dict:
    """Generate temporary configuration from template and servers.
    
    Args:
        template_data: Configuration template data
        servers: List of server configurations
        user_routes: Optional user-defined routes
        
    Returns:
        Generated configuration dictionary
        
    Raises:
        ValueError: If template is invalid or generation fails
    """
    # Emit config generation start event
    emit_event(
        EventType.CONFIG_GENERATED,
        {
            "template_keys": list(template_data.keys()) if isinstance(template_data, dict) else [],
            "server_count": len(servers),
            "user_routes_count": len(user_routes) if user_routes else 0,
            "status": "started"
        },
        source="config.generate",
        priority=EventPriority.NORMAL
    )
    
    try:
        if user_routes is None:
            user_routes = []
        
        # Validate template structure
        if not isinstance(template_data, dict):
            raise ValueError("Template data must be a dictionary")
        
        if "outbounds" not in template_data:
            raise ValueError("Template must contain 'outbounds' key")
        
        # Start with template copy
        config = copy.deepcopy(template_data)
        
        # Process servers into outbounds
        outbounds = []
        
        # Add server outbounds
        for i, server in enumerate(servers):
            if not isinstance(server, dict):
                continue
                
            # Create outbound configuration
            outbound = {
                "tag": server.get("tag", f"proxy-{i+1}"),
                "type": server.get("type", "shadowsocks"),
                **server
            }
            
            # Remove redundant fields and normalize port field
            outbound.pop("name", None)
            
            # Convert server_port to port if needed
            if "server_port" in outbound and "port" not in outbound:
                outbound["port"] = outbound.pop("server_port")
            elif "server_port" in outbound:
                # If both exist, remove server_port and keep port
                outbound.pop("server_port", None)
            
            outbounds.append(outbound)
        
        # Add user routes if provided
        if user_routes:
            for route in user_routes:
                if isinstance(route, dict) and "tag" in route:
                    outbounds.append(route)
        
        # Update config with generated outbounds
        config["outbounds"] = outbounds
        
        # Emit successful generation event
        emit_event(
            EventType.CONFIG_GENERATED,
            {
                "outbound_count": len(outbounds),
                "config_size": len(str(config)),
                "status": "completed"
            },
            source="config.generate",
            priority=EventPriority.NORMAL
        )
        
        return config
        
    except Exception as e:
        # Emit error event
        emit_event(
            EventType.ERROR_OCCURRED,
            {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "component": "config.generate"
            },
            source="config.generate",
            priority=EventPriority.HIGH
        )
        raise

def validate_temp_config_dict(config_data: dict) -> None:
    """Validate temporary configuration dictionary using basic validation.
    
    Args:
        config_data: Configuration dictionary to validate
        
    Raises:
        ValueError: If configuration is invalid
    """
    # Emit validation start event
    emit_event(
        EventType.CONFIG_VALIDATED,
        {
            "config_keys": list(config_data.keys()),
            "status": "started",
            "validation_type": "basic"
        },
        source="config.validate",
        priority=EventPriority.NORMAL
    )
    
    try:
        # Basic validation - check required fields
        if not isinstance(config_data, dict):
            raise ValueError("Configuration must be a dictionary")
        
        if "outbounds" not in config_data:
            raise ValueError("Configuration must contain 'outbounds' key")
        
        if not isinstance(config_data["outbounds"], list):
            raise ValueError("'outbounds' must be a list")
        
        # Emit successful validation event
        emit_event(
            EventType.CONFIG_VALIDATED,
            {
                "status": "passed",
                "validation_type": "basic"
            },
            source="config.validate",
            priority=EventPriority.NORMAL
        )
        
    except Exception as e:
        # Emit error event
        emit_event(
            EventType.ERROR_OCCURRED,
            {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "component": "config.validate"
            },
            source="config.validate",
            priority=EventPriority.HIGH
        )
        raise

# validate_config_file function is now imported from validation.internal module