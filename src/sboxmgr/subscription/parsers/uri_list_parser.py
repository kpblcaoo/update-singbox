"""URI list parser for subscription data.

This module provides parsing functionality for URI-based subscription formats
that contain multiple server URIs in a single file. It supports various
protocols including Shadowsocks, VLess, VMess, and Trojan with proper
error handling and validation.
"""

import base64
import binascii
import json
import logging
import re
from typing import List
from urllib.parse import urlparse, parse_qs, unquote
from ..models import ParsedServer
from ..base_parser import BaseParser
from sboxmgr.utils.env import get_debug_level
from ..registry import register

logger = logging.getLogger(__name__)

@register("parser_uri_list")
class URIListParser(BaseParser):
    """Parser for URI list format subscription data.
    
    This parser handles subscription data consisting of newline-separated
    proxy URIs. Each URI represents a single server configuration in a
    standardized URI format (vless://, vmess://, trojan://, ss://, etc.).
    """
    
    def parse(self, raw: bytes) -> List[ParsedServer]:
        """Parse URI list subscription data into ParsedServer objects.
        
        Args:
            raw: Raw bytes containing newline-separated proxy URIs.
            
        Returns:
            List[ParsedServer]: List of parsed server configurations.
            
        Raises:
            ValueError: If URI format is invalid or unsupported.
            UnicodeDecodeError: If raw data cannot be decoded as UTF-8.
        """
        lines = raw.decode("utf-8").splitlines()
        servers = []
        debug_level = get_debug_level()
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('ss://'):
                ss = self._parse_ss(line)
                if ss and ss.address != "invalid":
                    servers.append(ss)
                else:
                    if debug_level > 0:
                        logger.warning(f"Failed to parse ss:// line: {line}")
            elif line.startswith('vless://'):
                servers.append(self._parse_vless(line))
            elif line.startswith('vmess://'):
                servers.append(self._parse_vmess(line))
            elif line.startswith('trojan://'):
                trojan = self._parse_trojan(line)
                if trojan:
                    servers.append(trojan)
                else:
                    if debug_level > 0:
                        logger.warning(f"Failed to parse trojan:// line: {line}")
            else:
                if debug_level > 0:
                    logger.warning(f"Ignored line in uri list: {line}")
                servers.append(ParsedServer(type="unknown", address=line, port=0))
        return servers

    def _parse_ss(self, line: str) -> ParsedServer:
        """Parse shadowsocks URI into ParsedServer object.
        
        Supports both base64-encoded and plain format:
        - ss://base64(method:password@host:port)  # pragma: allowlist secret
        - ss://method:password@host:port  # pragma: allowlist secret
        
        Args:
            line: Shadowsocks URI string
            
        Returns:
            ParsedServer object with parsed configuration
        """
        parsed = urlparse(line)
        uri = parsed.netloc + parsed.path
        tag = unquote(parsed.fragment) if parsed.fragment else ""
        query = parse_qs(parsed.query)
        
        try:
            method_pass, host_port = self._extract_ss_components(uri, line)
            if not method_pass or not host_port:
                return self._create_invalid_ss_server("failed to extract components")
                
            method, password = self._parse_ss_credentials(method_pass, line)
            if not method or not password:
                return self._create_invalid_ss_server("failed to parse credentials")
                
            host, port, endpoint_error = self._parse_ss_endpoint(host_port, line)
            if not host or port == 0:
                return self._create_invalid_ss_server(endpoint_error or "failed to parse endpoint")
                
            return self._create_ss_server(method, password, host, port, tag, query)
            
        except (ValueError, AttributeError, IndexError):
            # Fallback to regex parsing if structured parsing fails
            return self._parse_ss_with_regex(uri, tag, query, line)

    def _extract_ss_components(self, uri: str, line: str) -> tuple[str, str]:
        """Extract method:password and host:port components from SS URI."""
        debug_level = get_debug_level()
        
        # Try base64 decoding first
        if '@' in uri:
            b64, after = uri.split('@', 1)
            try:
                decoded = base64.urlsafe_b64decode(b64 + '=' * (-len(b64) % 4)).decode('utf-8')
            except (binascii.Error, UnicodeDecodeError):
                decoded = b64  # fallback: not base64
            if '@' in decoded:
                parts = decoded.split('@', 1)
                return parts[0], parts[1]
            else:
                if debug_level > 0:
                    logger.warning(f"ss:// no host in line: {line}")
                return "", ""
        else:
            # Whole string is base64 or plain
            try:
                decoded = base64.urlsafe_b64decode(uri + '=' * (-len(uri) % 4)).decode('utf-8')
            except (binascii.Error, UnicodeDecodeError):
                decoded = uri  # fallback: not base64
            
            if '@' in decoded:
                parts = decoded.split('@', 1)
                return parts[0], parts[1]
            else:
                if debug_level > 0:
                    logger.warning(f"ss:// no host in line: {line}")
                return "", ""

    def _parse_ss_credentials(self, method_pass: str, line: str) -> tuple[str, str]:
        """Parse method and password from method:password string.
        
        Args:
            method_pass: String containing method:password.
            line: Original line for error reporting.
            
        Returns:
            Tuple of (method, password). Empty strings if parsing fails.
        """
        debug_level = get_debug_level()
        
        if ':' not in method_pass:
            if debug_level > 0:
                logger.warning(f"ss:// parse failed (no colon in method:pass): {line}")
            return "", ""
        
        parts = method_pass.split(':', 1)
        return parts[0], parts[1]

    def _parse_ss_endpoint(self, host_port: str, line: str) -> tuple[str, int, str]:
        """Parse host and port from host:port string.
        
        Args:
            host_port: String containing host:port.
            line: Original line for error reporting.
            
        Returns:
            Tuple of (host, port, error_message). If parsing fails, 
            host/port will be empty/0 and error_message will describe the issue.
        """
        debug_level = get_debug_level()
        
        if ':' not in host_port:
            if debug_level > 0:
                logger.warning(f"ss:// parse failed (no port specified): {line}")
            return "", 0, "no port specified"
        
        parts = host_port.split(':', 1)
        host, port_str = parts[0], parts[1]
        
        try:
            port = int(port_str)
            return host, port, ""
        except ValueError:
            if debug_level > 0:
                logger.warning(f"ss:// invalid port: {port_str} in line: {line}")
            return "", 0, "invalid port"

    def _create_ss_server(self, method: str, password: str, host: str, port: int, tag: str, query: dict) -> ParsedServer:
        """Create ParsedServer object for shadowsocks configuration."""
        meta = {"password": password}  # pragma: allowlist secret
        if tag:
            meta["tag"] = tag
        for k, v in query.items():
            meta[k] = v[0] if v else ""
        
        return ParsedServer(
            type="ss",
            address=host,
            port=port,
            security=method,
            meta=meta
        )

    def _create_invalid_ss_server(self, error: str) -> ParsedServer:
        """Create invalid ParsedServer for failed SS parsing."""
        return ParsedServer(type="ss", address="invalid", port=0, meta={"error": error})

    def _parse_ss_with_regex(self, uri: str, tag: str, query: dict, line: str) -> ParsedServer:
        """Fallback SS parsing using regex pattern matching."""
        debug_level = get_debug_level()
        
        match = re.match(r'(?P<method>[^:]+):(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)', uri)  # pragma: allowlist secret
        if match:
            meta = {"password": match.group('password')}  # pragma: allowlist secret
            if tag:
                meta["tag"] = tag
            for k, v in query.items():
                meta[k] = v[0] if v else ""
            return ParsedServer(
                type="ss",
                address=match.group('host'),
                port=int(match.group('port')),
                security=match.group('method'),
                meta=meta
            )
        
        if debug_level > 0:
            logger.warning(f"ss:// totally failed to parse: {line}")
        return self._create_invalid_ss_server("parse failed")

    def _parse_trojan(self, line: str) -> ParsedServer:
        # trojan://password@host:port?params#tag
        parsed = urlparse(line)
        host, port = parsed.hostname, parsed.port or 0
        password = parsed.username or ""
        params = parse_qs(parsed.query)
        tag = unquote(parsed.fragment) if parsed.fragment else ""
        meta = {"tag": tag} if tag else {}
        meta["password"] = password
        for k, v in params.items():
            meta[k] = v[0] if v else ""
        return ParsedServer(
            type="trojan",
            address=host or "",
            port=port,
            security=None,
            meta=meta
        )

    def _parse_vless(self, line: str) -> ParsedServer:
        # vless://uuid@host:port?params#label
        parsed = urlparse(line)
        host, port = parsed.hostname, parsed.port or 0
        uuid = parsed.username or ""
        params = parse_qs(parsed.query)
        label = unquote(parsed.fragment) if parsed.fragment else ""
        return ParsedServer(
            type="vless",
            address=host or "",
            port=port,
            security=params.get("security", [None])[0],
            meta={"uuid": uuid, "label": label, **{k: v[0] for k, v in params.items()}}  # pragma: allowlist secret
        )

    def _parse_vmess(self, line: str) -> ParsedServer:
        # vmess://base64(JSON)
        b64 = line[8:]
        try:
            decoded = base64.urlsafe_b64decode(b64 + '=' * (-len(b64) % 4)).decode('utf-8')
            data = json.loads(decoded)
            return ParsedServer(
                type="vmess",
                address=data.get("add", ""),
                port=int(data.get("port", 0)),
                security=data.get("security"),
                meta=data
            )
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError) as e:
            return ParsedServer(type="vmess", address="invalid", port=0, meta={"error": f"decode failed: {type(e).__name__}"}) 