"""Configuration validator for sing-box specific validation.

This module provides semantic validation for sing-box configuration files,
ensuring that generated configurations meet sing-box requirements and
preventing runtime errors from invalid configurations.
"""

import json
from typing import Dict, Any, List, Optional
from .validation import ConfigValidationError


def validate_temp_config_json(config_json: str) -> None:
    """Validate temporary configuration JSON string using semantic validation.
    
    Performs comprehensive validation of sing-box configuration including:
    - JSON syntax validation
    - Required field validation
    - Sing-box specific structure validation
    - Outbound configuration validation
    - Routing rule validation
    
    Args:
        config_json: JSON string containing sing-box configuration
        
    Raises:
        ConfigValidationError: If configuration is semantically invalid
        ValueError: If JSON syntax is invalid
    """
    try:
        # First, validate JSON syntax
        config_data = json.loads(config_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON syntax: {e}")
    
    # Validate configuration structure
    validate_singbox_config_structure(config_data)


def validate_singbox_config_structure(config_data: Dict[str, Any]) -> None:
    """Validate sing-box configuration structure and semantics.
    
    Args:
        config_data: Configuration dictionary to validate
        
    Raises:
        ConfigValidationError: If configuration structure is invalid
    """
    if not isinstance(config_data, dict):
        raise ConfigValidationError("Configuration must be a dictionary")
    
    # Check required top-level fields
    required_fields = ["outbounds"]
    for field in required_fields:
        if field not in config_data:
            raise ConfigValidationError(f"Configuration must contain '{field}' key")
    
    # Validate outbounds
    outbounds = config_data.get("outbounds", [])
    if not isinstance(outbounds, list):
        raise ConfigValidationError("'outbounds' must be a list")
    
    if not outbounds:
        raise ConfigValidationError("Configuration must contain at least one outbound")
    
    # Validate each outbound
    for i, outbound in enumerate(outbounds):
        validate_outbound_config(outbound, i)
    
    # Validate optional fields if present
    if "inbounds" in config_data:
        inbounds = config_data["inbounds"]
        if not isinstance(inbounds, list):
            raise ConfigValidationError("'inbounds' must be a list")
        
        for i, inbound in enumerate(inbounds):
            validate_inbound_config(inbound, i)
    
    if "route" in config_data:
        validate_route_config(config_data["route"])


def validate_outbound_config(outbound: Dict[str, Any], index: int) -> None:
    """Validate individual outbound configuration.
    
    Args:
        outbound: Outbound configuration dictionary
        index: Index of outbound in list (for error messages)
        
    Raises:
        ConfigValidationError: If outbound configuration is invalid
    """
    if not isinstance(outbound, dict):
        raise ConfigValidationError(f"Outbound {index} must be a dictionary")
    
    # Check required fields
    required_fields = ["type"]
    for field in required_fields:
        if field not in outbound:
            raise ConfigValidationError(f"Outbound {index} must contain '{field}' field")
    
    # Validate outbound type
    outbound_type = outbound["type"]
    if not isinstance(outbound_type, str):
        raise ConfigValidationError(f"Outbound {index} 'type' must be a string")
    
    # Validate protocol-specific fields
    validate_protocol_specific_fields(outbound, index)


def validate_protocol_specific_fields(outbound: Dict[str, Any], index: int) -> None:
    """Validate protocol-specific fields for outbound.
    
    Args:
        outbound: Outbound configuration dictionary
        index: Index of outbound in list
        
    Raises:
        ConfigValidationError: If protocol-specific fields are invalid
    """
    outbound_type = outbound["type"]
    
    # Common fields for most protocols
    if "server" in outbound:
        if not isinstance(outbound["server"], str):
            raise ConfigValidationError(f"Outbound {index} 'server' must be a string")
    
    if "server_port" in outbound:
        port = outbound["server_port"]
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise ConfigValidationError(f"Outbound {index} 'server_port' must be an integer between 1-65535")
    
    # Protocol-specific validation
    if outbound_type == "shadowsocks":
        validate_shadowsocks_fields(outbound, index)
    elif outbound_type == "vmess":
        validate_vmess_fields(outbound, index)
    elif outbound_type == "trojan":
        validate_trojan_fields(outbound, index)
    elif outbound_type == "wireguard":
        validate_wireguard_fields(outbound, index)
    elif outbound_type == "hysteria2":
        validate_hysteria2_fields(outbound, index)
    elif outbound_type == "tuic":
        validate_tuic_fields(outbound, index)
    elif outbound_type in ["direct", "block", "dns-out"]:
        # Special outbounds don't need additional validation
        pass
    else:
        # Unknown protocol type - warn but don't fail
        pass


def validate_shadowsocks_fields(outbound: Dict[str, Any], index: int) -> None:
    """Validate Shadowsocks specific fields.
    
    Args:
        outbound: Outbound configuration dictionary
        index: Index of outbound in list
        
    Raises:
        ConfigValidationError: If Shadowsocks fields are invalid
    """
    required_fields = ["method", "password"]
    for field in required_fields:
        if field not in outbound:
            raise ConfigValidationError(f"Shadowsocks outbound {index} must contain '{field}' field")
        if not isinstance(outbound[field], str):
            raise ConfigValidationError(f"Shadowsocks outbound {index} '{field}' must be a string")


def validate_vmess_fields(outbound: Dict[str, Any], index: int) -> None:
    """Validate VMess specific fields.
    
    Args:
        outbound: Outbound configuration dictionary
        index: Index of outbound in list
        
    Raises:
        ConfigValidationError: If VMess fields are invalid
    """
    if "uuid" not in outbound:
        raise ConfigValidationError(f"VMess outbound {index} must contain 'uuid' field")
    if not isinstance(outbound["uuid"], str):
        raise ConfigValidationError(f"VMess outbound {index} 'uuid' must be a string")


def validate_trojan_fields(outbound: Dict[str, Any], index: int) -> None:
    """Validate Trojan specific fields.
    
    Args:
        outbound: Outbound configuration dictionary
        index: Index of outbound in list
        
    Raises:
        ConfigValidationError: If Trojan fields are invalid
    """
    if "password" not in outbound:
        raise ConfigValidationError(f"Trojan outbound {index} must contain 'password' field")
    if not isinstance(outbound["password"], str):
        raise ConfigValidationError(f"Trojan outbound {index} 'password' must be a string")


def validate_wireguard_fields(outbound: Dict[str, Any], index: int) -> None:
    """Validate WireGuard specific fields.
    
    Args:
        outbound: Outbound configuration dictionary
        index: Index of outbound in list
        
    Raises:
        ConfigValidationError: If WireGuard fields are invalid
    """
    required_fields = ["private_key", "peer_public_key", "local_address"]
    for field in required_fields:
        if field not in outbound:
            raise ConfigValidationError(f"WireGuard outbound {index} must contain '{field}' field")


def validate_hysteria2_fields(outbound: Dict[str, Any], index: int) -> None:
    """Validate Hysteria2 specific fields.
    
    Args:
        outbound: Outbound configuration dictionary
        index: Index of outbound in list
        
    Raises:
        ConfigValidationError: If Hysteria2 fields are invalid
    """
    if "password" not in outbound:
        raise ConfigValidationError(f"Hysteria2 outbound {index} must contain 'password' field")
    if not isinstance(outbound["password"], str):
        raise ConfigValidationError(f"Hysteria2 outbound {index} 'password' must be a string")


def validate_tuic_fields(outbound: Dict[str, Any], index: int) -> None:
    """Validate TUIC specific fields.
    
    Args:
        outbound: Outbound configuration dictionary
        index: Index of outbound in list
        
    Raises:
        ConfigValidationError: If TUIC fields are invalid
    """
    required_fields = ["uuid", "password"]
    for field in required_fields:
        if field not in outbound:
            raise ConfigValidationError(f"TUIC outbound {index} must contain '{field}' field")
        if not isinstance(outbound[field], str):
            raise ConfigValidationError(f"TUIC outbound {index} '{field}' must be a string")


def validate_inbound_config(inbound: Dict[str, Any], index: int) -> None:
    """Validate individual inbound configuration.
    
    Args:
        inbound: Inbound configuration dictionary
        index: Index of inbound in list
        
    Raises:
        ConfigValidationError: If inbound configuration is invalid
    """
    if not isinstance(inbound, dict):
        raise ConfigValidationError(f"Inbound {index} must be a dictionary")
    
    if "type" not in inbound:
        raise ConfigValidationError(f"Inbound {index} must contain 'type' field")
    
    inbound_type = inbound["type"]
    if not isinstance(inbound_type, str):
        raise ConfigValidationError(f"Inbound {index} 'type' must be a string")


def validate_route_config(route: Dict[str, Any]) -> None:
    """Validate routing configuration.
    
    Args:
        route: Route configuration dictionary
        
    Raises:
        ConfigValidationError: If route configuration is invalid
    """
    if not isinstance(route, dict):
        raise ConfigValidationError("Route configuration must be a dictionary")
    
    # Validate rules if present
    if "rules" in route:
        rules = route["rules"]
        if not isinstance(rules, list):
            raise ConfigValidationError("Route 'rules' must be a list")
        
        for i, rule in enumerate(rules):
            validate_route_rule(rule, i)


def validate_route_rule(rule: Dict[str, Any], index: int) -> None:
    """Validate individual route rule.
    
    Args:
        rule: Route rule dictionary
        index: Index of rule in list
        
    Raises:
        ConfigValidationError: If route rule is invalid
    """
    if not isinstance(rule, dict):
        raise ConfigValidationError(f"Route rule {index} must be a dictionary")
    
    # Check for required fields based on rule type
    if "outbound" not in rule:
        raise ConfigValidationError(f"Route rule {index} must contain 'outbound' field")
    
    if not isinstance(rule["outbound"], str):
        raise ConfigValidationError(f"Route rule {index} 'outbound' must be a string") 