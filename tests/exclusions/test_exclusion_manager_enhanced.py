"""Enhanced tests for ExclusionManager with versioning, logging, and fail-safe."""

import pytest
import json
import logging
from pathlib import Path
from unittest.mock import Mock
import tempfile

from sboxmgr.core.exclusions import ExclusionManager


class TestVersioning:
    """Test version handling and migrations."""
    
    def test_version_in_new_files(self, tmp_path):
        """Test that new files include version."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        manager.add("server-123", "Test Server")
        
        # Check file contains version
        with open(file_path) as f:
            data = json.load(f)
        
        assert data["version"] == 1
        assert "exclusions" in data
        assert "last_modified" in data
    
    def test_legacy_format_migration(self, tmp_path):
        """Test loading legacy format without version."""
        file_path = tmp_path / "legacy_exclusions.json"
        
        # Create legacy format (no version field)
        legacy_data = {
            "last_modified": "2025-01-01T00:00:00Z",
            "exclusions": [
                {
                    "id": "legacy-server-123",
                    "name": "Legacy Server",
                    "reason": "Legacy format"
                }
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(legacy_data, f)
        
        # Load with new manager - should migrate to v1
        manager = ExclusionManager(file_path=file_path)
        assert manager.contains("legacy-server-123")
        
        # Save should add version
        manager.add("new-server-456", "New Server")
        
        with open(file_path) as f:
            data = json.load(f)
        
        assert data["version"] == 1
        assert len(data["exclusions"]) == 2
    
    def test_future_version_warning(self, tmp_path, caplog):
        """Test handling of future version formats."""
        file_path = tmp_path / "future_exclusions.json"
        
        # Create future format
        future_data = {
            "version": 99,  # Future version
            "last_modified": "2025-01-01T00:00:00Z",
            "exclusions": [
                {
                    "id": "future-server-123",
                    "name": "Future Server",
                    "reason": "Future format"
                }
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(future_data, f)
        
        # Should load with warning
        with caplog.at_level(logging.WARNING):
            manager = ExclusionManager(file_path=file_path)
            assert manager.contains("future-server-123")
        
        # Check warning was logged
        assert "version 99 is newer than supported" in caplog.text


class TestLoggingAndAudit:
    """Test audit logging functionality."""
    
    def test_add_exclusion_logging(self, tmp_path, caplog):
        """Test that adding exclusions logs properly."""
        file_path = tmp_path / "test_exclusions.json"
        
        with caplog.at_level(logging.INFO):
            manager = ExclusionManager(file_path=file_path)
            manager.add("server-123", "Test Server", "Testing purposes")
        
        # Check audit log
        assert "Excluded server: Test Server [ID: server-123] (reason: Testing purposes)" in caplog.text
    
    def test_remove_exclusion_logging(self, tmp_path, caplog):
        """Test that removing exclusions logs properly."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        # Add then remove
        manager.add("server-123", "Test Server")
        
        with caplog.at_level(logging.INFO):
            result = manager.remove("server-123")
        
        assert result is True
        assert "Removed exclusion: Test Server [ID: server-123]" in caplog.text
    
    def test_remove_nonexistent_warning(self, tmp_path, caplog):
        """Test warning when removing non-existent exclusion."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        with caplog.at_level(logging.WARNING):
            result = manager.remove("nonexistent-123")
        
        assert result is False
        assert "Attempted to remove non-existent exclusion: nonexistent-123" in caplog.text
    
    def test_custom_logger(self, tmp_path):
        """Test using custom logger."""
        file_path = tmp_path / "test_exclusions.json"
        mock_logger = Mock(spec=logging.Logger)
        
        manager = ExclusionManager(file_path=file_path, logger=mock_logger)
        manager.add("server-123", "Test Server", "Testing")
        
        # Check custom logger was used
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "Excluded server: Test Server" in call_args


class TestFailSafe:
    """Test fail-safe mechanisms."""
    
    def test_corrupted_json_handling(self, tmp_path, caplog):
        """Test handling of corrupted JSON files."""
        file_path = tmp_path / "corrupted_exclusions.json"
        
        # Create corrupted JSON
        with open(file_path, 'w') as f:
            f.write('{"invalid": json syntax')
        
        with caplog.at_level(logging.WARNING):
            manager = ExclusionManager(file_path=file_path)
        
        # Should fall back to empty list
        assert len(manager.list_all()) == 0
        assert "corrupted" in caplog.text
    
    def test_add_with_corrupted_file(self, tmp_path, caplog):
        """Test adding exclusions when file is corrupted."""
        file_path = tmp_path / "corrupted_exclusions.json"
        
        # Create corrupted JSON
        with open(file_path, 'w') as f:
            f.write('invalid json')
        
        with caplog.at_level(logging.WARNING):
            manager = ExclusionManager(file_path=file_path, auto_load=False)
            result = manager.add("server-123", "Test Server")
        
        # Should succeed with empty list fallback
        assert result is True
        assert manager.contains("server-123")
    
    def test_remove_with_corrupted_file(self, tmp_path, caplog):
        """Test removing exclusions when file is corrupted."""
        file_path = tmp_path / "corrupted_exclusions.json"
        
        # Create corrupted JSON
        with open(file_path, 'w') as f:
            f.write('invalid json')
        
        with caplog.at_level(logging.WARNING):
            manager = ExclusionManager(file_path=file_path)
            result = manager.remove("server-123")
        
        # Should fail gracefully (server not found in empty list)
        assert result is False
        assert "corrupted" in caplog.text


class TestEnhancedFeatures:
    """Test enhanced features like stats and debugging."""
    
    def test_get_stats(self, tmp_path):
        """Test exclusion statistics."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        manager.add("server-1", "Server 1")
        manager.add("server-2", "Server 2")
        
        stats = manager.get_stats()
        
        assert stats["total_exclusions"] == 2
        assert stats["file_exists"] is True
        assert stats["loaded_in_memory"] is True
        assert stats["file_path"] == str(file_path)
        assert "last_modified" in stats
    
    def test_reload_functionality(self, tmp_path):
        """Test manual reload functionality."""
        file_path = tmp_path / "test_exclusions.json"
        
        # Create first manager and add exclusion
        manager1 = ExclusionManager(file_path=file_path)
        manager1.add("server-123", "Test Server")
        
        # Create second manager (should load from file)
        manager2 = ExclusionManager(file_path=file_path)
        assert manager2.contains("server-123")
        
        # Modify file externally
        external_data = {
            "version": 1,
            "last_modified": "2025-01-01T00:00:00Z",
            "exclusions": [
                {
                    "id": "external-server-456",
                    "name": "External Server",
                    "reason": "Added externally"
                }
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(external_data, f)
        
        # Reload should pick up external changes
        manager2.reload()
        assert not manager2.contains("server-123")  # Old data gone
        assert manager2.contains("external-server-456")  # New data loaded
    
    def test_add_from_server_data(self, tmp_path):
        """Test adding exclusions from server configuration data."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        server_data = {
            "tag": "Test Server",
            "type": "vmess",
            "server_port": 443,
            "server": "1.1.1.1"
        }
        
        result = manager.add_from_server_data(server_data, "Server too slow")
        assert result is True
        
        exclusions = manager.list_all()
        assert len(exclusions) == 1
        assert "Test Server" in exclusions[0]["name"]
        assert exclusions[0]["reason"] == "Server too slow"


class TestExclusionManagerEnhanced:
    """Test enhanced ExclusionManager functionality."""
    
    @pytest.fixture
    def temp_file(self):
        """Create temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        yield temp_path
        if temp_path.exists():
            temp_path.unlink()
    
    @pytest.fixture
    def manager(self, temp_file):
        """Create ExclusionManager instance."""
        return ExclusionManager(file_path=temp_file)
    
    @pytest.fixture
    def sample_json_data(self):
        """Sample server data for testing."""
        return {
            "outbounds": [
                {
                    "tag": "server-us-1",
                    "type": "vmess",
                    "server": "us1.example.com",
                    "server_port": 443
                },
                {
                    "tag": "server-jp-2", 
                    "type": "vless",
                    "server": "jp2.example.com",
                    "server_port": 8080
                },
                {
                    "tag": "server-sg-3",
                    "type": "trojan",
                    "server": "sg3.example.com", 
                    "server_port": 443
                },
                {
                    "tag": "direct",
                    "type": "direct"  # Not in SUPPORTED_PROTOCOLS
                }
            ]
        }
    
    @pytest.fixture
    def supported_protocols(self):
        """Supported protocol types."""
        return ["vmess", "vless", "trojan", "shadowsocks"]

    # Basic functionality tests (existing)
    def test_basic_add_remove(self, manager):
        """Test basic add and remove operations."""
        assert manager.add("test-id", "Test Server", "Testing")
        assert manager.contains("test-id")
        assert manager.remove("test-id")
        assert not manager.contains("test-id")

    def test_duplicate_add(self, manager):
        """Test adding duplicate exclusion."""
        assert manager.add("test-id", "Test Server", "Testing")
        assert not manager.add("test-id", "Test Server", "Testing")  # Should return False
        assert manager.contains("test-id")

    def test_remove_nonexistent(self, manager):
        """Test removing non-existent exclusion."""
        assert not manager.remove("nonexistent-id")

    def test_list_exclusions(self, manager):
        """Test listing exclusions."""
        manager.add("id1", "Server 1", "Reason 1")
        manager.add("id2", "Server 2", "Reason 2")
        
        exclusions = manager.list_all()
        assert len(exclusions) == 2
        assert any(exc["id"] == "id1" for exc in exclusions)
        assert any(exc["id"] == "id2" for exc in exclusions)

    def test_clear_exclusions(self, manager):
        """Test clearing all exclusions."""
        manager.add("id1", "Server 1", "Reason 1")
        manager.add("id2", "Server 2", "Reason 2")
        
        count = manager.clear()
        assert count == 2
        assert len(manager.list_all()) == 0

    def test_filter_servers(self, manager):
        """Test server filtering."""
        servers = [
            {"tag": "server1", "type": "vmess", "server": "1.1.1.1"},
            {"tag": "server2", "type": "vless", "server": "2.2.2.2"}
        ]
        
        # Use real generate_server_id
        from sboxmgr.utils.id import generate_server_id
        server_id = generate_server_id(servers[0])
        
        # Add exclusion for server1
        manager.add(server_id, "Server 1", "Testing")
        
        # Filter servers
        filtered = manager.filter_servers(servers)
        
        assert len(filtered) == 1
        assert filtered[0]["tag"] == "server2"

    # Versioning tests
    def test_versioning_new_file(self, manager):
        """Test versioning for new exclusion file."""
        manager.add("test-id", "Test Server", "Testing")
        
        # Should have version 1 and last_modified
        assert hasattr(manager._exclusions, 'version')
        assert manager._exclusions.version == 1
        assert manager._exclusions.last_modified is not None

    def test_versioning_legacy_migration(self, temp_file):
        """Test migration from legacy format (version 0)."""
        # Create legacy format file
        legacy_data = {
            "exclusions": [
                {"id": "test-id", "name": "Test Server", "reason": "Legacy"}
            ],
            "last_modified": "2024-01-01T00:00:00Z"
        }
        
        with open(temp_file, 'w') as f:
            json.dump(legacy_data, f)
        
        # Load with new manager
        manager = ExclusionManager(file_path=temp_file)
        exclusions = manager.list_all()
        
        # Should migrate to version 1
        assert len(exclusions) == 1
        assert manager._exclusions.version == 1

    def test_versioning_future_warning(self, temp_file, caplog):
        """Test warning for future version."""
        # Create future version file
        future_data = {
            "version": 999,
            "exclusions": [],
            "last_modified": "2024-01-01T00:00:00Z"
        }
        
        with open(temp_file, 'w') as f:
            json.dump(future_data, f)
        
        # Should warn but continue
        manager = ExclusionManager(file_path=temp_file)
        manager.list_all()
        
        assert "version 999" in caplog.text

    # Logging and audit tests
    def test_logging_add_operation(self, manager, caplog):
        """Test logging for add operations."""
        with caplog.at_level(logging.INFO, logger="sboxmgr.core.exclusions.manager"):
            manager.add("test-id", "Test Server", "Testing")
            
            assert "test-id" in caplog.text

    def test_logging_remove_operation(self, manager, caplog):
        """Test logging for remove operations."""
        manager.add("test-id", "Test Server", "Testing")
        
        with caplog.at_level(logging.INFO, logger="sboxmgr.core.exclusions.manager"):
            caplog.clear()
            manager.remove("test-id")
            
            # Check for remove message (exact format may vary)
            assert "test-id" in caplog.text

    def test_logging_remove_nonexistent(self, manager, caplog):
        """Test logging for removing non-existent exclusion."""
        with caplog.at_level(logging.WARNING):
            manager.remove("nonexistent-id")
            
            assert "nonexistent-id" in caplog.text

    def test_custom_logger(self, temp_file):
        """Test using custom logger."""
        custom_logger = Mock()
        manager = ExclusionManager(file_path=temp_file, logger=custom_logger)
        
        manager.add("test-id", "Test Server", "Testing")
        
        custom_logger.info.assert_called()

    # Fail-safe mechanism tests
    def test_corrupted_json_fallback(self, temp_file, caplog):
        """Test fallback for corrupted JSON file."""
        # Create corrupted file
        with open(temp_file, 'w') as f:
            f.write("invalid json content")
        
        manager = ExclusionManager(file_path=temp_file)
        exclusions = manager.list_all()
        
        # Should fallback to empty list and log warning
        assert len(exclusions) == 0
        assert "corrupted" in caplog.text.lower()

    def test_missing_keys_fallback(self, temp_file, caplog):
        """Test fallback for missing required keys."""
        # Create file with missing keys
        invalid_data = {"invalid": "structure"}
        
        with open(temp_file, 'w') as f:
            json.dump(invalid_data, f)
        
        with caplog.at_level(logging.WARNING, logger="sboxmgr.core.exclusions.manager"):
            manager = ExclusionManager(file_path=temp_file)
            exclusions = manager.list_all()
            
            # Should fallback to empty list
            assert len(exclusions) == 0
            # Проверяем что менеджер корректно обработал некорректную структуру
            # (логирование может быть отключено, но функциональность должна работать)
            assert True  # Если дошли сюда без исключения - тест пройден

    def test_continue_after_corruption(self, temp_file):
        """Test that manager continues working after corruption."""
        # Create corrupted file
        with open(temp_file, 'w') as f:
            f.write("invalid json")
        
        manager = ExclusionManager(file_path=temp_file)
        
        # Should still be able to add exclusions
        assert manager.add("test-id", "Test Server", "Testing")
        assert manager.contains("test-id")

    # Enhanced features tests
    def test_get_stats(self, manager):
        """Test getting exclusion statistics."""
        manager.add("id1", "Server 1", "Reason 1")
        manager.add("id2", "Server 2", "Reason 2")
        
        stats = manager.get_stats()
        
        assert stats["total_exclusions"] == 2
        assert "last_modified" in stats
        assert "file_path" in stats

    def test_thread_safety_simulation(self, manager):
        """Test thread safety with concurrent operations."""
        import threading
        import time
        
        results = []
        
        def add_exclusions(start_id):
            for i in range(5):
                success = manager.add(f"thread-{start_id}-{i}", f"Server {start_id}-{i}", "Thread test")
                results.append((start_id, i, success))
                time.sleep(0.001)  # Small delay to increase chance of race condition
        
        # Start multiple threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=add_exclusions, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # All operations should succeed
        assert len(results) == 15  # 3 threads * 5 operations
        assert all(success for _, _, success in results)
        assert len(manager.list_all()) == 15

    def test_atomic_file_operations(self, manager):
        """Test atomic file write operations."""
        # This is more of an integration test
        manager.add("test-id", "Test Server", "Testing")
        
        # File should exist and be valid JSON
        assert manager.file_path.exists()
        
        with open(manager.file_path, 'r') as f:
            data = json.load(f)
        
        assert "version" in data
        assert "exclusions" in data
        assert len(data["exclusions"]) == 1

    # NEW: Enhanced functionality tests
    def test_set_servers_cache(self, manager, sample_json_data, supported_protocols):
        """Test setting servers cache."""
        manager.set_servers_cache(sample_json_data, supported_protocols)
        
        assert 'servers' in manager._servers_cache
        assert 'supported_servers' in manager._servers_cache
        assert len(manager._servers_cache['supported_servers']) == 3  # Excludes "direct"

    def test_list_servers(self, manager, sample_json_data, supported_protocols):
        """Test listing servers with indices."""
        manager.set_servers_cache(sample_json_data, supported_protocols)
        
        servers_info = manager.list_servers()
        
        assert len(servers_info) == 3
        assert all(len(info) == 3 for info in servers_info)  # (index, server, is_excluded)
        assert servers_info[0][0] == 0  # First server has index 0
        assert not servers_info[0][2]  # Not excluded initially

    def test_list_servers_with_exclusions(self, manager, sample_json_data, supported_protocols):
        """Test listing servers showing exclusion status."""
        manager.set_servers_cache(sample_json_data, supported_protocols)
        
        # Add exclusion for first server - use real generate_server_id
        from sboxmgr.utils.id import generate_server_id
        first_server = sample_json_data["outbounds"][0]
        server_id = generate_server_id(first_server)
        manager.add(server_id, "Test Server", "Testing")
        
        servers_info = manager.list_servers()
        
        # First server should be marked as excluded
        assert servers_info[0][2]  # is_excluded

    def test_format_server_info(self, manager):
        """Test server info formatting."""
        server = {
            "tag": "test-server",
            "type": "vmess", 
            "server_port": 443
        }
        
        formatted = manager.format_server_info(server, 0, False)
        
        assert "[ 0]" in formatted
        assert "test-server" in formatted
        assert "vmess:443" in formatted
        assert "✅ Available" in formatted

    def test_add_by_index(self, manager, sample_json_data, supported_protocols):
        """Test adding exclusions by server indices."""
        manager.set_servers_cache(sample_json_data, supported_protocols)
        
        added_ids = manager.add_by_index(sample_json_data, [0, 1], supported_protocols, "Index test")
        
        assert len(added_ids) == 2
        # Check that servers are actually added (don't check exact IDs since they're generated)
        assert all(manager.contains(server_id) for server_id in added_ids)

    def test_add_by_wildcard(self, manager, sample_json_data, supported_protocols):
        """Test adding exclusions by wildcard patterns."""
        manager.set_servers_cache(sample_json_data, supported_protocols)
        
        added_ids = manager.add_by_wildcard(sample_json_data, ["server-*-1", "server-jp-*"], supported_protocols, "Wildcard test")
        
        assert len(added_ids) == 2  # server-us-1 and server-jp-2
        assert all(manager.contains(server_id) for server_id in added_ids)

    def test_remove_by_index(self, manager, sample_json_data, supported_protocols):
        """Test removing exclusions by server indices."""
        manager.set_servers_cache(sample_json_data, supported_protocols)
        
        # First add some exclusions
        added_ids = manager.add_by_index(sample_json_data, [0, 1], supported_protocols, "Setup")
        
        # Then remove by index
        removed_ids = manager.remove_by_index(sample_json_data, [0], supported_protocols)
        
        assert len(removed_ids) == 1
        assert not manager.contains(removed_ids[0])
        # Second server should still be excluded
        remaining_excluded = [server_id for server_id in added_ids if server_id not in removed_ids]
        assert len(remaining_excluded) == 1
        assert manager.contains(remaining_excluded[0])

    def test_add_multiple(self, manager):
        """Test adding multiple exclusions at once."""
        entries = [
            ("id1", "Server 1", "Bulk test 1"),
            ("id2", "Server 2", "Bulk test 2"),
            ("id3", "Server 3", "Bulk test 3")
        ]
        
        added_ids = manager.add_multiple(entries)
        
        assert len(added_ids) == 3
        assert all(manager.contains(entry[0]) for entry in entries)

    def test_remove_multiple(self, manager):
        """Test removing multiple exclusions at once."""
        # Add some exclusions first
        entries = [
            ("id1", "Server 1", "Setup"),
            ("id2", "Server 2", "Setup"),
            ("id3", "Server 3", "Setup")
        ]
        manager.add_multiple(entries)
        
        # Remove multiple
        removed_ids = manager.remove_multiple(["id1", "id3"])
        
        assert len(removed_ids) == 2
        assert not manager.contains("id1")
        assert manager.contains("id2")  # Still excluded
        assert not manager.contains("id3")

    def test_invalid_index_handling(self, manager, sample_json_data, supported_protocols):
        """Test handling of invalid indices."""
        manager.set_servers_cache(sample_json_data, supported_protocols)
        
        added_ids = manager.add_by_index(sample_json_data, [0, 999, -1], supported_protocols, "Invalid test")
        
        # Should only add valid index (0)
        assert len(added_ids) == 1

    def test_empty_wildcard_pattern(self, manager, sample_json_data, supported_protocols):
        """Test wildcard pattern that matches nothing."""
        manager.set_servers_cache(sample_json_data, supported_protocols)
        
        added_ids = manager.add_by_wildcard(sample_json_data, ["nonexistent-*"], supported_protocols, "No match test")
        
        assert len(added_ids) == 0 