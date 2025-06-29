"""Sing-box configuration exporter implementation.

This module provides comprehensive sing-box configuration export functionality
including server conversion, routing rule generation, and version compatibility
handling. It supports both modern and legacy sing-box syntax for maximum
compatibility across different sing-box versions.
"""
import json
import logging
from typing import List, Optional, Dict, Any, Callable
from ..models import ParsedServer, ClientProfile
from ..base_exporter import BaseExporter
from ..registry import register
from ...utils.version import should_use_legacy_outbounds

logger = logging.getLogger(__name__)

def kebab_to_snake(d):
    """Convert kebab-case keys to snake_case recursively in dictionaries.
    
    Transforms dictionary keys from kebab-case (hyphen-separated) to snake_case
    (underscore-separated) format. This is useful for normalizing configuration
    data between different naming conventions.
    
    Args:
        d: Dictionary, list, or other data structure to process.
        
    Returns:
        Processed data structure with kebab-case keys converted to snake_case.
        Non-dictionary types are returned unchanged.
    """
    if not isinstance(d, dict):
        return d
    return {k.replace('-', '_'): kebab_to_snake(v) for k, v in d.items()}

def generate_inbounds(profile: ClientProfile) -> list:
    """Генерирует секцию inbounds для sing-box config на основе ClientProfile.

    Args:
        profile (ClientProfile): Профиль клиента с описанием inbounds.

    Returns:
        list: Список inbounds для секции 'inbounds' в sing-box config.

    SEC:
        - По умолчанию bind только на localhost (127.0.0.1).
        - Порты по умолчанию безопасные, внешний bind только при явном подтверждении.
        - Валидация через pydantic.
    """
    inbounds = []
    for inbound in profile.inbounds:
        # pydantic уже валидирует SEC, но можно добавить дополнительные проверки
        inb = inbound.model_dump(exclude_unset=True)
        # Убираем None-поля для компактности
        inb = {k: v for k, v in inb.items() if v is not None}
        inbounds.append(inb)
    return inbounds


def _get_protocol_dispatcher() -> Dict[str, Callable]:
    """Возвращает словарь диспетчеров для специальных протоколов.
    
    Returns:
        Dict[str, Callable]: Маппинг протокол -> функция экспорта.
    """
    return {
        "wireguard": _export_wireguard,
        "hysteria2": _export_hysteria2,
        "tuic": _export_tuic,
        "shadowtls": _export_shadowtls,
        "anytls": _export_anytls,
        "tor": _export_tor,
        "ssh": _export_ssh,
    }


def _normalize_protocol_type(server_type: str) -> str:
    """Нормализует тип протокола для sing-box.
    
    Args:
        server_type (str): Исходный тип протокола.
        
    Returns:
        str: Нормализованный тип протокола.
    """
    if server_type == "ss":
        return "shadowsocks"
    return server_type


def _is_supported_protocol(protocol_type: str) -> bool:
    """Проверяет поддержку протокола.
    
    Args:
        protocol_type (str): Тип протокола.
        
    Returns:
        bool: True если протокол поддерживается.
    """
    supported_types = {
        "vless", "vmess", "trojan", "ss", "shadowsocks", 
        "wireguard", "hysteria2", "tuic", "shadowtls", 
        "anytls", "tor", "ssh"
    }
    return protocol_type in supported_types



def _create_base_outbound(server: ParsedServer, protocol_type: str) -> Dict[str, Any]:
    """Создаёт базовую структуру outbound.
    
    Args:
        server (ParsedServer): Сервер для экспорта.
        protocol_type (str): Нормализованный тип протокола.
        
    Returns:
        Dict[str, Any]: Базовая структура outbound.
    """
    return {
        "type": protocol_type,
        "server": server.address,
        "server_port": server.port,
    }


def _process_shadowsocks_config(outbound: Dict[str, Any], server: ParsedServer, meta: Dict[str, Any]) -> bool:
    """Обрабатывает конфигурацию Shadowsocks.
    
    Args:
        outbound (Dict[str, Any]): Outbound конфигурация для модификации.
        server (ParsedServer): Исходный сервер.
        meta (Dict[str, Any]): Метаданные сервера.
        
    Returns:
        bool: True если конфигурация валидна, False если нужно пропустить сервер.
    """
    method = meta.get("cipher") or meta.get("method") or server.security
    if not method:
        logger.warning(f"WARNING: shadowsocks outbound without method/cipher, skipping: {server.address}:{server.port}")
        return False
    outbound["method"] = method
    return True


def _process_transport_config(outbound: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Обрабатывает конфигурацию транспорта (ws, grpc, tcp, udp).
    
    Args:
        outbound (Dict[str, Any]): Outbound конфигурация для модификации.
        meta (Dict[str, Any]): Метаданные сервера для модификации.
    """
    network = meta.pop("network", None)
    if network in ("ws", "grpc"):
        outbound["transport"] = {"type": network}
        for k in list(meta.keys()):
            if k.startswith(network):
                outbound["transport"][k[len(network)+1:]] = meta.pop(k)
    elif network in ("tcp", "udp"):
        outbound["network"] = network


def _process_tls_config(outbound: Dict[str, Any], meta: Dict[str, Any], protocol_type: str) -> None:
    """Обрабатывает конфигурацию TLS/Reality/uTLS.
    
    Args:
        outbound (Dict[str, Any]): Outbound конфигурация для модификации.
        meta (Dict[str, Any]): Метаданные сервера для модификации.
        protocol_type (str): Тип протокола.
    """
    tls: Dict[str, Any] = {}
    
    # Базовая TLS конфигурация
    if meta.get("tls") or meta.get("security") == "tls":
        tls["enabled"] = True
        meta.pop("tls", None)
        meta.pop("security", None)
    
    # Server name
    if meta.get("servername"):
        tls["server_name"] = meta.pop("servername")
    
    # Reality конфигурация
    if meta.get("reality-opts"):
        reality = kebab_to_snake(meta.pop("reality-opts"))
        if "reality" not in tls:
            tls["reality"] = {}
        tls["reality"].update(reality)
    
    if meta.get("pbk"):
        if "reality" not in tls:
            tls["reality"] = {}
        tls["reality"]["public_key"] = meta.pop("pbk")
    
    if meta.get("short_id"):
        if "reality" not in tls:
            tls["reality"] = {}
        tls["reality"]["short_id"] = meta.pop("short_id")
    
    # uTLS конфигурация
    utls_fp = meta.pop("client-fingerprint", None) or meta.pop("fp", None)
    if utls_fp:
        if "utls" not in tls:
            tls["utls"] = {}
        tls["utls"]["fingerprint"] = utls_fp
        tls["utls"]["enabled"] = True
    
    # ALPN
    if meta.get("alpn"):
        tls["alpn"] = meta.pop("alpn")
    
    # Добавляем TLS конфигурацию только для поддерживающих протоколов
    if tls and protocol_type in {"vless", "vmess", "trojan"}:
        outbound["tls"] = tls


def _process_auth_and_flow_config(outbound: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Обрабатывает конфигурацию аутентификации и flow.
    
    Args:
        outbound (Dict[str, Any]): Outbound конфигурация для модификации.
        meta (Dict[str, Any]): Метаданные сервера для модификации.
    """
    if meta.get("uuid"):
        outbound["uuid"] = meta.pop("uuid")
    
    if meta.get("flow"):
        outbound["flow"] = meta.pop("flow")


def _process_tag_config(outbound: Dict[str, Any], server: ParsedServer, meta: Dict[str, Any]) -> None:
    """Обрабатывает конфигурацию тега outbound.
    
    Args:
        outbound (Dict[str, Any]): Outbound конфигурация для модификации.
        server (ParsedServer): Исходный сервер.
        meta (Dict[str, Any]): Метаданные сервера для модификации.
    """
    label = meta.pop("label", None)
    if label:
        outbound["tag"] = label
    elif meta.get("name"):
        outbound["tag"] = meta.pop("name")
    else:
        outbound["tag"] = server.address


def _process_additional_config(outbound: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Обрабатывает дополнительные параметры конфигурации.
    
    Args:
        outbound (Dict[str, Any]): Outbound конфигурация для модификации.
        meta (Dict[str, Any]): Метаданные сервера.
    """
    whitelist = {
        "password", "method", "multiplex", "packet_encoding", 
        "udp_over_tcp", "udp_relay_mode", "udp_fragment", "udp_timeout"
    }
    for k, v in meta.items():
        if k in whitelist:
            outbound[k] = v


def _process_standard_server(server: ParsedServer, protocol_type: str) -> Optional[Dict[str, Any]]:
    """Обрабатывает стандартный сервер (не специальный протокол).
    
    Args:
        server (ParsedServer): Сервер для обработки.
        protocol_type (str): Нормализованный тип протокола.
        
    Returns:
        Optional[Dict[str, Any]]: Outbound конфигурация или None если нужно пропустить.
    """
    outbound = _create_base_outbound(server, protocol_type)
    meta = dict(server.meta or {})
    
    # Обрабатываем Shadowsocks конфигурацию
    if protocol_type == "shadowsocks":
        if not _process_shadowsocks_config(outbound, server, meta):
            return None
    
    # Обрабатываем различные аспекты конфигурации
    _process_transport_config(outbound, meta)
    _process_tls_config(outbound, meta, protocol_type)
    _process_auth_and_flow_config(outbound, meta)
    _process_tag_config(outbound, server, meta)
    _process_additional_config(outbound, meta)
    
    return outbound


def _process_single_server(server: ParsedServer) -> Optional[Dict[str, Any]]:
    """Обрабатывает один сервер и возвращает outbound конфигурацию.
    
    Args:
        server (ParsedServer): Сервер для обработки.
        
    Returns:
        Optional[Dict[str, Any]]: Outbound конфигурация или None если нужно пропустить.
    """
    protocol_type = _normalize_protocol_type(server.type)
    
    # Проверяем поддержку протокола
    if not _is_supported_protocol(protocol_type):
        logger.warning(f"Unsupported outbound type: {server.type}, skipping {server.address}:{server.port}")
        return None
    
    # Обрабатываем специальные протоколы
    dispatcher = _get_protocol_dispatcher()
    if protocol_type in dispatcher:
        return dispatcher[protocol_type](server)  # Может вернуть None
    
    # Обрабатываем стандартные протоколы
    return _process_standard_server(server, protocol_type)


def _add_special_outbounds(outbounds: List[Dict[str, Any]], use_legacy: bool) -> None:
    """Добавляет специальные outbounds (direct, block, dns-out).
    
    Args:
        outbounds (List[Dict[str, Any]]): Список outbounds для модификации.
        use_legacy (bool): Использовать ли legacy режим.
    """
    tags = {o.get("tag") for o in outbounds}
    if "direct" not in tags:
        outbounds.append({"type": "direct", "tag": "direct"})
    if "block" not in tags:
        outbounds.append({"type": "block", "tag": "block"})
    if "dns-out" not in tags:
        outbounds.append({"type": "dns", "tag": "dns-out"})


def singbox_export(
    servers: List[ParsedServer],
    routes,
    client_profile: Optional[ClientProfile] = None,
    singbox_version: Optional[str] = None,
    skip_version_check: bool = False
) -> dict:
    """Export parsed servers to sing-box configuration format.
    
    Converts a list of parsed server configurations into a complete sing-box
    configuration with outbounds, routing rules, and optional inbound profiles.
    Supports version compatibility checks and legacy outbound generation.
    
    Args:
        servers: List of ParsedServer objects to export.
        routes: Routing rules configuration.
        client_profile: Optional client profile for inbound generation.
        singbox_version: Optional sing-box version for compatibility checks.
        skip_version_check: Whether to skip version compatibility validation.
        
    Returns:
        Dictionary containing complete sing-box configuration with outbounds,
        routing rules, and optional inbounds section.
        
    Note:
        Automatically adds special outbounds (direct, block, dns-out) based
        on version compatibility. Supports legacy mode for sing-box < 1.11.0.
    """
    outbounds = []
    
    # Определяем нужно ли использовать legacy outbounds
    use_legacy = False if skip_version_check else should_use_legacy_outbounds(singbox_version)
    
    if use_legacy and singbox_version:
        logger.warning(f"Using legacy outbounds for sing-box {singbox_version} compatibility")
    
    # Обрабатываем каждый сервер
    for server in servers:
        outbound = _process_single_server(server)
        if outbound:
            outbounds.append(outbound)
    
    # Добавляем специальные outbounds
    _add_special_outbounds(outbounds, use_legacy)
    
    # Формируем финальную конфигурацию
    config = {
        "outbounds": outbounds,
        "route": {"rules": routes}
    }
    
    if client_profile is not None:
        config["inbounds"] = generate_inbounds(client_profile)
    
    return config

def _export_wireguard(s: ParsedServer) -> dict:
    """Генерирует outbound-конфиг для WireGuard.

    Args:
        s (ParsedServer): Сервер типа wireguard.

    Returns:
        dict: Outbound-конфиг для sing-box или None (если не хватает обязательных полей).
    """
    required = [s.address, s.port, s.private_key, s.peer_public_key, s.local_address]
    if not all(required):
        logger.warning(f"Incomplete wireguard fields, skipping: {s.address}:{s.port}")
        return None
    out = {
        "type": "wireguard",
        "server": s.address,
        "server_port": s.port,
        "private_key": s.private_key,
        "peer_public_key": s.peer_public_key,
        "local_address": s.local_address,
    }
    if getattr(s, "pre_shared_key", None):
        out["pre_shared_key"] = s.pre_shared_key
    
    # Безопасная проверка meta на None
    meta = getattr(s, 'meta', {}) or {}
    if meta.get("mtu") is not None:
        out["mtu"] = meta["mtu"]
    if meta.get("keepalive") is not None:
        out["keepalive"] = meta["keepalive"]
    if s.tag:
        out["tag"] = s.tag
    return out

def _export_tuic(s: ParsedServer) -> dict:
    """Генерирует outbound-конфиг для TUIC.
    Args:
        s (ParsedServer): Сервер типа tuic.
    Returns:
        dict: Outbound-конфиг для sing-box или None (если не хватает обязательных полей).
    """
    required = [s.address, s.port, s.uuid, s.password]
    if not all(required):
        logger.warning(f"Incomplete tuic fields, skipping: {s.address}:{s.port}")
        return None
    out = {
        "type": "tuic",
        "server": s.address,
        "server_port": s.port,
        "uuid": s.uuid,
        "password": s.password,
    }
    if s.congestion_control:
        out["congestion_control"] = s.congestion_control
    if not s.alpn:
        out["alpn"] = s.alpn
    
    # Безопасная проверка meta на None
    meta = getattr(s, 'meta', {}) or {}
    if meta.get("udp_relay_mode") is not None:
        out["udp_relay_mode"] = meta["udp_relay_mode"]
    if s.tls:
        out["tls"] = s.tls
    if s.tag:
        out["tag"] = s.tag
    return out

def _export_shadowtls(s: ParsedServer) -> dict:
    """Генерирует outbound-конфиг для ShadowTLS.
    Args:
        s (ParsedServer): Сервер типа shadowtls.
    Returns:
        dict: Outbound-конфиг для sing-box или None (если не хватает обязательных полей).
    """
    required = [s.address, s.port, s.password, s.version]
    if not all(required):
        logger.warning(f"Incomplete shadowtls fields, skipping: {s.address}:{s.port}")
        return None
    out = {
        "type": "shadowtls",
        "server": s.address,
        "server_port": s.port,
        "password": s.password,
        "version": s.version,
    }
    if s.handshake:
        out["handshake"] = s.handshake
    if s.tls:
        out["tls"] = s.tls
    if s.tag:
        out["tag"] = s.tag
    return out

def _export_anytls(s: ParsedServer) -> dict:
    """Генерирует outbound-конфиг для AnyTLS.
    Args:
        s (ParsedServer): Сервер типа anytls.
    Returns:
        dict: Outbound-конфиг для sing-box или None (если не хватает обязательных полей).
    """
    required = [s.address, s.port, s.uuid]
    if not all(required):
        logger.warning(f"Incomplete anytls fields, skipping: {s.address}:{s.port}")
        return None
    out = {
        "type": "anytls",
        "server": s.address,
        "server_port": s.port,
        "uuid": s.uuid,
    }
    if s.tls:
        out["tls"] = s.tls
    if s.tag:
        out["tag"] = s.tag
    return out

def _export_tor(s: ParsedServer) -> dict:
    """Генерирует outbound-конфиг для Tor.
    Args:
        s (ParsedServer): Сервер типа tor.
    Returns:
        dict: Outbound-конфиг для sing-box или None (если не хватает обязательных полей).
    """
    required = [s.address, s.port]
    if not all(required):
        logger.warning(f"Incomplete tor fields, skipping: {s.address}:{s.port}")
        return None
    out = {
        "type": "tor",
        "server": s.address,
        "server_port": s.port,
    }
    if s.tag:
        out["tag"] = s.tag
    return out

def _export_ssh(s: ParsedServer) -> dict:
    """Генерирует outbound-конфиг для SSH.
    Args:
        s (ParsedServer): Сервер типа ssh.
    Returns:
        dict: Outbound-конфиг для sing-box или None (если не хватает обязательных полей).
    """
    required = [s.address, s.port, s.username]
    if not all(required):
        logger.warning(f"Incomplete ssh fields, skipping: {s.address}:{s.port}")
        return None
    out = {
        "type": "ssh",
        "server": s.address,
        "server_port": s.port,
        "username": s.username,
    }
    if s.password:
        out["password"] = s.password
    if s.private_key:
        out["private_key"] = s.private_key
    if s.tls:
        out["tls"] = s.tls
    if s.tag:
        out["tag"] = s.tag
    return out

def _export_hysteria2(server):
    required = [server.address, server.port, server.password]
    if not all(required):
        logger.warning(f"Incomplete hysteria2 fields, skipping: {server.address}:{server.port}")
        return None
    return {
        "type": "hysteria2",
        "server": server.address,
        "port": server.port,
        "password": server.password,
        "tag": getattr(server, "tag", server.address),
    }

@register("singbox")
class SingboxExporter(BaseExporter):
    """Sing-box format configuration exporter.
    
    Implements the BaseExporter interface for generating sing-box compatible
    JSON configurations from parsed server data. Handles protocol-specific
    outbound generation and version compatibility.
    """
    
    def export(self, servers: List[ParsedServer]) -> str:
        """Export servers to sing-box JSON configuration string.
        
        Args:
            servers: List of ParsedServer objects to export.
            
        Returns:
            JSON string containing sing-box configuration.
            
        Raises:
            ValueError: If server data is invalid or cannot be exported.
        """
        config = singbox_export(servers, [])
        return json.dumps(config, indent=2, ensure_ascii=False) 