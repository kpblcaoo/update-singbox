import pytest
import json
from unittest.mock import patch
from sboxmgr.server.state import load_selected_config, save_selected_config


class TestLoadSelectedConfig:
    """Test load_selected_config function."""
    
    def test_load_selected_config_file_exists_valid_json(self, tmp_path):
        """Test loading valid JSON from existing file."""
        config_file = tmp_path / "selected.json"
        test_data = {"selected": ["server1", "server2"]}
        
        # Create test file
        with open(config_file, "w") as f:
            json.dump(test_data, f)
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            result = load_selected_config()
        
        assert result == test_data
    
    def test_load_selected_config_file_exists_invalid_json(self, tmp_path):
        """Test loading invalid JSON from existing file."""
        config_file = tmp_path / "selected.json"
        
        # Create invalid JSON file
        config_file.write_text("{ invalid json content")
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('logging.error') as mock_error:
            
            result = load_selected_config()
        
        assert result == {"selected": []}
        mock_error.assert_called_once()
        assert "повреждён или невалиден" in mock_error.call_args[0][0]
        assert str(config_file) in mock_error.call_args[0][0]
    
    def test_load_selected_config_file_not_exists(self, tmp_path):
        """Test loading when file doesn't exist."""
        config_file = tmp_path / "nonexistent.json"
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            result = load_selected_config()
        
        assert result == {"selected": []}
    
    def test_load_selected_config_empty_file(self, tmp_path):
        """Test loading empty file."""
        config_file = tmp_path / "empty.json"
        config_file.write_text("")
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('logging.error') as mock_error:
            
            result = load_selected_config()
        
        assert result == {"selected": []}
        mock_error.assert_called_once()
    
    def test_load_selected_config_complex_data(self, tmp_path):
        """Test loading complex configuration data."""
        config_file = tmp_path / "complex.json"
        test_data = {
            "selected": [
                {
                    "id": "server1",
                    "type": "vless",
                    "server": "example1.com",
                    "port": 443
                },
                {
                    "id": "server2", 
                    "type": "shadowsocks",
                    "server": "example2.com",
                    "port": 8080
                }
            ],
            "metadata": {
                "last_updated": "2024-01-01T00:00:00Z",
                "version": "1.0"
            }
        }
        
        with open(config_file, "w") as f:
            json.dump(test_data, f)
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            result = load_selected_config()
        
        assert result == test_data
        assert len(result["selected"]) == 2
        assert result["metadata"]["version"] == "1.0"
    
    def test_load_selected_config_file_permissions_error(self, tmp_path):
        """Test loading when file has permission issues."""
        config_file = tmp_path / "permission_denied.json"
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('sboxmgr.server.state.file_exists', return_value=True), \
             patch('sboxmgr.server.state.read_json', side_effect=PermissionError("Permission denied")):
            
            # Should propagate the PermissionError since it's not JSONDecodeError
            with pytest.raises(PermissionError):
                load_selected_config()


class TestSaveSelectedConfig:
    """Test save_selected_config function."""
    
    def test_save_selected_config_default_file(self, tmp_path):
        """Test saving with default config file path."""
        config_file = tmp_path / "default.json"
        test_data = {"selected": ["server1", "server2"]}
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('sboxmgr.server.state.atomic_write_json') as mock_write:
            
            save_selected_config(test_data)
        
        mock_write.assert_called_once_with(test_data, str(config_file))
    
    def test_save_selected_config_custom_file(self, tmp_path):
        """Test saving with custom config file path."""
        custom_file = tmp_path / "custom.json"
        test_data = {"selected": ["custom_server"]}
        
        with patch('sboxmgr.server.state.atomic_write_json') as mock_write:
            save_selected_config(test_data, str(custom_file))
        
        mock_write.assert_called_once_with(test_data, str(custom_file))
    
    def test_save_selected_config_empty_data(self, tmp_path):
        """Test saving empty configuration."""
        config_file = tmp_path / "empty.json"
        test_data = {"selected": []}
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('sboxmgr.server.state.atomic_write_json') as mock_write:
            
            save_selected_config(test_data)
        
        mock_write.assert_called_once_with(test_data, str(config_file))
    
    def test_save_selected_config_complex_data(self, tmp_path):
        """Test saving complex configuration data."""
        config_file = tmp_path / "complex.json"
        test_data = {
            "selected": [
                {
                    "id": "server1",
                    "type": "vless", 
                    "server": "example.com",
                    "port": 443,
                    "tls": {"enabled": True}
                }
            ],
            "metadata": {
                "created": "2024-01-01T00:00:00Z",
                "source": "subscription"
            }
        }
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('sboxmgr.server.state.atomic_write_json') as mock_write:
            
            save_selected_config(test_data)
        
        mock_write.assert_called_once_with(test_data, str(config_file))
    
    def test_save_selected_config_none_data(self, tmp_path):
        """Test saving None data."""
        config_file = tmp_path / "none.json"
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('sboxmgr.server.state.atomic_write_json') as mock_write:
            
            save_selected_config(None)
        
        mock_write.assert_called_once_with(None, str(config_file))
    
    def test_save_selected_config_write_error_propagation(self, tmp_path):
        """Test that write errors are properly propagated."""
        config_file = tmp_path / "error.json"
        test_data = {"selected": ["server1"]}
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('sboxmgr.server.state.atomic_write_json', side_effect=OSError("Disk full")):
            
            with pytest.raises(OSError, match="Disk full"):
                save_selected_config(test_data)


class TestServerStateIntegration:
    """Integration tests for server state management."""
    
    def test_load_save_roundtrip(self, tmp_path):
        """Test complete load-save roundtrip."""
        config_file = tmp_path / "roundtrip.json"
        original_data = {
            "selected": [
                {"id": "server1", "type": "vless"},
                {"id": "server2", "type": "shadowsocks"}
            ]
        }
        
        # Save data
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            save_selected_config(original_data)
        
        # Verify file was created
        assert config_file.exists()
        
        # Load data back
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            loaded_data = load_selected_config()
        
        assert loaded_data == original_data
    
    def test_load_save_with_real_files(self, tmp_path):
        """Test with real file operations (no mocking atomic_write_json)."""
        config_file = tmp_path / "real.json"
        test_data = {"selected": ["real_server"]}
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            # Save using real atomic_write_json
            save_selected_config(test_data)
            
            # Verify file exists and has correct content
            assert config_file.exists()
            with open(config_file) as f:
                file_content = json.load(f)
            assert file_content == test_data
            
            # Load using real file operations
            loaded_data = load_selected_config()
            assert loaded_data == test_data
    
    def test_load_corrupted_then_save_new(self, tmp_path):
        """Test loading corrupted file then saving new data."""
        config_file = tmp_path / "corrupted.json"
        
        # Create corrupted file
        config_file.write_text("{ corrupted json")
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('logging.error'):
            
            # Load should return default
            loaded_data = load_selected_config()
            assert loaded_data == {"selected": []}
            
            # Save new data
            new_data = {"selected": ["recovered_server"]}
            save_selected_config(new_data)
            
            # Should be able to load new data
            loaded_again = load_selected_config()
            assert loaded_again == new_data
    
    def test_multiple_save_operations(self, tmp_path):
        """Test multiple consecutive save operations."""
        config_file = tmp_path / "multiple.json"
        
        datasets = [
            {"selected": ["server1"]},
            {"selected": ["server1", "server2"]},
            {"selected": []},
            {"selected": ["final_server"], "metadata": {"version": "2.0"}}
        ]
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            for i, data in enumerate(datasets):
                save_selected_config(data)
                
                # Verify each save
                loaded = load_selected_config()
                assert loaded == data, f"Failed at iteration {i}"
    
    def test_concurrent_access_simulation(self, tmp_path):
        """Test simulation of concurrent access patterns."""
        config_file = tmp_path / "concurrent.json"
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            # Simulate multiple processes accessing the file
            initial_data = {"selected": ["initial"]}
            save_selected_config(initial_data)
            
            # Load from multiple "processes" - each starts fresh
            for i in range(5):
                # Reset to initial state for each "process" simulation
                save_selected_config(initial_data)
                loaded = load_selected_config()
                assert loaded == initial_data
                
                # Each "process" adds its own server
                new_data = {"selected": loaded["selected"] + [f"server_{i}"]}
                save_selected_config(new_data)
                
                # Verify the save
                final_loaded = load_selected_config()
                assert f"server_{i}" in final_loaded["selected"]
                assert len(final_loaded["selected"]) == 2  # initial + server_i


class TestServerStateEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_load_selected_config_various_json_errors(self, tmp_path):
        """Test various types of JSON decode errors."""
        test_cases = [
            ("{ incomplete", "Incomplete JSON object"),
            ("[1, 2, 3,]", "Trailing comma"),
            ('{"key": undefined}', "Undefined value"),
            ("", "Empty file"),
            ("not json at all", "Not JSON")
        ]
        
        for invalid_content, description in test_cases:
            config_file = tmp_path / f"invalid_{len(invalid_content)}.json"
            config_file.write_text(invalid_content)
            
            with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
                 patch('logging.error') as mock_error:
                
                result = load_selected_config()
                
                assert result == {"selected": []}, f"Failed for case: {description}"
                mock_error.assert_called_once()
    
    def test_save_selected_config_with_none_file_path(self):
        """Test save_selected_config when get_selected_config_file returns None."""
        test_data = {"selected": ["test"]}
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=None), \
             patch('sboxmgr.server.state.atomic_write_json') as mock_write:
            
            save_selected_config(test_data)
        
        mock_write.assert_called_once_with(test_data, None)
    
    def test_load_selected_config_file_exists_returns_false_positive(self, tmp_path):
        """Test when file_exists returns True but file is actually missing."""
        config_file = tmp_path / "false_positive.json"
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('sboxmgr.server.state.file_exists', return_value=True), \
             patch('sboxmgr.server.state.read_json', side_effect=FileNotFoundError("File not found")):
            
            # Should propagate FileNotFoundError since it's not JSONDecodeError
            with pytest.raises(FileNotFoundError):
                load_selected_config()
    
    def test_save_selected_config_special_characters(self, tmp_path):
        """Test saving data with special characters and unicode."""
        config_file = tmp_path / "unicode.json"
        test_data = {
            "selected": ["сервер_русский", "服务器_中文", "サーバー_日本語"],
            "description": "Test with émojis 🚀 and spëcial chars"
        }
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)), \
             patch('sboxmgr.server.state.atomic_write_json') as mock_write:
            
            save_selected_config(test_data)
        
        mock_write.assert_called_once_with(test_data, str(config_file))
    
    def test_load_selected_config_very_large_file(self, tmp_path):
        """Test loading very large configuration file."""
        config_file = tmp_path / "large.json"
        
        # Create large dataset
        large_data = {
            "selected": [f"server_{i}" for i in range(1000)],
            "metadata": {f"key_{i}": f"value_{i}" for i in range(100)}
        }
        
        with open(config_file, "w") as f:
            json.dump(large_data, f)
        
        with patch('sboxmgr.server.state.get_selected_config_file', return_value=str(config_file)):
            result = load_selected_config()
        
        assert len(result["selected"]) == 1000
        assert len(result["metadata"]) == 100
        assert result["selected"][0] == "server_0"
        assert result["selected"][-1] == "server_999"
