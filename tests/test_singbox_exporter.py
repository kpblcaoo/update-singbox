from sboxmgr.subscription.exporters.singbox_exporter import singbox_export
from sboxmgr.subscription.models import ParsedServer
import json
import pytest
from sboxmgr.subscription.exporters.singbox_exporter import _export_wireguard, _export_tuic

def test_singbox_exporter():
    servers = [
        ParsedServer(type="vmess", address="example.com", port=443, security="auto", meta={"uuid": "0000"}),  # pragma: allowlist secret
        ParsedServer(type="ss", address="127.0.0.1", port=8388, security="aes-256-gcm", meta={"password": "pass"}),  # pragma: allowlist secret
    ]
    config = singbox_export(servers, routes=[])
    config_json = json.dumps(config)
    assert "outbounds" in config_json
    assert "example.com" in config_json
    assert "127.0.0.1" in config_json

def test_export_wireguard_with_falsy_values():
    """Test that wireguard export correctly handles falsy values (0, False, None) in meta fields."""
    server = ParsedServer(
        type="wireguard",
        address="10.0.0.1",
        port=51820,
        private_key="private_key_test",  # pragma: allowlist secret
        peer_public_key="peer_public_key_test",  # pragma: allowlist secret
        local_address=["10.0.0.2/24"],
        meta={
            "mtu": 0,  # Falsy but valid value
            "keepalive": False,  # Falsy but valid value
        }
    )
    config = singbox_export([server], routes=[])
    config_json = json.dumps(config)
    
    # Check that falsy values are included in export
    assert "mtu" in config_json
    assert "keepalive" in config_json
    assert '"mtu": 0' in config_json
    assert '"keepalive": false' in config_json

def test_export_tuic_with_falsy_values():
    """Test that tuic export correctly handles falsy values in udp_relay_mode."""
    server = ParsedServer(
        type="tuic",
        address="10.0.0.1",
        port=443,
        uuid="test-uuid",
        password="test-password",  # pragma: allowlist secret
        meta={
            "udp_relay_mode": False,  # Falsy but valid value
        }
    )
    config = singbox_export([server], routes=[])
    config_json = json.dumps(config)
    
    # Check that falsy udp_relay_mode is included in export
    assert "udp_relay_mode" in config_json
    assert '"udp_relay_mode": false' in config_json

def test_export_with_none_values():
    """Test that export correctly handles None values in meta fields."""
    server = ParsedServer(
        type="wireguard",
        address="10.0.0.1",
        port=51820,
        private_key="private_key_test",  # pragma: allowlist secret
        peer_public_key="peer_public_key_test",  # pragma: allowlist secret
        local_address=["10.0.0.2/24"],
        meta={
            "mtu": None,  # None value
            "keepalive": None,  # None value
        }
    )
    config = singbox_export([server], routes=[])
    config_json = json.dumps(config)
    
    # Check that None values are NOT included in export (correct behavior)
    assert "mtu" not in config_json
    assert "keepalive" not in config_json

def test_export_outbound_without_tag():
    """Test that outbound without 'tag' does not cause KeyError and special outbounds are added."""
    server = ParsedServer(
        type="wireguard",
        address="10.0.0.1",
        port=51820,
        private_key="private_key_test",  # pragma: allowlist secret
        peer_public_key="peer_public_key_test",  # pragma: allowlist secret
        local_address=["10.0.0.2/24"],
        meta={}
    )
    config = singbox_export([server], routes=[])
    outbounds = config.get("outbounds", [])
    # Должны быть служебные outbounds (direct, block, dns-out)
    tags = {o.get("tag") for o in outbounds}
    assert "direct" in tags
    assert "block" in tags
    assert "dns-out" in tags

class TestSingboxExporterMetaHandling:
    """Test meta field handling in singbox exporter."""
    
    def test_wireguard_with_none_meta(self):
        """Test wireguard export with meta=None doesn't raise AttributeError."""
        server = ParsedServer(
            type="wireguard",
            address="1.1.1.1",
            port=51820,
            private_key="test_private_key",  # pragma: allowlist secret
            peer_public_key="test_peer_public_key",  # pragma: allowlist secret
            local_address=["10.0.0.2/24"],
            meta=None  # Explicitly set to None
        )
        
        # Should not raise AttributeError
        result = _export_wireguard(server)
        
        assert result is not None
        assert result["type"] == "wireguard"
        assert result["server"] == "1.1.1.1"
        assert result["server_port"] == 51820
        assert result["private_key"] == "test_private_key"
        assert result["peer_public_key"] == "test_peer_public_key"
        assert result["local_address"] == ["10.0.0.2/24"]
        # mtu and keepalive should not be present when meta is None
        assert "mtu" not in result
        assert "keepalive" not in result
    
    def test_wireguard_with_empty_meta(self):
        """Test wireguard export with empty meta dict."""
        server = ParsedServer(
            type="wireguard",
            address="1.1.1.1",
            port=51820,
            private_key="test_private_key",  # pragma: allowlist secret
            peer_public_key="test_peer_public_key",  # pragma: allowlist secret
            local_address=["10.0.0.2/24"],
            meta={}  # Empty dict
        )
        
        result = _export_wireguard(server)
        
        assert result is not None
        assert result["type"] == "wireguard"
        # mtu and keepalive should not be present when meta is empty
        assert "mtu" not in result
        assert "keepalive" not in result
    
    def test_wireguard_with_valid_meta(self):
        """Test wireguard export with valid meta containing mtu and keepalive."""
        server = ParsedServer(
            type="wireguard",
            address="1.1.1.1",
            port=51820,
            private_key="test_private_key",  # pragma: allowlist secret
            peer_public_key="test_peer_public_key",  # pragma: allowlist secret
            local_address=["10.0.0.2/24"],
            meta={"mtu": 1420, "keepalive": 25}
        )
        
        result = _export_wireguard(server)
        
        assert result is not None
        assert result["type"] == "wireguard"
        assert result["mtu"] == 1420
        assert result["keepalive"] == 25
    
    def test_wireguard_with_falsy_meta_values(self):
        """Test wireguard export with falsy values in meta (mtu=0, keepalive=false)."""
        server = ParsedServer(
            type="wireguard",
            address="1.1.1.1",
            port=51820,
            private_key="test_private_key",  # pragma: allowlist secret
            peer_public_key="test_peer_public_key",  # pragma: allowlist secret
            local_address=["10.0.0.2/24"],
            meta={"mtu": 0, "keepalive": False}
        )
        
        result = _export_wireguard(server)
        
        assert result is not None
        assert result["type"] == "wireguard"
        # Falsy values should be included
        assert result["mtu"] == 0
        assert result["keepalive"] is False
    
    def test_tuic_with_none_meta(self):
        """Test tuic export with meta=None doesn't raise AttributeError."""
        server = ParsedServer(
            type="tuic",
            address="1.1.1.1",
            port=443,
            uuid="test-uuid",
            password="test-password",  # pragma: allowlist secret
            meta=None  # Explicitly set to None
        )
        
        # Should not raise AttributeError
        result = _export_tuic(server)
        
        assert result is not None
        assert result["type"] == "tuic"
        assert result["server"] == "1.1.1.1"
        assert result["server_port"] == 443
        assert result["uuid"] == "test-uuid"
        assert result["password"] == "test-password"
        # udp_relay_mode should not be present when meta is None
        assert "udp_relay_mode" not in result
    
    def test_tuic_with_valid_meta(self):
        """Test tuic export with valid meta containing udp_relay_mode."""
        server = ParsedServer(
            type="tuic",
            address="1.1.1.1",
            port=443,
            uuid="test-uuid",
            password="test-password",  # pragma: allowlist secret
            meta={"udp_relay_mode": "native"}
        )
        
        result = _export_tuic(server)
        
        assert result is not None
        assert result["type"] == "tuic"
        assert result["udp_relay_mode"] == "native"
    
    def test_tuic_with_falsy_meta_values(self):
        """Test tuic export with falsy values in meta."""
        server = ParsedServer(
            type="tuic",
            address="1.1.1.1",
            port=443,
            uuid="test-uuid",
            password="test-password",  # pragma: allowlist secret
            meta={"udp_relay_mode": False}
        )
        
        result = _export_tuic(server)
        
        assert result is not None
        assert result["type"] == "tuic"
        # Falsy values should be included
        assert result["udp_relay_mode"] is False
    
    def test_server_without_meta_attribute(self):
        """Test export with server that doesn't have meta attribute."""
        # Create a server object without meta attribute
        server = ParsedServer(
            type="wireguard",
            address="1.1.1.1",
            port=51820,
            private_key="test_private_key",  # pragma: allowlist secret
            peer_public_key="test_peer_public_key",  # pragma: allowlist secret
            local_address=["10.0.0.2/24"]
        )
        # Manually remove meta attribute to simulate old server objects
        delattr(server, 'meta')
        
        # Should not raise AttributeError
        result = _export_wireguard(server)
        
        assert result is not None
        assert result["type"] == "wireguard"
        # mtu and keepalive should not be present
        assert "mtu" not in result
        assert "keepalive" not in result 