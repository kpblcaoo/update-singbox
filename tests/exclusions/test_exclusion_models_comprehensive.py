#!/usr/bin/env python3
"""Comprehensive tests for exclusion models to kill all mutations."""

from datetime import datetime, timezone, timedelta

from sboxmgr.core.exclusions.models import ExclusionEntry, ExclusionList


class TestExclusionEntryMutationKillers:
    """Comprehensive tests to kill all mutations in ExclusionEntry."""
    
    def test_exclusion_entry_creation_all_fields(self):
        """Test creation with all possible field combinations."""
        # Test with all fields
        timestamp = datetime.now(timezone.utc)
        entry = ExclusionEntry(
            id="test-123",
            name="Test Server",
            reason="Testing all fields",
            timestamp=timestamp
        )
        
        assert entry.id == "test-123"
        assert entry.name == "Test Server"
        assert entry.reason == "Testing all fields"
        assert entry.timestamp == timestamp
        
        # Test with minimal fields
        entry_minimal = ExclusionEntry(id="minimal")
        assert entry_minimal.id == "minimal"
        assert entry_minimal.name is None
        assert entry_minimal.reason is None
        assert isinstance(entry_minimal.timestamp, datetime)
        
        # Test with partial fields
        entry_partial = ExclusionEntry(id="partial", name="Partial Name")
        assert entry_partial.id == "partial"
        assert entry_partial.name == "Partial Name"
        assert entry_partial.reason is None
    
    def test_to_dict_serialization_edge_cases(self):
        """Test to_dict with various edge cases."""
        # Test with None values
        entry_none = ExclusionEntry(id="test", name=None, reason=None)
        data = entry_none.to_dict()
        assert data["id"] == "test"
        assert data["name"] is None
        assert data["reason"] is None
        assert data["timestamp"].endswith("Z")
        
        # Test with empty strings
        entry_empty = ExclusionEntry(id="test", name="", reason="")
        data = entry_empty.to_dict()
        assert data["name"] == ""
        assert data["reason"] == ""
        
        # Test with special characters
        entry_special = ExclusionEntry(
            id="test-special-!@#$%^&*()",
            name="Name with 中文 and émojis 🚀",
            reason="Reason with\nnewlines\tand\ttabs"
        )
        data = entry_special.to_dict()
        assert data["id"] == "test-special-!@#$%^&*()"
        assert "中文" in data["name"]
        assert "🚀" in data["name"]
        assert "\n" in data["reason"]
        assert "\t" in data["reason"]
    
    def test_from_dict_deserialization_edge_cases(self):
        """Test from_dict with various input formats and edge cases."""
        # Test with minimal data
        minimal_data = {"id": "minimal-test"}
        entry = ExclusionEntry.from_dict(minimal_data)
        assert entry.id == "minimal-test"
        assert entry.name is None
        assert entry.reason is None
        assert isinstance(entry.timestamp, datetime)
        
        # Test with ISO timestamp (Z format)
        iso_data = {
            "id": "iso-test",
            "name": "ISO Test",
            "reason": "Testing ISO",
            "timestamp": "2025-01-15T10:30:45Z"
        }
        entry = ExclusionEntry.from_dict(iso_data)
        assert entry.timestamp.year == 2025
        assert entry.timestamp.month == 1
        assert entry.timestamp.day == 15
        assert entry.timestamp.hour == 10
        assert entry.timestamp.minute == 30
        assert entry.timestamp.second == 45
        
        # Test with +00:00 format timestamp
        plus_data = {
            "id": "plus-test",
            "timestamp": "2025-01-15T10:30:45+00:00"
        }
        entry = ExclusionEntry.from_dict(plus_data)
        assert entry.timestamp.year == 2025
        
        # Test with invalid timestamp string
        invalid_ts_data = {
            "id": "invalid-ts",
            "timestamp": "not-a-timestamp"
        }
        entry = ExclusionEntry.from_dict(invalid_ts_data)
        assert isinstance(entry.timestamp, datetime)
        # Should fallback to now()
        assert entry.timestamp.year >= 2025
        
        # Test with non-string timestamp
        non_string_ts_data = {
            "id": "non-string-ts",
            "timestamp": 1234567890
        }
        entry = ExclusionEntry.from_dict(non_string_ts_data)
        assert isinstance(entry.timestamp, datetime)
        
        # Test with empty timestamp
        empty_ts_data = {
            "id": "empty-ts",
            "timestamp": ""
        }
        entry = ExclusionEntry.from_dict(empty_ts_data)
        assert isinstance(entry.timestamp, datetime)
        
        # Test with None timestamp
        none_ts_data = {
            "id": "none-ts",
            "timestamp": None
        }
        entry = ExclusionEntry.from_dict(none_ts_data)
        assert isinstance(entry.timestamp, datetime)


class TestExclusionListMutationKillers:
    """Comprehensive tests to kill all mutations in ExclusionList."""
    
    def test_exclusion_list_initialization(self):
        """Test all initialization scenarios."""
        # Default initialization
        list_default = ExclusionList()
        assert len(list_default.exclusions) == 0
        assert isinstance(list_default.last_modified, datetime)
        assert list_default.version == 1
        
        # With custom data
        entries = [ExclusionEntry(id="test1"), ExclusionEntry(id="test2")]
        custom_time = datetime.now(timezone.utc) - timedelta(hours=1)
        list_custom = ExclusionList(
            exclusions=entries,
            last_modified=custom_time,
            version=2
        )
        assert len(list_custom.exclusions) == 2
        assert list_custom.last_modified == custom_time
        assert list_custom.version == 2
    
    def test_add_method_all_scenarios(self):
        """Test add method with all possible scenarios."""
        exclusion_list = ExclusionList()
        original_time = exclusion_list.last_modified
        
        # Add first entry
        entry1 = ExclusionEntry(id="server-1", name="Server 1")
        result = exclusion_list.add(entry1)
        assert result is True
        assert len(exclusion_list.exclusions) == 1
        assert exclusion_list.last_modified > original_time
        
        # Add second entry
        entry2 = ExclusionEntry(id="server-2", name="Server 2")
        result = exclusion_list.add(entry2)
        assert result is True
        assert len(exclusion_list.exclusions) == 2
        
        # Try to add duplicate (same ID)
        entry1_duplicate = ExclusionEntry(id="server-1", name="Different Name")
        result = exclusion_list.add(entry1_duplicate)
        assert result is False
        assert len(exclusion_list.exclusions) == 2  # No change
        
        # Verify the original entry wasn't modified
        found_entry = next(ex for ex in exclusion_list.exclusions if ex.id == "server-1")
        assert found_entry.name == "Server 1"  # Original name preserved
        
        # Add entry with None name and reason
        entry_none = ExclusionEntry(id="server-none", name=None, reason=None)
        result = exclusion_list.add(entry_none)
        assert result is True
        assert len(exclusion_list.exclusions) == 3
        
        # Add entry with empty strings
        entry_empty = ExclusionEntry(id="server-empty", name="", reason="")
        result = exclusion_list.add(entry_empty)
        assert result is True
        assert len(exclusion_list.exclusions) == 4
    
    def test_remove_method_all_scenarios(self):
        """Test remove method with all possible scenarios."""
        exclusion_list = ExclusionList()
        
        # Add test entries
        entry1 = ExclusionEntry(id="server-1")
        entry2 = ExclusionEntry(id="server-2")
        entry3 = ExclusionEntry(id="server-3")
        exclusion_list.add(entry1)
        exclusion_list.add(entry2)
        exclusion_list.add(entry3)
        
        original_count = len(exclusion_list.exclusions)
        original_time = exclusion_list.last_modified
        
        # Remove existing entry
        result = exclusion_list.remove("server-2")
        assert result is True
        assert len(exclusion_list.exclusions) == original_count - 1
        assert exclusion_list.last_modified > original_time
        
        # Verify correct entry was removed
        remaining_ids = {ex.id for ex in exclusion_list.exclusions}
        assert remaining_ids == {"server-1", "server-3"}
        
        # Try to remove non-existent entry
        result = exclusion_list.remove("server-nonexistent")
        assert result is False
        assert len(exclusion_list.exclusions) == 2  # No change
        
        # Remove another existing entry
        result = exclusion_list.remove("server-1")
        assert result is True
        assert len(exclusion_list.exclusions) == 1
        
        # Remove last entry
        result = exclusion_list.remove("server-3")
        assert result is True
        assert len(exclusion_list.exclusions) == 0
        
        # Try to remove from empty list
        result = exclusion_list.remove("server-1")
        assert result is False
        assert len(exclusion_list.exclusions) == 0
        
        # Test with special characters in ID
        special_entry = ExclusionEntry(id="server-!@#$%^&*()")
        exclusion_list.add(special_entry)
        result = exclusion_list.remove("server-!@#$%^&*()")
        assert result is True
        assert len(exclusion_list.exclusions) == 0
    
    def test_contains_method_all_scenarios(self):
        """Test contains method with all possible scenarios."""
        exclusion_list = ExclusionList()
        
        # Test empty list
        assert exclusion_list.contains("any-id") is False
        
        # Add entries
        entry1 = ExclusionEntry(id="server-1")
        entry2 = ExclusionEntry(id="server-2")
        exclusion_list.add(entry1)
        exclusion_list.add(entry2)
        
        # Test existing entries
        assert exclusion_list.contains("server-1") is True
        assert exclusion_list.contains("server-2") is True
        
        # Test non-existing entries
        assert exclusion_list.contains("server-3") is False
        assert exclusion_list.contains("") is False
        assert exclusion_list.contains("server-") is False
        assert exclusion_list.contains("1") is False
        
        # Test with special characters
        special_entry = ExclusionEntry(id="server-!@#$%^&*()")
        exclusion_list.add(special_entry)
        assert exclusion_list.contains("server-!@#$%^&*()") is True
        assert exclusion_list.contains("server-!@#$%^&*()x") is False
        
        # Test case sensitivity
        case_entry = ExclusionEntry(id="CaseSensitive")
        exclusion_list.add(case_entry)
        assert exclusion_list.contains("CaseSensitive") is True
        assert exclusion_list.contains("casesensitive") is False
        assert exclusion_list.contains("CASESENSITIVE") is False
    
    def test_clear_method_all_scenarios(self):
        """Test clear method with all possible scenarios."""
        exclusion_list = ExclusionList()
        
        # Clear empty list
        count = exclusion_list.clear()
        assert count == 0
        assert len(exclusion_list.exclusions) == 0
        
        # Add entries and clear
        entries = [
            ExclusionEntry(id="server-1"),
            ExclusionEntry(id="server-2"),
            ExclusionEntry(id="server-3")
        ]
        for entry in entries:
            exclusion_list.add(entry)
        
        original_time = exclusion_list.last_modified
        count = exclusion_list.clear()
        assert count == 3
        assert len(exclusion_list.exclusions) == 0
        assert exclusion_list.last_modified > original_time
        
        # Clear already empty list
        count = exclusion_list.clear()
        assert count == 0
        assert len(exclusion_list.exclusions) == 0
        
        # Test with single entry
        single_entry = ExclusionEntry(id="single")
        exclusion_list.add(single_entry)
        count = exclusion_list.clear()
        assert count == 1
        assert len(exclusion_list.exclusions) == 0
    
    def test_get_ids_method_all_scenarios(self):
        """Test get_ids method with all possible scenarios."""
        exclusion_list = ExclusionList()
        
        # Empty list
        ids = exclusion_list.get_ids()
        assert ids == set()
        assert isinstance(ids, set)
        
        # Single entry
        entry1 = ExclusionEntry(id="server-1")
        exclusion_list.add(entry1)
        ids = exclusion_list.get_ids()
        assert ids == {"server-1"}
        
        # Multiple entries
        entry2 = ExclusionEntry(id="server-2")
        entry3 = ExclusionEntry(id="server-3")
        exclusion_list.add(entry2)
        exclusion_list.add(entry3)
        ids = exclusion_list.get_ids()
        assert ids == {"server-1", "server-2", "server-3"}
        
        # Test that it's a proper set (no duplicates possible)
        assert len(ids) == 3
        
        # Test with special characters
        special_entry = ExclusionEntry(id="server-!@#$%^&*()")
        exclusion_list.add(special_entry)
        ids = exclusion_list.get_ids()
        assert "server-!@#$%^&*()" in ids
        
        # Verify set operations work
        assert ids.intersection({"server-1", "server-999"}) == {"server-1"}
        assert ids.union({"server-999"}) == {"server-1", "server-2", "server-3", "server-!@#$%^&*()", "server-999"}
    
    def test_to_dict_serialization_comprehensive(self):
        """Test to_dict with comprehensive scenarios."""
        # Empty list
        empty_list = ExclusionList()
        data = empty_list.to_dict()
        assert data["version"] == 1
        assert "last_modified" in data
        assert data["last_modified"].endswith("Z")
        assert data["exclusions"] == []
        
        # List with entries
        exclusion_list = ExclusionList()
        entry1 = ExclusionEntry(id="server-1", name="Server 1", reason="Test reason")
        entry2 = ExclusionEntry(id="server-2", name=None, reason=None)
        exclusion_list.add(entry1)
        exclusion_list.add(entry2)
        
        data = exclusion_list.to_dict()
        assert data["version"] == 1
        assert len(data["exclusions"]) == 2
        
        # Verify entry serialization
        exclusion_data = data["exclusions"]
        assert any(ex["id"] == "server-1" for ex in exclusion_data)
        assert any(ex["id"] == "server-2" for ex in exclusion_data)
        
        # Test with custom version
        custom_list = ExclusionList(version=5)
        data = custom_list.to_dict()
        assert data["version"] == 5
    
    def test_from_dict_deserialization_comprehensive(self):
        """Test from_dict with comprehensive scenarios and edge cases."""
        # Test version 0 (legacy format)
        legacy_data = {
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": [
                {"id": "server-1", "name": "Server 1"},
                {"id": "server-2", "name": "Server 2"}
            ]
        }
        exclusion_list = ExclusionList.from_dict(legacy_data)
        assert exclusion_list.version == 1  # Migrated to v1
        assert len(exclusion_list.exclusions) == 2
        
        # Test negative version (should NOT migrate - only version 0 migrates)
        negative_version_data = {
            "version": -1,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(negative_version_data)
        assert exclusion_list.version == -1  # Should keep original negative version
        
        # Test version 1 (current format)
        v1_data = {
            "version": 1,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": [
                {"id": "server-1", "name": "Server 1", "reason": "Test"}
            ]
        }
        exclusion_list = ExclusionList.from_dict(v1_data)
        assert exclusion_list.version == 1
        assert len(exclusion_list.exclusions) == 1
        
        # Test future version (should warn but load)
        future_data = {
            "version": 99,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": []
        }
        # This should log a warning but still work
        exclusion_list = ExclusionList.from_dict(future_data)
        assert exclusion_list.version == 99
        
        # Test invalid timestamp formats
        invalid_ts_data = {
            "version": 1,
            "last_modified": "not-a-timestamp",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(invalid_ts_data)
        assert isinstance(exclusion_list.last_modified, datetime)
        
        # Test empty timestamp
        empty_ts_data = {
            "version": 1,
            "last_modified": "",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(empty_ts_data)
        assert isinstance(exclusion_list.last_modified, datetime)
        
        # Test missing timestamp
        no_ts_data = {
            "version": 1,
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(no_ts_data)
        assert isinstance(exclusion_list.last_modified, datetime)
        
        # Test missing exclusions
        no_exclusions_data = {
            "version": 1,
            "last_modified": "2025-01-15T10:30:45Z"
        }
        exclusion_list = ExclusionList.from_dict(no_exclusions_data)
        assert len(exclusion_list.exclusions) == 0
        
        # Test empty exclusions
        empty_exclusions_data = {
            "version": 1,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(empty_exclusions_data)
        assert len(exclusion_list.exclusions) == 0


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions that might be missed."""
    
    def test_arithmetic_operations_in_remove(self):
        """Test that arithmetic in remove method works correctly."""
        exclusion_list = ExclusionList()
        
        # Add multiple entries
        for i in range(10):
            entry = ExclusionEntry(id=f"server-{i}")
            exclusion_list.add(entry)
        
        original_count = len(exclusion_list.exclusions)
        assert original_count == 10
        
        # Remove one entry
        result = exclusion_list.remove("server-5")
        assert result is True
        
        # Verify count arithmetic: original_count - 1
        new_count = len(exclusion_list.exclusions)
        assert new_count == original_count - 1
        assert new_count == 9
        
        # Remove multiple entries
        exclusion_list.remove("server-1")
        exclusion_list.remove("server-2")
        exclusion_list.remove("server-3")
        
        final_count = len(exclusion_list.exclusions)
        assert final_count == 6  # 10 - 4 = 6
        
        # Test the specific comparison that might be mutated
        # original_count = len(self.exclusions)
        # if len(self.exclusions) < original_count:
        remaining_ids = exclusion_list.get_ids()
        expected_remaining = {"server-0", "server-4", "server-6", "server-7", "server-8", "server-9"}
        assert remaining_ids == expected_remaining
    
    def test_comparison_operations_in_contains(self):
        """Test comparison operations in contains method."""
        exclusion_list = ExclusionList()
        
        # Test the any() function with == comparison
        # any(ex.id == server_id for ex in self.exclusions)
        entries = [
            ExclusionEntry(id="exact-match"),
            ExclusionEntry(id="partial-match-test"),
            ExclusionEntry(id="CASE-SENSITIVE"),
        ]
        
        for entry in entries:
            exclusion_list.add(entry)
        
        # Test exact matches (== operator)
        assert exclusion_list.contains("exact-match") is True
        assert exclusion_list.contains("partial-match-test") is True
        assert exclusion_list.contains("CASE-SENSITIVE") is True
        
        # Test non-matches (== should return False)
        assert exclusion_list.contains("exact-matc") is False  # Missing character
        assert exclusion_list.contains("exact-match ") is False  # Extra space
        assert exclusion_list.contains("partial-match") is False  # Partial
        assert exclusion_list.contains("case-sensitive") is False  # Case difference
        assert exclusion_list.contains("") is False  # Empty string
    
    def test_boolean_logic_in_add(self):
        """Test boolean logic in add method."""
        exclusion_list = ExclusionList()
        
        # Test the boolean logic: if any(ex.id == entry.id for ex in self.exclusions):
        entry1 = ExclusionEntry(id="test-server")
        entry2 = ExclusionEntry(id="test-server")  # Same ID, different object
        entry3 = ExclusionEntry(id="different-server")
        
        # First add should succeed (any() returns False)
        result1 = exclusion_list.add(entry1)
        assert result1 is True
        
        # Second add with same ID should fail (any() returns True)
        result2 = exclusion_list.add(entry2)
        assert result2 is False
        
        # Third add with different ID should succeed (any() returns False)
        result3 = exclusion_list.add(entry3)
        assert result3 is True
        
        # Verify final state
        assert len(exclusion_list.exclusions) == 2
        ids = exclusion_list.get_ids()
        assert ids == {"test-server", "different-server"}
    
    def test_list_comprehension_in_remove(self):
        """Test list comprehension logic in remove method."""
        exclusion_list = ExclusionList()
        
        # Add test data (note: add() prevents duplicates, so only unique IDs)
        test_ids = ["keep-1", "remove-me", "keep-2", "keep-3"]
        for server_id in test_ids:
            entry = ExclusionEntry(id=server_id)
            exclusion_list.add(entry)
        
        # Verify initial state
        assert len(exclusion_list.exclusions) == 4
        assert exclusion_list.contains("remove-me")
        
        # The remove method uses: [ex for ex in self.exclusions if ex.id != server_id]
        original_count = len(exclusion_list.exclusions)
        result = exclusion_list.remove("remove-me")
        
        # Should return True if any were removed
        assert result is True
        
        # Should remove the entry completely
        new_count = len(exclusion_list.exclusions)
        assert new_count == original_count - 1  # One entry removed
        assert new_count == 3
        
        # Verify remaining entries
        remaining_ids = exclusion_list.get_ids()
        # Should NOT have "remove-me" entry anymore
        assert "remove-me" not in remaining_ids
        assert "keep-1" in remaining_ids
        assert "keep-2" in remaining_ids
        assert "keep-3" in remaining_ids
        
        # Test removing non-existent entry
        result = exclusion_list.remove("remove-me")
        assert result is False  # Should return False
        assert len(exclusion_list.exclusions) == 3  # No change
    
    def test_timestamp_comparison_edge_cases(self):
        """Test timestamp handling edge cases."""
        # Test with microseconds
        microsecond_data = {
            "id": "micro-test",
            "timestamp": "2025-01-15T10:30:45.123456Z"
        }
        entry = ExclusionEntry.from_dict(microsecond_data)
        assert entry.timestamp.microsecond == 123456
        
        # Test with different timezone formats
        tz_formats = [
            "2025-01-15T10:30:45Z",
            "2025-01-15T10:30:45+00:00",
            "2025-01-15T10:30:45.000Z",
            "2025-01-15T10:30:45.000+00:00"
        ]
        
        for ts_format in tz_formats:
            data = {"id": "tz-test", "timestamp": ts_format}
            entry = ExclusionEntry.from_dict(data)
            assert entry.timestamp.year == 2025
            assert entry.timestamp.month == 1
            assert entry.timestamp.day == 15
    
    def test_string_operations_edge_cases(self):
        """Test string operations and formatting edge cases."""
        # Test replace operation in to_dict: .replace("+00:00", "Z")
        entry = ExclusionEntry(id="string-test")
        data = entry.to_dict()
        
        # Should end with Z, not +00:00
        assert data["timestamp"].endswith("Z")
        assert "+00:00" not in data["timestamp"]
        
        # Test the reverse operation in from_dict: .replace("Z", "+00:00")
        z_format_data = {
            "id": "reverse-test",
            "timestamp": "2025-01-15T10:30:45Z"
        }
        entry = ExclusionEntry.from_dict(z_format_data)
        assert isinstance(entry.timestamp, datetime)
        
        # Test edge case where timestamp might contain multiple Z's
        weird_timestamp_data = {
            "id": "weird-test",
            "timestamp": "2025-01-15T10:30:45ZZ"  # Double Z
        }
        # Should handle gracefully (might fail parsing, fallback to now())
        entry = ExclusionEntry.from_dict(weird_timestamp_data)
        assert isinstance(entry.timestamp, datetime)


class TestStringIdentityMutationKillers:
    """Tests specifically designed to kill == vs is mutations."""
    
    def test_string_equality_vs_identity_in_add(self):
        """Test that add() uses == not is for string comparison."""
        exclusion_list = ExclusionList()
        
        # Create two entries with same ID content but different string objects
        # Use different methods to avoid string interning
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        id_string_1 = f"server-{unique_suffix}"
        id_string_2 = ("server-" + unique_suffix)  # Force different object
        
        # Make sure they are actually different objects but equal content
        # If they are the same object due to optimization, create truly different ones
        if id_string_1 is id_string_2:
            id_string_2 = "".join(["server-", unique_suffix])
        
        # Verify they are equal but not identical (if possible)
        assert id_string_1 == id_string_2  # Equal content
        
        entry1 = ExclusionEntry(id=id_string_1, name="First entry")
        entry2 = ExclusionEntry(id=id_string_2, name="Second entry")
        
        # First add should succeed
        result1 = exclusion_list.add(entry1)
        assert result1 is True
        
        # Second add should fail because IDs are equal
        # This tests that the code correctly identifies duplicates
        result2 = exclusion_list.add(entry2)
        assert result2 is False  # Should be rejected due to duplicate ID
        
        assert len(exclusion_list.exclusions) == 1
    
    def test_string_equality_vs_identity_in_contains(self):
        """Test that contains() uses == not is for string comparison."""
        exclusion_list = ExclusionList()
        
        # Add entry with specific ID
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        original_id = f"server-{unique_suffix}"
        entry = ExclusionEntry(id=original_id, name="Test entry")
        exclusion_list.add(entry)
        
        # Test with same content - create string with same content
        lookup_id = "server-" + unique_suffix  # Same content
        
        # Verify they are equal
        assert original_id == lookup_id  # Equal content
        
        # contains() should return True because it uses == for comparison
        result = exclusion_list.contains(lookup_id)
        assert result is True
        
        # Test with actually different content
        different_id = f"server-{str(uuid.uuid4())[:8]}"
        result = exclusion_list.contains(different_id)
        assert result is False
    
    def test_string_equality_vs_identity_in_remove(self):
        """Test that remove() uses == not is for string comparison."""
        exclusion_list = ExclusionList()
        
        # Add entry with specific ID
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        original_id = f"server-{unique_suffix}"
        entry = ExclusionEntry(id=original_id, name="Test entry")
        exclusion_list.add(entry)
        
        # Remove with same content
        remove_id = "server-" + unique_suffix  # Same content
        
        # Verify they are equal
        assert original_id == remove_id  # Equal content
        
        # remove() should succeed because it uses == for comparison
        result = exclusion_list.remove(remove_id)
        assert result is True
        
        assert len(exclusion_list.exclusions) == 0
        assert not exclusion_list.contains(original_id)


class TestVersionComparisonMutationKillers:
    """Tests specifically designed to kill version comparison mutations."""
    
    def test_version_boundary_conditions(self):
        """Test version comparison edge cases."""
        # Test exactly version 0
        version_0_data = {
            "version": 0,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(version_0_data)
        assert exclusion_list.version == 1  # Should migrate to v1
        
        # Test negative version (should NOT migrate - only version 0 migrates)
        negative_data = {
            "version": -1,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(negative_data)
        assert exclusion_list.version == -1  # Should keep original negative version
        
        # Test version 1 (should not migrate)
        version_1_data = {
            "version": 1,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(version_1_data)
        assert exclusion_list.version == 1  # Should stay v1
        
        # Test version 2 (should trigger future version warning but not migrate)
        version_2_data = {
            "version": 2,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(version_2_data)
        assert exclusion_list.version == 2  # Should keep original version
        
        # Test very large version
        large_version_data = {
            "version": 999,
            "last_modified": "2025-01-15T10:30:45Z",
            "exclusions": []
        }
        exclusion_list = ExclusionList.from_dict(large_version_data)
        assert exclusion_list.version == 999  # Should keep original version 