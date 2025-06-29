import pytest
import json
from pathlib import Path
from unittest.mock import patch
from sboxmgr.utils.file import (
    handle_temp_file,
    atomic_write_json,
    atomic_remove,
    file_exists,
    read_json,
    write_json
)


class TestHandleTempFile:
    """Test handle_temp_file function."""
    
    def test_handle_temp_file_success(self, tmp_path):
        """Test successful temp file handling."""
        target_path = tmp_path / "test.json"
        content = {"test": "data"}
        
        result = handle_temp_file(content, str(target_path))
        
        assert result is True
        assert target_path.exists()
        
        # Check content
        with open(target_path) as f:
            data = json.load(f)
        assert data == content


class TestFileExists:
    """Test file_exists function."""
    
    def test_file_exists_true(self, tmp_path):
        """Test file_exists returns True for existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        assert file_exists(str(test_file)) is True
    
    def test_file_exists_false(self, tmp_path):
        """Test file_exists returns False for non-existent file."""
        test_file = tmp_path / "nonexistent.txt"
        
        assert file_exists(str(test_file)) is False


class TestReadJson:
    """Test read_json function."""
    
    def test_read_json_success(self, tmp_path):
        """Test successful JSON reading."""
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        
        with open(test_file, "w") as f:
            json.dump(test_data, f)
        
        result = read_json(str(test_file))
        assert result == test_data
    
    def test_read_json_file_not_found(self, tmp_path):
        """Test reading non-existent JSON file."""
        test_file = tmp_path / "nonexistent.json"
        
        with pytest.raises(FileNotFoundError):
            read_json(str(test_file))


class TestWriteJson:
    """Test write_json function."""
    
    def test_write_json_success(self, tmp_path):
        """Test successful JSON writing."""
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}
        
        write_json(test_data, str(test_file))
        
        assert test_file.exists()
        
        # Verify content
        with open(test_file) as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data


class TestAtomicWriteJson:
    """Test atomic_write_json function."""
    
    def test_atomic_write_json_success(self, tmp_path):
        """Test successful atomic JSON write."""
        target_path = tmp_path / "test.json"
        data = {"key": "value", "number": 42}
        
        result = atomic_write_json(data, str(target_path))
        
        assert result is True
        assert target_path.exists()
        
        # Check content
        with open(target_path) as f:
            loaded_data = json.load(f)
        assert loaded_data == data
    
    def test_atomic_write_json_temp_file_cleanup(self, tmp_path):
        """Test temp file cleanup on failure."""
        target_path = tmp_path / "test.json"
        data = {"test": "data"}
        
        with patch('os.replace', side_effect=OSError("Replace failed")):
            with pytest.raises(OSError):
                atomic_write_json(data, str(target_path))
        
        # Temp file should be cleaned up
        temp_path = Path(str(target_path) + ".tmp")
        assert not temp_path.exists()
    
    def test_atomic_write_json_serialization_error(self, tmp_path):
        """Test atomic write with JSON serialization error."""
        target_path = tmp_path / "test.json"
        
        # Create non-serializable data
        class NonSerializable:
            pass
        
        data = {"obj": NonSerializable()}
        
        with pytest.raises(TypeError):
            atomic_write_json(data, str(target_path))
        
        # Target file should not exist
        assert not target_path.exists()
        
        # Temp file should be cleaned up
        temp_path = Path(str(target_path) + ".tmp")
        assert not temp_path.exists()


class TestAtomicRemove:
    """Test atomic_remove function."""
    
    def test_atomic_remove_existing_file(self, tmp_path):
        """Test removing existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        assert test_file.exists()
        
        with patch('logging.info') as mock_log:
            atomic_remove(str(test_file))
        
        assert not test_file.exists()
        mock_log.assert_called_once()
        assert "Removed file:" in mock_log.call_args[0][0]
    
    def test_atomic_remove_nonexistent_file(self, tmp_path):
        """Test removing non-existent file (should not raise error)."""
        test_file = tmp_path / "nonexistent.txt"
        
        assert not test_file.exists()
        
        # Should not raise exception
        atomic_remove(str(test_file))
    
    def test_atomic_remove_permission_error(self, tmp_path):
        """Test removing file with permission error."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        with patch('os.remove', side_effect=PermissionError("Permission denied")), \
             patch('logging.error') as mock_log:
            
            with pytest.raises(PermissionError):
                atomic_remove(str(test_file))
            
            mock_log.assert_called_once()
            assert "Failed to remove" in mock_log.call_args[0][0]


class TestHandleTempFileAdvanced:
    """Advanced tests for handle_temp_file function."""
    
    def test_handle_temp_file_with_validation_success(self, tmp_path):
        """Test temp file handling with successful validation."""
        target_path = tmp_path / "test.json"
        content = {"test": "data"}
        
        def validate_fn(path):
            # Check if file contains valid JSON
            try:
                with open(path) as f:
                    json.load(f)
                return True
            except (json.JSONDecodeError, FileNotFoundError):
                return False
        
        result = handle_temp_file(content, str(target_path), validate_fn)
        
        assert result is True
        assert target_path.exists()
    
    def test_handle_temp_file_with_validation_failure(self, tmp_path):
        """Test temp file handling with validation failure."""
        target_path = tmp_path / "test.json"
        content = {"test": "data"}
        
        def validate_fn(path):
            return False  # Always fail validation
        
        with pytest.raises(ValueError, match="Validation failed"):
            handle_temp_file(content, str(target_path), validate_fn)
        
        # Target file should not exist
        assert not target_path.exists()
    
    def test_handle_temp_file_move_error(self, tmp_path):
        """Test temp file handling with move error."""
        target_path = tmp_path / "test.json"
        content = {"test": "data"}
        
        with patch('shutil.move', side_effect=OSError("Move failed")):
            with pytest.raises(OSError, match="Move failed"):
                handle_temp_file(content, str(target_path))
    
    def test_handle_temp_file_logging(self, tmp_path):
        """Test temp file handling logging on error."""
        target_path = tmp_path / "test.json"
        content = {"test": "data"}
        
        with patch('shutil.move', side_effect=OSError("Move failed")), \
             patch('logging.error') as mock_log:
            
            with pytest.raises(OSError):
                handle_temp_file(content, str(target_path))
            
            mock_log.assert_called_once()
            assert "Failed to handle temporary file" in mock_log.call_args[0][0]


class TestReadJsonAdvanced:
    """Advanced tests for read_json function."""
    
    def test_read_json_invalid_json(self, tmp_path):
        """Test reading invalid JSON file."""
        test_file = tmp_path / "invalid.json"
        test_file.write_text("{ invalid json content")
        
        with pytest.raises(json.JSONDecodeError):
            read_json(str(test_file))
    
    def test_read_json_empty_file(self, tmp_path):
        """Test reading empty JSON file."""
        test_file = tmp_path / "empty.json"
        test_file.write_text("")
        
        with pytest.raises(json.JSONDecodeError):
            read_json(str(test_file))
    
    def test_read_json_complex_data(self, tmp_path):
        """Test reading complex JSON data."""
        test_file = tmp_path / "complex.json"
        test_data = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, "two", {"three": 3}],
            "object": {
                "nested": {
                    "deep": "value"
                }
            }
        }
        
        with open(test_file, "w") as f:
            json.dump(test_data, f)
        
        result = read_json(str(test_file))
        assert result == test_data


class TestWriteJsonAdvanced:
    """Advanced tests for write_json function."""
    
    def test_write_json_serialization_error(self, tmp_path):
        """Test JSON writing with serialization error."""
        test_file = tmp_path / "test.json"
        
        # Create non-serializable data
        class NonSerializable:
            pass
        
        test_data = {"obj": NonSerializable()}
        
        with pytest.raises(TypeError):
            write_json(test_data, str(test_file))
        
        # File is created but should be empty due to serialization error
        if test_file.exists():
            # File should be empty or contain incomplete data
            content = test_file.read_text()
            assert content == "" or "{" in content
    
    def test_write_json_formatting(self, tmp_path):
        """Test JSON writing with proper formatting."""
        test_file = tmp_path / "formatted.json"
        test_data = {"key": "value", "nested": {"inner": "data"}}
        
        write_json(test_data, str(test_file))
        
        # Check that file is properly formatted (indented)
        content = test_file.read_text()
        assert "  " in content  # Should have indentation
        assert content.count("\n") > 1  # Should have multiple lines
    
    def test_write_json_overwrite(self, tmp_path):
        """Test JSON writing overwrites existing file."""
        test_file = tmp_path / "overwrite.json"
        
        # Write initial data
        initial_data = {"initial": "data"}
        write_json(initial_data, str(test_file))
        
        # Overwrite with new data
        new_data = {"new": "data"}
        write_json(new_data, str(test_file))
        
        # Verify new data
        with open(test_file) as f:
            loaded_data = json.load(f)
        assert loaded_data == new_data
        assert loaded_data != initial_data


class TestFileUtilsIntegration:
    """Integration tests for file utilities."""
    
    def test_atomic_write_vs_regular_write(self, tmp_path):
        """Test atomic write vs regular write behavior."""
        regular_file = tmp_path / "regular.json"
        atomic_file = tmp_path / "atomic.json"
        test_data = {"integration": "test"}
        
        # Both should produce same result for successful writes
        write_json(test_data, str(regular_file))
        atomic_write_json(test_data, str(atomic_file))
        
        assert read_json(str(regular_file)) == read_json(str(atomic_file))
    
    def test_file_lifecycle(self, tmp_path):
        """Test complete file lifecycle: create, read, update, remove."""
        test_file = tmp_path / "lifecycle.json"
        
        # 1. Create
        initial_data = {"version": 1, "data": "initial"}
        write_json(initial_data, str(test_file))
        assert file_exists(str(test_file))
        
        # 2. Read
        loaded_data = read_json(str(test_file))
        assert loaded_data == initial_data
        
        # 3. Update (atomic)
        updated_data = {"version": 2, "data": "updated"}
        atomic_write_json(updated_data, str(test_file))
        assert read_json(str(test_file)) == updated_data
        
        # 4. Remove
        atomic_remove(str(test_file))
        assert not file_exists(str(test_file))
    
    def test_error_handling_consistency(self, tmp_path):
        """Test consistent error handling across functions."""
        nonexistent_file = tmp_path / "nonexistent.json"
        
        # read_json should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            read_json(str(nonexistent_file))
        
        # file_exists should return False (not raise)
        assert file_exists(str(nonexistent_file)) is False
        
        # atomic_remove should not raise (safe to call)
        atomic_remove(str(nonexistent_file))  # Should not raise
        
        # write_json to invalid path should raise
        invalid_path = tmp_path / "nonexistent_dir" / "file.json"
        with pytest.raises(FileNotFoundError):
            write_json({"test": "data"}, str(invalid_path))
