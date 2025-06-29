import pytest
from unittest.mock import patch
from sboxmgr.server.selection import list_servers


class TestListServers:
    """Test list_servers function."""
    
    def test_list_servers_basic_functionality(self):
        """Test basic functionality of list_servers."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                },
                {
                    "tag": "server2", 
                    "type": "vmess",
                    "server_port": 443,
                    "server": "2.2.2.2"
                }
            ]
        }
        supported_protocols = ["shadowsocks", "vmess"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id') as mock_gen_id, \
             patch('typer.echo') as mock_echo:
            
            mock_gen_id.side_effect = ["id1", "id2"]
            
            list_servers(json_data, supported_protocols)
            
            # Check header output
            mock_echo.assert_any_call("Index | Name | Protocol | Port")
            mock_echo.assert_any_call("--------------------------------")
            
            # Check server output
            mock_echo.assert_any_call("0 | server1 | shadowsocks | 8080")
            mock_echo.assert_any_call("1 | server2 | vmess | 443")
    
    def test_list_servers_with_exclusions(self):
        """Test list_servers with excluded servers."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks", 
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                },
                {
                    "tag": "server2",
                    "type": "vmess",
                    "server_port": 443,
                    "server": "2.2.2.2"
                }
            ]
        }
        supported_protocols = ["shadowsocks", "vmess"]
        exclusions = {
            "exclusions": [
                {"id": "excluded_id1"}
            ]
        }
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value=exclusions), \
             patch('sboxmgr.server.selection.generate_server_id') as mock_gen_id, \
             patch('typer.echo') as mock_echo:
            
            mock_gen_id.side_effect = ["excluded_id1", "id2"]
            
            list_servers(json_data, supported_protocols)
            
            # Check that excluded server is marked
            mock_echo.assert_any_call("0 | server1 [excluded] | shadowsocks | 8080")
            mock_echo.assert_any_call("1 | server2 | vmess | 443")
    
    def test_list_servers_unsupported_protocols(self):
        """Test list_servers filters unsupported protocols."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                },
                {
                    "tag": "server2",
                    "type": "unsupported_protocol",
                    "server_port": 443,
                    "server": "2.2.2.2"
                }
            ]
        }
        supported_protocols = ["shadowsocks", "vmess"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('typer.echo') as mock_echo:
            
            list_servers(json_data, supported_protocols)
            
            # Only supported protocol should be shown
            mock_echo.assert_any_call("0 | server1 | shadowsocks | 8080")
            
            # Unsupported protocol should not appear
            echo_calls = [call[0][0] for call in mock_echo.call_args_list]
            assert not any("unsupported_protocol" in call for call in echo_calls)
    
    def test_list_servers_missing_fields(self):
        """Test list_servers handles missing fields gracefully."""
        json_data = {
            "outbounds": [
                {
                    "type": "shadowsocks",
                    # Missing tag, server_port
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                },
                {
                    "tag": "server2",
                    # Missing type, server_port
                    "server": "2.2.2.2"
                }
            ]
        }
        supported_protocols = ["shadowsocks", "vmess"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('typer.echo') as mock_echo:
            
            list_servers(json_data, supported_protocols)
            
            # Should handle missing fields with N/A
            mock_echo.assert_any_call("0 | N/A | shadowsocks | N/A")
            
            # Server with missing type should be filtered out
            echo_calls = [call[0][0] for call in mock_echo.call_args_list]
            assert not any("server2" in call for call in echo_calls)
    
    def test_list_servers_debug_logging(self):
        """Test list_servers with debug logging enabled."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                }
            ]
        }
        supported_protocols = ["shadowsocks"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('logging.info') as mock_log:
            
            list_servers(json_data, supported_protocols, debug_level=1)
            
            # Check logging output
            mock_log.assert_any_call("Index | Name | Protocol | Port")
            mock_log.assert_any_call("--------------------------------")
            mock_log.assert_any_call("0 | server1 | shadowsocks | 8080")
    
    def test_list_servers_no_debug_logging(self):
        """Test list_servers with debug logging disabled."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                }
            ]
        }
        supported_protocols = ["shadowsocks"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('logging.info') as mock_log:
            
            list_servers(json_data, supported_protocols, debug_level=-1)
            
            # Should not log when debug_level < 0
            mock_log.assert_not_called()
    
    def test_list_servers_dry_run_mode(self):
        """Test list_servers in dry run mode."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                }
            ]
        }
        supported_protocols = ["shadowsocks"]
        
        with patch('sboxmgr.server.selection.load_exclusions') as mock_load_exclusions, \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('typer.echo') as mock_echo:
            
            mock_load_exclusions.return_value = {"exclusions": []}
            
            list_servers(json_data, supported_protocols, dry_run=True)
            
            # Should pass dry_run to load_exclusions
            mock_load_exclusions.assert_called_once_with(dry_run=True)
            mock_echo.assert_any_call("0 | server1 | shadowsocks | 8080")
    
    def test_list_servers_empty_outbounds(self):
        """Test list_servers with empty outbounds."""
        json_data = {"outbounds": []}
        supported_protocols = ["shadowsocks", "vmess"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('typer.echo') as mock_echo:
            
            list_servers(json_data, supported_protocols)
            
            # Should still show header
            mock_echo.assert_any_call("Index | Name | Protocol | Port")
            mock_echo.assert_any_call("--------------------------------")
            
            # But no server entries
            echo_calls = [call[0][0] for call in mock_echo.call_args_list]
            server_calls = [call for call in echo_calls if " | " in call and "Index" not in call and "----" not in call]
            assert len(server_calls) == 0
    
    def test_list_servers_direct_array_format(self):
        """Test list_servers with direct array format (no outbounds key)."""
        json_data = [
            {
                "tag": "server1",
                "type": "shadowsocks",
                "server_port": 8080,
                "server": "1.1.1.1",
                "method": "chacha20-poly1305"
            }
        ]
        supported_protocols = ["shadowsocks"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"):
            
            # This should fail because list_servers expects dict with "outbounds" key
            with pytest.raises(AttributeError):
                list_servers(json_data, supported_protocols)
    
    def test_list_servers_complex_exclusions(self):
        """Test list_servers with complex exclusions structure."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                },
                {
                    "tag": "server2",
                    "type": "vmess",
                    "server_port": 443,
                    "server": "2.2.2.2"
                },
                {
                    "tag": "server3",
                    "type": "trojan",
                    "server_port": 443,
                    "server": "3.3.3.3"
                }
            ]
        }
        supported_protocols = ["shadowsocks", "vmess", "trojan"]
        exclusions = {
            "exclusions": [
                {"id": "excluded_id1"},
                {"id": "excluded_id3"}
            ]
        }
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value=exclusions), \
             patch('sboxmgr.server.selection.generate_server_id') as mock_gen_id, \
             patch('typer.echo') as mock_echo:
            
            mock_gen_id.side_effect = ["excluded_id1", "id2", "excluded_id3"]
            
            list_servers(json_data, supported_protocols)
            
            # Check exclusion markings
            mock_echo.assert_any_call("0 | server1 [excluded] | shadowsocks | 8080")
            mock_echo.assert_any_call("1 | server2 | vmess | 443")
            mock_echo.assert_any_call("2 | server3 [excluded] | trojan | 443")
    
    def test_list_servers_no_exclusions_key(self):
        """Test list_servers when exclusions data has no 'exclusions' key."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                }
            ]
        }
        supported_protocols = ["shadowsocks"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('typer.echo') as mock_echo:
            
            list_servers(json_data, supported_protocols)
            
            # Should handle missing exclusions key gracefully
            mock_echo.assert_any_call("0 | server1 | shadowsocks | 8080")


class TestListServersEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_list_servers_none_values(self):
        """Test list_servers handles None values gracefully."""
        json_data = {
            "outbounds": [
                {
                    "tag": None,
                    "type": "shadowsocks",
                    "server_port": None,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                }
            ]
        }
        supported_protocols = ["shadowsocks"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('typer.echo') as mock_echo:
            
            list_servers(json_data, supported_protocols)
            
            # Should handle None values by displaying them as "None"
            mock_echo.assert_any_call("0 | None | shadowsocks | None")
    
    def test_list_servers_empty_supported_protocols(self):
        """Test list_servers with empty supported protocols list."""
        json_data = {
            "outbounds": [
                {
                    "tag": "server1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                }
            ]
        }
        supported_protocols = []
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('typer.echo') as mock_echo:
            
            list_servers(json_data, supported_protocols)
            
            # Should show header but no servers
            mock_echo.assert_any_call("Index | Name | Protocol | Port")
            mock_echo.assert_any_call("--------------------------------")
            
            # No servers should be displayed
            echo_calls = [call[0][0] for call in mock_echo.call_args_list]
            server_calls = [call for call in echo_calls if " | " in call and "Index" not in call and "----" not in call]
            assert len(server_calls) == 0
    
    def test_list_servers_mixed_data_types(self):
        """Test list_servers with mixed data types in fields."""
        json_data = {
            "outbounds": [
                {
                    "tag": 123,  # Integer instead of string
                    "type": "shadowsocks",
                    "server_port": "8080",  # String instead of int
                    "server": "1.1.1.1",
                    "method": "chacha20-poly1305"
                }
            ]
        }
        supported_protocols = ["shadowsocks"]
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('typer.echo') as mock_echo:
            
            list_servers(json_data, supported_protocols)
            
            # Should handle mixed types gracefully
            mock_echo.assert_any_call("0 | 123 | shadowsocks | 8080")


class TestListServersIntegration:
    """Integration tests for list_servers."""
    
    def test_list_servers_realistic_scenario(self):
        """Test list_servers with realistic server configuration."""
        json_data = {
            "outbounds": [
                {
                    "tag": "US-Server-1",
                    "type": "shadowsocks",
                    "server_port": 8080,
                    "server": "us1.example.com",
                    "method": "chacha20-poly1305",
                    "password": "secret123"  # pragma: allowlist secret
                },
                {
                    "tag": "UK-Server-1", 
                    "type": "vmess",
                    "server_port": 443,
                    "server": "uk1.example.com",
                    "uuid": "12345678-1234-1234-1234-123456789abc",
                    "security": "auto"
                },
                {
                    "tag": "DE-Server-1",
                    "type": "trojan",
                    "server_port": 443,
                    "server": "de1.example.com",
                    "password": "trojan_pass"  # pragma: allowlist secret
                },
                {
                    "tag": "Unsupported-Server",
                    "type": "http",
                    "server_port": 8080,
                    "server": "proxy.example.com"
                }
            ]
        }
        supported_protocols = ["shadowsocks", "vmess", "trojan"]
        exclusions = {
            "exclusions": [
                {"id": "uk_server_id"}
            ]
        }
        
        with patch('sboxmgr.server.selection.load_exclusions', return_value=exclusions), \
             patch('sboxmgr.server.selection.generate_server_id') as mock_gen_id, \
             patch('typer.echo') as mock_echo:
            
            mock_gen_id.side_effect = ["us_server_id", "uk_server_id", "de_server_id", "http_server_id"]
            
            list_servers(json_data, supported_protocols, debug_level=1)
            
            # Check all expected servers are shown
            mock_echo.assert_any_call("0 | US-Server-1 | shadowsocks | 8080")
            mock_echo.assert_any_call("1 | UK-Server-1 [excluded] | vmess | 443")
            mock_echo.assert_any_call("2 | DE-Server-1 | trojan | 443")
            
            # Unsupported protocol should not appear
            echo_calls = [call[0][0] for call in mock_echo.call_args_list]
            assert not any("Unsupported-Server" in call for call in echo_calls)
            assert not any("http" in call for call in echo_calls)

        with patch('sboxmgr.server.selection.load_exclusions', return_value={"exclusions": []}), \
             patch('sboxmgr.server.selection.generate_server_id', return_value="id1"), \
             patch('logging.info') as mock_log:
            
            # Test with empty exclusions
            list_servers(json_data, supported_protocols)
            
            # Should have called generate_server_id for each server
            assert mock_gen_id.call_count == 2
            mock_log.assert_called() 