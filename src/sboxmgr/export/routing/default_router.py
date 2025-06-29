"""Default routing plugin implementation.

This module provides the DefaultRouter class which implements basic routing
rule generation for sing-box configurations. It creates simple routing rules
that direct traffic through the configured proxy servers with basic fallback
handling.
"""
from .base_router import BaseRoutingPlugin
from typing import List, Dict, Any, Union

class DefaultRouter(BaseRoutingPlugin):
    """Default implementation of routing rule generation.
    
    This router generates basic routing rules suitable for sing-box
    configurations. It creates rules that route traffic through proxy servers
    with simple fallback to direct connection when needed.
    """
    
    def generate_routes(self, servers: List[Any], exclusions: List[str], user_routes: List[Dict], context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate default routing rules for sing-box configuration.
        
        Creates basic routing rules that direct traffic through proxy servers
        with fallback handling. Supports user-defined routes and exclusions.
        
        Args:
            servers: List of parsed server configurations.
            exclusions: List of server patterns to exclude from routing.
            user_routes: User-defined routing rules to include.
            context: Additional context including debug level and mode.
            
        Returns:
            List of routing rule dictionaries for sing-box configuration.
        """
        # Логируем только при debug_level >= 2
        debug_level = getattr(context, 'debug_level', 0) if context else 0
        if debug_level >= 2:
            print(f"[DefaultRouter] context={context}, exclusions={exclusions}, user_routes={user_routes}")
        
        rules: List[Dict[str, Any]] = []
        
        # 1. DNS hijacking rule (высокий приоритет)
        rules.append({
            "protocol": "dns",
            "action": "hijack-dns"
        })
        
        # 2. Private IP addresses should go direct
        rules.append({
            "ip_is_private": True,
            "outbound": "direct"
        })
        
        # 3. Process exclusions - excluded IPs should go direct
        if exclusions:
            # Convert exclusions to CIDR if they are IP addresses
            excluded_cidrs: List[str] = []
            excluded_domains: List[str] = []
            
            for exclusion in exclusions:
                # Try to determine if it's an IP or domain
                if self._is_ip_address(exclusion):
                    excluded_cidrs.append(f"{exclusion}/32")
                else:
                    excluded_domains.append(exclusion)
            
            # Add rules for excluded IPs
            if excluded_cidrs:
                rules.append({
                    "ip_cidr": excluded_cidrs,
                    "outbound": "direct"
                })
            
            # Add rules for excluded domains
            if excluded_domains:
                rules.append({
                    "domain": excluded_domains,
                    "outbound": "direct"
                })
        
        # 4. Add user-defined routes (as-is, user knows what they're doing)
        if user_routes:
            for route in user_routes:
                if isinstance(route, dict):
                    rules.append(route)
        
        # 5. Default fallback - if we have servers, route to first one
        # Otherwise route to direct
        if servers and len(servers) > 0:
            first_server = servers[0]
            server_tag = getattr(first_server, 'meta', {}).get('tag') or getattr(first_server, 'tag', None)
            if not server_tag:
                # Generate tag from server properties
                server_type = getattr(first_server, 'type', 'proxy')
                server_address = getattr(first_server, 'address', 'unknown')
                server_tag = f"{server_type}-{server_address}"
            
            # Add default proxy rule - route all other traffic through first server
            rules.append({
                "outbound": server_tag
            })
        else:
            # No servers available - route everything to direct
            rules.append({
                "outbound": "direct"
            })
        
        if debug_level >= 1:
            print(f"[DefaultRouter] Generated {len(rules)} routing rules")
        
        return rules
    
    def _is_ip_address(self, address: str) -> bool:
        """Check if string is an IP address.
        
        Args:
            address: String to check.
            
        Returns:
            True if it looks like an IP address.
        """
        try:
            import ipaddress
            ipaddress.ip_address(address)
            return True
        except ValueError:
            return False 