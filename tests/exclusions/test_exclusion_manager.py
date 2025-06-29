"""Tests for the new ExclusionManager architecture."""

import json
from unittest.mock import patch

from sboxmgr.core.exclusions import ExclusionManager, ExclusionEntry, ExclusionList


class TestExclusionManager:
    """Test ExclusionManager functionality."""
    
    def test_manager_initialization(self, tmp_path):
        """Test ExclusionManager initialization."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        assert manager.file_path == file_path
        assert manager.is_loaded()
        assert len(manager.list_all()) == 0
    
    def test_add_and_contains(self, tmp_path):
        """Test adding exclusions and checking containment."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        # Add exclusion
        result = manager.add("server-123", "Test Server", "Testing")
        assert result is True
        assert manager.contains("server-123")
        
        # Try to add same exclusion again
        result = manager.add("server-123", "Test Server", "Testing")
        assert result is False
        
        # Check file was created
        assert file_path.exists()
    
    def test_remove_exclusion(self, tmp_path):
        """Test removing exclusions."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        # Add and then remove
        manager.add("server-123", "Test Server")
        assert manager.contains("server-123")
        
        result = manager.remove("server-123")
        assert result is True
        assert not manager.contains("server-123")
        
        # Try to remove non-existent
        result = manager.remove("server-456")
        assert result is False
    
    def test_clear_exclusions(self, tmp_path):
        """Test clearing all exclusions."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        # Add multiple exclusions
        manager.add("server-1", "Server 1")
        manager.add("server-2", "Server 2")
        assert len(manager.list_all()) == 2
        
        # Clear all
        count = manager.clear()
        assert count == 2
        assert len(manager.list_all()) == 0
    
    def test_filter_servers(self, tmp_path):
        """Test filtering servers by exclusions."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        # Mock server data
        servers = [
            {"tag": "Server1", "type": "vmess", "server_port": 443, "server": "1.1.1.1"},
            {"tag": "Server2", "type": "vmess", "server_port": 443, "server": "2.2.2.2"},
            {"tag": "Server3", "type": "vmess", "server_port": 443, "server": "3.3.3.3"},
        ]
        
        # Add exclusion for first server
        from sboxmgr.utils.id import generate_server_id
        server1_id = generate_server_id(servers[0])
        manager.add(server1_id, "Server1 excluded")
        
        # Filter servers
        filtered = manager.filter_servers(servers)
        assert len(filtered) == 2
        assert filtered[0]["tag"] == "Server2"
        assert filtered[1]["tag"] == "Server3"
    
    def test_persistence_and_reload(self, tmp_path):
        """Test data persistence and reloading."""
        file_path = tmp_path / "test_exclusions.json"
        
        # Create manager and add exclusion
        manager1 = ExclusionManager(file_path=file_path)
        manager1.add("server-123", "Test Server")
        
        # Create new manager instance (should load from file)
        manager2 = ExclusionManager(file_path=file_path)
        assert manager2.contains("server-123")
        
        # Test reload
        manager1.clear()
        manager2.reload()
        assert not manager2.contains("server-123")
    
    def test_backward_compatibility(self, tmp_path):
        """Test loading old format exclusions."""
        file_path = tmp_path / "old_exclusions.json"
        
        # Create old format file
        old_data = {
            "last_modified": "2025-01-01T00:00:00Z",
            "exclusions": [
                {
                    "id": "old-server-123",
                    "name": "Old Server",
                    "reason": "Legacy format"
                }
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(old_data, f)
        
        # Load with new manager
        manager = ExclusionManager(file_path=file_path)
        assert manager.contains("old-server-123")
        exclusions = manager.list_all()
        assert len(exclusions) == 1
        assert exclusions[0]["name"] == "Old Server"
    
    def test_default_singleton(self):
        """Test default singleton pattern."""
        # Reset singleton before test
        ExclusionManager._default_instance = None
        
        # Mock get_exclusion_file to return consistent path
        with patch('sboxmgr.utils.env.get_exclusion_file') as mock_get_path:
            mock_get_path.return_value = "/test/path/exclusions.json"
            
            manager1 = ExclusionManager.default()
            manager2 = ExclusionManager.default()
            
            # Same instance if same path
            assert manager1 is manager2  # Same instance
            
            # Test that different paths create different instances
            # This tests the new behavior where singleton respects env changes
            mock_get_path.return_value = "/different/path/exclusions.json"
            manager3 = ExclusionManager.default()
            assert manager3 is not manager1  # Different instance for different path
    
    def test_stats(self, tmp_path):
        """Test exclusion statistics."""
        file_path = tmp_path / "test_exclusions.json"
        manager = ExclusionManager(file_path=file_path)
        
        manager.add("server-1", "Server 1")
        manager.add("server-2", "Server 2")
        
        stats = manager.get_stats()
        assert stats["total_exclusions"] == 2
        assert stats["file_exists"] is True
        assert stats["loaded_in_memory"] is True
        assert "last_modified" in stats


class TestExclusionModels:
    """Test exclusion data models."""
    
    def test_exclusion_entry(self):
        """Test ExclusionEntry model."""
        entry = ExclusionEntry(
            id="test-123",
            name="Test Server",
            reason="Testing"
        )
        
        # Test serialization
        data = entry.to_dict()
        assert data["id"] == "test-123"
        assert data["name"] == "Test Server"
        assert data["reason"] == "Testing"
        assert "timestamp" in data
        
        # Test deserialization
        entry2 = ExclusionEntry.from_dict(data)
        assert entry2.id == entry.id
        assert entry2.name == entry.name
        assert entry2.reason == entry.reason
    
    def test_exclusion_list(self):
        """Test ExclusionList model."""
        exclusion_list = ExclusionList()
        
        entry1 = ExclusionEntry(id="server-1", name="Server 1")
        entry2 = ExclusionEntry(id="server-2", name="Server 2")
        
        # Test adding
        assert exclusion_list.add(entry1) is True
        assert exclusion_list.add(entry2) is True
        assert exclusion_list.add(entry1) is False  # Duplicate
        
        # Test contains
        assert exclusion_list.contains("server-1") is True
        assert exclusion_list.contains("server-3") is False
        
        # Test get_ids
        ids = exclusion_list.get_ids()
        assert ids == {"server-1", "server-2"}
        
        # Test serialization
        data = exclusion_list.to_dict()
        assert len(data["exclusions"]) == 2
        assert "last_modified" in data
        
        # Test deserialization
        exclusion_list2 = ExclusionList.from_dict(data)
        assert len(exclusion_list2.exclusions) == 2
        assert exclusion_list2.contains("server-1") 