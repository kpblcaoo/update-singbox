#!/usr/bin/env python3
"""
Update sing-box configuration from a remote JSON source.

This script fetches proxy configurations from a specified URL, validates the
selected protocol, generates a sing-box configuration file, and manages the
sing-box service. It supports protocols like VLESS, Shadowsocks, VMess, Trojan,
TUIC, and Hysteria2.

Usage:
    python3 update_singbox.py -u <URL> [-r <remarks> | -i <index>] [-d]
    Example: python3 update_singbox.py -u https://example.com/config -r "Server1"
    Example: python3 update_singbox.py -u https://example.com/config -i 2 -d

Environment Variables:
    SINGBOX_LOG_FILE: Path to log file (default: /var/log/update-singbox.log)
    SINGBOX_CONFIG_FILE: Path to config file (default: /etc/sing-box/config.json)
    SINGBOX_BACKUP_FILE: Path to backup file (default: /etc/sing-box/config.json.bak)
    SINGBOX_TEMPLATE_FILE: Path to template file (default: ./config.template.json)
    SINGBOX_MAX_LOG_SIZE: Max log size in bytes (default: 1048576)

Requirements:
    Python 3.10 or later (for match statement).
    requests library with SOCKS support (pip install requests[socks])
"""
import argparse
import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import requests
import tempfile
from urllib.parse import urlparse

# Check Python version for match statement compatibility
if sys.version_info < (3, 10):
    print("Error: Python 3.10 or later is required for this script.", file=sys.stderr)
    sys.exit(1)

# Configuration with environment variable fallbacks
LOG_FILE = os.getenv("SINGBOX_LOG_FILE", "/var/log/update-singbox.log")
CONFIG_FILE = os.getenv("SINGBOX_CONFIG_FILE", "/etc/sing-box/config.json")
BACKUP_FILE = os.getenv("SINGBOX_BACKUP_FILE", "/etc/sing-box/config.json.bak")
TEMPLATE_FILE = os.getenv("SINGBOX_TEMPLATE_FILE", "./config.template.json")
MAX_LOG_SIZE = int(os.getenv("SINGBOX_MAX_LOG_SIZE", "1048576"))  # 1MB

# Supported protocols
SUPPORTED_PROTOCOLS = {"vless", "shadowsocks", "vmess", "trojan", "tuic", "hysteria2"}

def handle_error(message, recover=False):
    logging.error(message)
    if recover and os.path.exists(BACKUP_FILE):
        try:
            shutil.copy2(BACKUP_FILE, CONFIG_FILE)
            manage_service("restart")
            logging.warning("Restored previous config from backup.")
        except Exception as e:
            logging.critical(f"Rollback failed: {e}")


def setup_logging(debug):
    """Configure logging with file and syslog handlers."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(file_handler)

    # Syslog handler
    try:
        syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
        syslog_handler.setFormatter(logging.Formatter("sing-box-update: %(message)s"))
        logger.addHandler(syslog_handler)
    except OSError as e:
        logging.warning(f"Failed to configure syslog handler: {e}")

    rotate_logs()

def rotate_logs():
    """Rotate log file if it exceeds MAX_LOG_SIZE."""
    if not os.path.exists(LOG_FILE):
        return
    log_size = os.path.getsize(LOG_FILE)
    if log_size > MAX_LOG_SIZE:
        for i in range(5, 0, -1):
            old_log = f"{LOG_FILE}.{i}"
            new_log = f"{LOG_FILE}.{i+1}"
            if os.path.exists(old_log):
                os.rename(old_log, new_log)
        os.rename(LOG_FILE, f"{LOG_FILE}.1")
        open(LOG_FILE, "a").close()  # Create empty log file


def fetch_json(url, proxy=None):
    """Fetch JSON from URL using requests with optional SOCKS proxy."""
    try:
        # Configure proxy if provided
        proxies = {}
         # Ensure proxy starts with socks5:// or socks5h://
        if proxy:
            if not proxy.startswith(("socks5://", "socks5h://")):
                proxy = f"socks5://{proxy}"
            proxies = {"http": proxy, "https": proxy}
        logging.debug(f"Fetching JSON from URL: {url} with proxy: {proxies}")
        # Send request with User-Agent
        response = requests.get(url, proxies=proxies, headers={"User-Agent": "ktor-client"})
        logging.debug(f"Response Status Code: {response.status_code}")
        logging.debug(f"Response Content: {response.text}")
        response.raise_for_status() # Raise exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        handle_error(f"Failed to fetch configuration from {url}: {e}")
    except ValueError:
        handle_error("Received invalid JSON from URL")

def select_config(json_data, remarks, index):
    """Select proxy configuration by remarks or index."""
    logging.debug(f"Fetched JSON data: {json_data}")
    if not json_data:
        handle_error("Received empty configuration")
    if remarks:
        for item in json_data:
            if item.get("remarks") == remarks:
                logging.debug(f"Selected configuration by remarks: {item}")
                return item.get("outbounds", [{}])[0]
        handle_error(f"No configuration found with remarks: {remarks}")
    try:
        logging.debug(f"Selected configuration by index: {json_data[index]}")
        return json_data[index].get("outbounds", [{}])[0]
    except (IndexError, TypeError):
        handle_error(f"No configuration found at index: {index}")

valid_outbounds = []

for idx, config in enumerate(json_data):
    logging.info(f"Processing server at index {idx}")
    try:
        outbounds = config.get("outbounds", [])
        for outbound_idx, outbound_config in enumerate(outbounds):
            logging.info(f"Testing outbound at index {outbound_idx} for server {idx}")
            try:
                outbound = validate_protocol(outbound_config, outbound_idx, idx)
                
                # Check for duplicate tags
                if not any(o["tag"] == outbound["tag"] for o in valid_outbounds):
                    valid_outbounds.append(outbound)
                else:
                    logging.warning(f"Duplicate tag detected and skipped: {outbound['tag']}")
            except Exception as e:
                logging.error(f"Failed to process outbound at index {outbound_idx} for server {idx}: {e}")
    except Exception as e:
        logging.error(f"Failed to process server at index {idx}: {e}")

    # Protocol-specific handling using match statement
    match protocol:
        case "vless":
            vnext = config.get("settings", {}).get("vnext", [{}])[0]
            users = vnext.get("users", [{}])[0]
            params = {
                "server": vnext.get("address"),
                "server_port": vnext.get("port"),
                "uuid": users.get("id"),
            }
            if users.get("flow"):
                params["flow"] = users.get("flow")
            outbound.update(params)
            required_keys = ["server", "server_port", "uuid"]
        case "shadowsocks":
            server = config.get("settings", {}).get("servers", [{}])[0]
            params = {
                "server": server.get("address"),
                "server_port": server.get("port"),
                "method": server.get("method"),
                "password": server.get("password"),
            }
            if server.get("plugin"):
                params["plugin"] = server.get("plugin")
            if server.get("plugin_opts"):
                params["plugin_opts"] = server.get("plugin_opts")
            outbound.update(params)
            required_keys = ["server", "server_port", "method", "password"]
        case "vmess":
            vnext = config.get("settings", {}).get("vnext", [{}])[0]
            users = vnext.get("users", [{}])[0]
            outbound.update({
                "server": vnext.get("address"),
                "server_port": vnext.get("port"),
                "uuid": users.get("id"),
                "security": users.get("security", "auto"),
            })
            required_keys = ["server", "server_port", "uuid"]
        case "trojan":
            server = config.get("settings", {}).get("servers", [{}])[0]
            outbound.update({
                "server": server.get("address"),
                "server_port": server.get("port"),
                "password": server.get("password"),
            })
            required_keys = ["server", "server_port", "password"]
        case "tuic":
            server = config.get("settings", {}).get("servers", [{}])[0]
            params = {
                "server": server.get("address"),
                "server_port": server.get("port"),
                "uuid": server.get("uuid"),
            }
            if server.get("password"):
                params["password"] = server.get("password")
            outbound.update(params)
            required_keys = ["server", "server_port", "uuid"]
        case "hysteria2":
            server = config.get("settings", {}).get("servers", [{}])[0]
            outbound.update({
                "server": server.get("address"),
                "server_port": server.get("port"),
                "password": server.get("password"),
            })
            required_keys = ["server", "server_port", "password"]
        case _:
            handle_error(f"No handler defined for protocol: {protocol}")

    # Validate required parameters
    for key in required_keys:
        if not outbound.get(key):
            handle_error(f"Missing required parameter for {protocol}: {key}")

    # Handle security and transport settings
    outbound = handle_security_and_transport(config, outbound, protocol)
    return outbound

def handle_security_and_transport(config, outbound, protocol):
    """Handle security and transport settings."""
    if protocol == "shadowsocks":
        # Shadowsocks ignores security and non-tcp transport settings
        if config.get("streamSettings", {}).get("security", "none") != "none":
            logging.warning("Security settings ignored for Shadowsocks")
        if config.get("streamSettings", {}).get("network", "tcp") != "tcp":
            logging.warning("Transport settings ignored for Shadowsocks")
        return outbound

    stream_settings = config.get("streamSettings", {})
    security = stream_settings.get("security", "none")
    transport = stream_settings.get("network", "tcp")

    # Validate compatibility of transport and security
    if protocol == "vless" and security == "reality":
        if transport in {"ws", "tuic", "hysteria2", "shadowtls"}:
            handle_error(f"Transport {transport} is incompatible with reality")
    if security == "reality" and protocol != "vless":
        handle_error(f"Security reality is only supported for VLESS")

    # Configure TLS for reality or tls security
    if security == "reality":
        reality_settings = stream_settings.get("realitySettings", {})
        tls = {
            "enabled": True,
            "reality": {
                "enabled": True,
                "public_key": reality_settings.get("publicKey"),
                "short_id": reality_settings.get("shortId"),
            },
        }
        if reality_settings.get("serverName"):
            tls["server_name"] = reality_settings.get("serverName")
        if reality_settings.get("fingerprint"):
            tls["utls"] = {"enabled": True, "fingerprint": reality_settings.get("fingerprint", "chrome")}
        if not all(tls["reality"].get(k) for k in ["public_key", "short_id"]):
            handle_error("Missing required parameters for reality: publicKey, shortId")
        outbound["tls"] = tls
    elif security == "tls":
        tls_settings = stream_settings.get("tlsSettings", {})
        tls = {"enabled": True, "server_name": tls_settings.get("serverName")}
        if not tls["server_name"]:
            handle_error("Missing serverName for tls")
        if tls_settings.get("fingerprint"):
            tls["utls"] = {"enabled": True, "fingerprint": tls_settings.get("fingerprint", "chrome")}
        if tls_settings.get("alpn"):
            tls["alpn"] = tls_settings.get("alpn")
        outbound["tls"] = tls
    elif security != "none":
        handle_error(f"Unknown security type: {security}")

    # Configure transport settings (except for reality+tcp+vless)
    if security != "reality" or transport != "tcp" or protocol != "vless":
        transport_settings = {}
        match transport:
            case "ws":
                ws_settings = stream_settings.get("wsSettings", {})
                transport_settings = {"type": "ws"}
                if ws_settings.get("path"):
                    transport_settings["path"] = ws_settings.get("path")
                if ws_settings.get("headers", {}).get("Host"):
                    transport_settings["headers"] = {"Host": ws_settings["headers"]["Host"]}
            case "grpc":
                grpc_settings = stream_settings.get("grpcSettings", {})
                transport_settings = {"type": "grpc", "service_name": grpc_settings.get("serviceName")}
                if not transport_settings["service_name"]:
                    handle_error("Missing serviceName for grpc")
            case "http":
                http_settings = stream_settings.get("httpSettings", {})
                transport_settings = {"type": "http"}
                if http_settings.get("path"):
                    transport_settings["path"] = http_settings.get("path")
                if http_settings.get("host"):
                    transport_settings["headers"] = {"Host": http_settings["host"]}
            case "tcp":
                transport_settings = {"type": "tcp"}
            case _:
                handle_error(f"Unknown transport type: {transport}")
        if transport_settings:
            outbound["transport"] = transport_settings
    return outbound

def generate_config(template_file, outbound_tags):
    try:
        with open(template_file, "r", encoding="utf-8") as f:
            template = f.read()

        config_str = template.replace("$outbound_json", json.dumps(outbound_tags, indent=2))
        json.loads(config_str)  # Validate that the generated config is valid JSON

        dir_name = os.path.dirname(CONFIG_FILE)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_name, suffix=".json") as tmp:
            tmp.write(config_str)
            temp_path = tmp.name

        subprocess.run(["sing-box", "check", "-c", temp_path], check=True)

        if os.path.exists(CONFIG_FILE):
            shutil.copy2(CONFIG_FILE, BACKUP_FILE)
            logging.info(f"Created backup: {BACKUP_FILE}")

        os.replace(temp_path, CONFIG_FILE)
        logging.info(f"Config written to: {CONFIG_FILE}")

        # Restart the service and check its status
        if not manage_service():
            raise RuntimeError("sing-box restart failed after config update")

    except Exception as e:
        handle_error(f"Failed to apply new config: {e}", recover=True)

    # Create an array of outbound tags for urltest
    outbound_tags_list = [o["tag"] for o in outbound_tags if "tag" in o]

    # Replace $outbound_json in the template with the array of tags
    config = template.replace("$outbound_json", json.dumps(outbound_tags_list, indent=2))

    # Add all outbound objects (with servers and their settings)
    full_config = json.loads(config)
    full_config["outbounds"].extend(outbound_tags)

    # Write the final configuration
    with open(CONFIG_FILE, "w") as f:
        f.write(json.dumps(full_config, indent=2))
    logging.info(f"Configuration updated with outbound tags: {outbound_tags_list}")

    # Validate configuration with sing-box
    try:
        subprocess.run(["sing-box", "check", "-c", CONFIG_FILE], check=True)
        logging.info("Configuration validated successfully")
    except (subprocess.CalledProcessError, FileNotFoundError):
        handle_error("Generated configuration is invalid or sing-box not found")

def manage_service():
    """Restart or start sing-box service."""
    if not shutil.which("systemctl"):
        handle_error("systemctl not found; cannot manage sing-box service")
    try:
        result = subprocess.run(["systemctl", "is-active", "--quiet", "sing-box.service"], check=False)
        action = "restart" if result.returncode == 0 else "start"
        subprocess.run(["systemctl", action, "sing-box.service"], check=True)
        logging.info(f"Service {action}ed")
    except subprocess.CalledProcessError:
        handle_error(f"Failed to {action} sing-box service")

def main():
    """Main function to update sing-box configuration."""
    parser = argparse.ArgumentParser(description="Update sing-box configuration")
    parser.add_argument("-u", "--url", required=True, help="URL for proxy configuration")
    parser.add_argument("-r", "--remarks", help="Select server by remarks")
    parser.add_argument("-i", "--index", type=int, default=None, help="Select server by index (default: None)")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--proxy", help="SOCKS5 proxy address (e.g., socks5://127.0.0.1:1080 or 127.0.0.1:1080)")
    args = parser.parse_args()

    setup_logging(args.debug)
    logging.info("=== Starting sing-box configuration update ===")

    # Fetch JSON data from the provided URL
    json_data = fetch_json(args.url, args.proxy)

    # Process JSON data and validate configurations
    valid_outbounds = []

    for idx, config in enumerate(json_data):
        logging.info(f"Processing server at index {idx}")
        try:
            outbounds = config.get("outbounds", [])
            for outbound_idx, outbound_config in enumerate(outbounds):
                logging.info(f"Testing outbound at index {outbound_idx} for server {idx}")
                try:
                    outbound = validate_protocol(outbound_config, outbound_idx, idx)
                    valid_outbounds.append(outbound)
                except Exception as e:
                    logging.error(f"Failed to process outbound at index {outbound_idx} for server {idx}: {e}")
        except Exception as e:
            logging.error(f"Failed to process server at index {idx}: {e}")

    # Generate configuration if valid outbounds are found
    if valid_outbounds:
        generate_config(TEMPLATE_FILE, valid_outbounds)
    else:
        logging.error("No valid outbounds found. Configuration update aborted.")

    logging.info("Update completed")

if __name__ == "__main__":
    main()