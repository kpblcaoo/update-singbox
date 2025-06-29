import pytest
import json
from unittest.mock import patch, Mock
import requests
from sboxmgr.config.fetch import fetch_json, select_config


class TestFetchJson:
    """Test fetch_json function."""
    
    def test_fetch_json_success(self):
        """Test successful JSON fetching."""
        test_data = {"test": "data", "servers": ["server1", "server2"]}
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = test_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetch_json("https://example.com/config.json")
            
            assert result == test_data
            mock_get.assert_called_once_with(
                "https://example.com/config.json",
                headers={"User-Agent": "SFI"},
                proxies=None,
                timeout=10
            )
    
    def test_fetch_json_with_proxy(self):
        """Test JSON fetching with proxy."""
        test_data = {"proxy": "test"}
        proxy_url = "http://proxy:8080"
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = test_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetch_json("https://example.com/config.json", proxy_url)
            
            assert result == test_data
            mock_get.assert_called_once_with(
                "https://example.com/config.json",
                headers={"User-Agent": "SFI"},
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=10
            )
    
    def test_fetch_json_empty_response(self):
        """Test fetching empty JSON response."""
        with patch('requests.get') as mock_get, \
             patch('sboxmgr.config.fetch.error') as mock_error:
            
            mock_response = Mock()
            mock_response.json.return_value = None
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetch_json("https://example.com/config.json")
            
            assert result is None
            mock_error.assert_called_once_with("Received empty JSON from URL")
    
    def test_fetch_json_timeout_error(self):
        """Test timeout error handling."""
        with patch('requests.get', side_effect=requests.Timeout("Timeout")), \
             patch('sboxmgr.config.fetch.error') as mock_error:
            
            result = fetch_json("https://example.com/config.json")
            
            assert result is None
            mock_error.assert_called_once_with("Timeout fetching configuration from https://example.com/config.json")
    
    def test_fetch_json_http_error(self):
        """Test HTTP error handling."""
        with patch('requests.get') as mock_get, \
             patch('sboxmgr.config.fetch.error') as mock_error:
            
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
            mock_get.return_value = mock_response
            
            result = fetch_json("https://example.com/config.json")
            
            assert result is None
            mock_error.assert_called_once()
            assert "HTTP error fetching configuration" in mock_error.call_args[0][0]
    
    def test_fetch_json_connection_error(self):
        """Test connection error handling."""
        with patch('requests.get', side_effect=requests.ConnectionError("Connection failed")), \
             patch('sboxmgr.config.fetch.error') as mock_error:
            
            result = fetch_json("https://example.com/config.json")
            
            assert result is None
            mock_error.assert_called_once()
            assert "Connection error fetching configuration" in mock_error.call_args[0][0]
    
    def test_fetch_json_decode_error(self):
        """Test JSON decode error handling."""
        with patch('requests.get') as mock_get, \
             patch('sboxmgr.config.fetch.error') as mock_error:
            
            mock_response = Mock()
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetch_json("https://example.com/config.json")
            
            assert result is None
            mock_error.assert_called_once()
            assert "Invalid JSON received" in mock_error.call_args[0][0]
    
    def test_fetch_json_unexpected_error(self):
        """Test unexpected error handling."""
        with patch('requests.get', side_effect=Exception("Unexpected error")), \
             patch('sboxmgr.config.fetch.error') as mock_error:
            
            result = fetch_json("https://example.com/config.json")
            
            assert result is None
            mock_error.assert_called_once()
            assert "Unexpected error fetching configuration" in mock_error.call_args[0][0]


class TestSelectConfig:
    """Test select_config function."""
    
    def test_select_config_by_remarks_success(self):
        """Test successful selection by remarks."""
        json_data = {
            "outbounds": [
                {"type": "vless", "tag": "server1", "server": "example1.com"},
                {"type": "shadowsocks", "tag": "server2", "server": "example2.com"},
                {"type": "direct", "tag": "direct"}
            ]
        }
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
            
            result = select_config(json_data, "server2", None)
            
            assert result == {"type": "shadowsocks", "tag": "server2", "server": "example2.com"}
    
    def test_select_config_by_index_success(self):
        """Test successful selection by index."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com"},
            {"type": "shadowsocks", "tag": "server2", "server": "example2.com"}
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
            
            result = select_config(outbounds, None, 1)
            
            assert result == {"type": "shadowsocks", "tag": "server2", "server": "example2.com"}
    
    def test_select_config_filters_outbounds(self):
        """Test that only valid outbound types are considered."""
        json_data = {
            "outbounds": [
                {"type": "direct", "tag": "direct"},
                {"type": "vless", "tag": "server1", "server": "example1.com"},
                {"type": "block", "tag": "block"},
                {"type": "shadowsocks", "tag": "server2", "server": "example2.com"}
            ]
        }
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
            
            result = select_config(json_data, None, 0)
            
            # Should select first valid outbound (vless), not direct
            assert result == {"type": "vless", "tag": "server1", "server": "example1.com"}
    
    def test_select_config_empty_outbounds(self):
        """Test error when no valid outbounds found."""
        json_data = {
            "outbounds": [
                {"type": "direct", "tag": "direct"},
                {"type": "block", "tag": "block"}
            ]
        }
        
        with pytest.raises(ValueError, match="Received empty configuration"):
            select_config(json_data, None, 0)
    
    def test_select_config_remarks_not_found(self):
        """Test error when remarks not found."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com"},
            {"type": "shadowsocks", "tag": "server2", "server": "example2.com"}
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}):
            
            with pytest.raises(ValueError, match="No configuration found with remarks: nonexistent"):
                select_config(outbounds, "nonexistent", None)
    
    def test_select_config_index_out_of_range(self):
        """Test error when index is out of range."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com"}
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}):
            
            with pytest.raises(ValueError, match="No configuration found at index: 5"):
                select_config(outbounds, None, 5)
    
    def test_select_config_excluded_by_remarks(self):
        """Test error when selected server is excluded (by remarks)."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com", "port": 443}
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": [{"id": "excluded_id"}]}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="excluded_id"):
            
            with pytest.raises(ValueError, match="Сервер с remarks 'server1' находится в списке исключённых"):
                select_config(outbounds, "server1", None)
    
    def test_select_config_excluded_by_index(self):
        """Test error when selected server is excluded (by index)."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com", "port": 443}
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": [{"id": "excluded_id"}]}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="excluded_id"):
            
            with pytest.raises(ValueError, match="Сервер с индексом 0 находится в списке исключённых"):
                select_config(outbounds, None, 0)
    
    def test_select_config_with_dry_run(self):
        """Test select_config with dry_run parameter."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com"}
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions') as mock_load, \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
            
            mock_load.return_value = {"exclusions": []}
            
            result = select_config(outbounds, None, 0, dry_run=True)
            
            assert result == {"type": "vless", "tag": "server1", "server": "example1.com"}
            mock_load.assert_called_once_with(dry_run=True)
    
    def test_select_config_list_input(self):
        """Test select_config with list input (not dict with outbounds)."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com"},
            {"type": "shadowsocks", "tag": "server2", "server": "example2.com"}
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
            
            result = select_config(outbounds, "server2", None)
            
            assert result == {"type": "shadowsocks", "tag": "server2", "server": "example2.com"}


class TestSelectConfigEdgeCases:
    """Test edge cases for select_config function."""
    
    def test_select_config_all_supported_types(self):
        """Test all supported outbound types are recognized."""
        supported_types = ["vless", "shadowsocks", "vmess", "trojan", "tuic", "hysteria2"]
        
        json_data = {
            "outbounds": [
                {"type": outbound_type, "tag": f"server_{i}", "server": f"example{i}.com"}
                for i, outbound_type in enumerate(supported_types)
            ]
        }
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
            
            # Test each type can be selected
            for i, outbound_type in enumerate(supported_types):
                result = select_config(json_data, None, i)
                assert result["type"] == outbound_type
                assert result["tag"] == f"server_{i}"
    
    def test_select_config_mixed_valid_invalid_types(self):
        """Test filtering with mixed valid and invalid types."""
        json_data = {
            "outbounds": [
                {"type": "direct", "tag": "direct"},
                {"type": "vless", "tag": "server1", "server": "example1.com"},
                {"type": "block", "tag": "block"},
                {"type": "dns", "tag": "dns"},
                {"type": "shadowsocks", "tag": "server2", "server": "example2.com"},
                {"type": "selector", "tag": "selector"}
            ]
        }
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
            
            # Index 0 should get first valid outbound (vless)
            result = select_config(json_data, None, 0)
            assert result["type"] == "vless"
            
            # Index 1 should get second valid outbound (shadowsocks)
            result = select_config(json_data, None, 1)
            assert result["type"] == "shadowsocks"
    
    def test_select_config_complex_exclusions(self):
        """Test complex exclusions scenario."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com", "port": 443},
            {"type": "shadowsocks", "tag": "server2", "server": "example2.com", "port": 8080},
            {"type": "vmess", "tag": "server3", "server": "example3.com", "port": 80}
        ]
        
        exclusions = {
            "exclusions": [
                {"id": "server1_id"},
                {"id": "server3_id"}
            ]
        }
        
        def mock_generate_id(server):
            return f"{server['tag']}_id"
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value=exclusions), \
             patch('sboxmgr.config.fetch.generate_server_id', side_effect=mock_generate_id):
            
            # server1 and server3 are excluded, only server2 should be selectable
            result = select_config(outbounds, "server2", None)
            assert result["tag"] == "server2"
            
            # Trying to select excluded servers should fail
            with pytest.raises(ValueError, match="находится в списке исключённых"):
                select_config(outbounds, "server1", None)
            
            with pytest.raises(ValueError, match="находится в списке исключённых"):
                select_config(outbounds, "server3", None)
    
    def test_select_config_invalid_index_types(self):
        """Test invalid index types."""
        outbounds = [
            {"type": "vless", "tag": "server1", "server": "example1.com"}
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}):
            
            # String index should raise error
            with pytest.raises(ValueError, match="No configuration found at index"):
                select_config(outbounds, None, "invalid")
            
            # Negative index should work (Python list indexing)
            with patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
                result = select_config(outbounds, None, -1)
                assert result["tag"] == "server1"
    
    def test_select_config_empty_tag(self):
        """Test outbound with empty or missing tag."""
        outbounds = [
            {"type": "vless", "server": "example1.com"},  # No tag
            {"type": "shadowsocks", "tag": "", "server": "example2.com"},  # Empty tag
            {"type": "vmess", "tag": "server3", "server": "example3.com"}  # Normal tag
        ]
        
        with patch('sboxmgr.config.fetch.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.config.fetch.generate_server_id', return_value="test_id"):
            
            # Should be able to select by index even without tag
            result = select_config(outbounds, None, 0)
            assert result["type"] == "vless"
            assert "tag" not in result or result.get("tag") is None
            
            # Should be able to find by tag when it exists
            result = select_config(outbounds, "server3", None)
            assert result["tag"] == "server3"
            
            # Should not find by empty tag (empty string is falsy, so it goes to index path with None)
            with pytest.raises(ValueError, match="No configuration found at index: None"):
                select_config(outbounds, "", None)


class TestFetchJsonIntegration:
    """Integration tests for fetch_json function."""
    
    def test_fetch_json_real_response_structure(self):
        """Test fetch_json with realistic response structure."""
        realistic_data = {
            "outbounds": [
                {
                    "type": "vless",
                    "tag": "proxy-1",
                    "server": "example.com",
                    "server_port": 443,
                    "uuid": "12345678-1234-1234-1234-123456789abc",
                    "tls": {"enabled": True}
                }
            ],
            "route": {"rules": []},
            "dns": {"servers": []}
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = realistic_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetch_json("https://example.com/config.json")
            
            assert result == realistic_data
            assert "outbounds" in result
            assert len(result["outbounds"]) == 1
            assert result["outbounds"][0]["type"] == "vless"
    
    def test_fetch_json_error_logging_integration(self):
        """Test that all error types are properly logged."""
        test_url = "https://example.com/config.json"
        
        error_scenarios = [
            (requests.Timeout("Timeout"), "Timeout fetching configuration"),
            (requests.HTTPError("404"), "HTTP error fetching configuration"),
            (requests.ConnectionError("Connection failed"), "Connection error fetching configuration"),
            (Exception("Unexpected"), "Unexpected error fetching configuration")
        ]
        
        for exception, expected_log in error_scenarios:
            with patch('requests.get', side_effect=exception), \
                 patch('sboxmgr.config.fetch.error') as mock_error:
                
                result = fetch_json(test_url)
                
                assert result is None
                mock_error.assert_called_once()
                assert expected_log in mock_error.call_args[0][0]
                assert test_url in mock_error.call_args[0][0]
