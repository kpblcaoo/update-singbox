"""Tests for config generation bugfixes."""

import pytest
from unittest.mock import patch, Mock
from sboxmgr.config.generate import generate_temp_config, validate_temp_config_dict
from sboxmgr.subscription.parsers.uri_list_parser import URIListParser


class TestConfigGenerateBugfixes:
    """Test suite for config generation bug fixes."""

    def test_validate_temp_config_json_string_input(self):
        """Test that validate_temp_config accepts JSON string, not dict."""
        # This test is no longer relevant as validate_temp_config was removed
        # The validation is now handled by basic JSON parsing in generate_config
        pass

    def test_orchestrator_creates_new_subscription_manager(self):
        """Test that Orchestrator always creates new SubscriptionManager for each URL."""
        from sboxmgr.core.orchestrator import Orchestrator
        from sboxmgr.subscription.models import SubscriptionSource, PipelineResult
        
        # Create orchestrator
        orchestrator = Orchestrator.create_default()
        
        # Mock the SubscriptionManager constructor to track calls
        with patch("sboxmgr.subscription.manager.SubscriptionManager") as mock_manager_class:
            mock_manager_instance = Mock()
            mock_result = PipelineResult(config=[], context=Mock(), errors=[], success=True)
            mock_manager_instance.get_servers.return_value = mock_result
            mock_manager_class.return_value = mock_manager_instance
            
            # Call get_subscription_servers with different URLs
            url1 = "http://example1.com/sub"
            url2 = "http://example2.com/sub"
            
            orchestrator.get_subscription_servers(url=url1)
            orchestrator.get_subscription_servers(url=url2)
            
            # Verify that SubscriptionManager was created twice with different sources
            assert mock_manager_class.call_count == 2
            
            # Verify that each call used the correct URL
            call1_source = mock_manager_class.call_args_list[0][0][0]
            call2_source = mock_manager_class.call_args_list[1][0][0]
            
            assert isinstance(call1_source, SubscriptionSource)
            assert isinstance(call2_source, SubscriptionSource)
            assert call1_source.url == url1
            assert call2_source.url == url2

    def test_validate_temp_config_dict_error_handling(self):
        """Test that validate_temp_config_dict handles error messages correctly.
        
        This test verifies that the function correctly handles string error messages
        from validate_config_dict instead of trying to join them as a list.
        """
        from sboxmgr.config.generate import validate_temp_config_dict
        
        # Invalid config that will trigger validation error (missing required outbounds field)
        invalid_config = {"invalid": "config"}
        
        # Should raise ValueError with proper error message (not joined string)
        with pytest.raises(ValueError) as exc_info:
            validate_temp_config_dict(invalid_config)
        
        error_message = str(exc_info.value)
        # Updated to match new error message format
        assert "Configuration must contain 'outbounds' key" in error_message
        # Should not contain artifacts from joining a string character by character
        assert not any(char in error_message for char in ["o; u; t; b; o; u; n; d; s"])

    def test_json_parsing_fix(self):
        """Test that JSON parsing validation uses correct function."""
        template_data = {
            "outbounds": [],
            "inbounds": [{"type": "mixed", "listen": "127.0.0.1", "listen_port": 1080}]
        }
        servers = [{"type": "shadowsocks", "server": "1.2.3.4", "server_port": 8388}]
        
        config = generate_temp_config(template_data, servers)
        
        # This should not raise an error
        validate_temp_config_dict(config)
        
    def test_server_port_conversion(self):
        """Test that server_port is properly converted to port."""
        template_data = {"outbounds": []}
        servers = [
            {"type": "shadowsocks", "server": "1.2.3.4", "server_port": 8388, "method": "aes-256-gcm"},
            {"type": "trojan", "server": "2.3.4.5", "port": 443},  # Already has port
            {"type": "vmess", "server": "3.4.5.6", "server_port": 80, "port": 8080}  # Both fields
        ]
        
        config = generate_temp_config(template_data, servers)
        outbounds = config["outbounds"]
        
        # First server: server_port should be converted to port
        assert outbounds[0]["port"] == 8388
        assert "server_port" not in outbounds[0]
        
        # Second server: port should remain unchanged
        assert outbounds[1]["port"] == 443
        assert "server_port" not in outbounds[1]
        
        # Third server: port should be preserved, server_port removed
        assert outbounds[2]["port"] == 8080
        assert "server_port" not in outbounds[2]
        
    def test_server_port_missing_both_fields(self):
        """Test behavior when neither port nor server_port is present."""
        template_data = {"outbounds": []}
        servers = [{"type": "shadowsocks", "server": "1.2.3.4", "method": "aes-256-gcm"}]
        
        config = generate_temp_config(template_data, servers)
        outbounds = config["outbounds"]
        
        # Should not have port field added
        assert "port" not in outbounds[0]
        assert "server_port" not in outbounds[0]


class TestURIParserExceptionHandling:
    """Test improved exception handling in URI parser."""
    
    def test_vmess_specific_exceptions(self):
        """Test that vmess parsing catches specific exceptions."""
        parser = URIListParser()
        
        # Test invalid base64
        invalid_b64 = "vmess://invalid!base64!"
        result = parser._parse_vmess(invalid_b64)
        assert result.type == "vmess"
        assert result.address == "invalid"
        assert "decode failed" in result.meta["error"]
        
        # Test invalid JSON after base64 decode
        import base64
        invalid_json = base64.urlsafe_b64encode(b"not json").decode()
        invalid_json_uri = f"vmess://{invalid_json}"
        result = parser._parse_vmess(invalid_json_uri)
        assert result.type == "vmess"
        assert result.address == "invalid"
        assert "decode failed" in result.meta["error"]
        
    def test_ss_base64_fallback(self):
        """Test that SS parsing falls back gracefully on decode errors."""
        parser = URIListParser()
        
        # Test with invalid base64 that should fallback to plain text
        uri_data = "invalid!base64@example.com:8388"
        line = f"ss://{uri_data}"
        result = parser._extract_ss_components(uri_data, line)
        
        # Should fallback to treating as plain text
        assert result == ("invalid!base64", "example.com:8388")
        
    def test_ss_parsing_with_various_errors(self):
        """Test SS parsing handles various error conditions."""
        parser = URIListParser()
        
        # Test completely malformed URI
        malformed = "ss://totally-broken-uri-with-no-structure"
        result = parser._parse_ss(malformed)
        
        # Should return invalid server
        assert result.type == "ss"
        assert result.address == "invalid"
        assert "error" in result.meta
