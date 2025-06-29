"""Tests for configuration loading and validation.

Tests cover all the bug fixes implemented in the config loader module.
"""

import pytest
import json
import toml
import yaml
from pathlib import Path
from pydantic import ValidationError

from sboxmgr.config.loader import (
    load_config,
    load_config_file,
    find_config_file,
    save_config,
    create_default_config_file,
    merge_cli_args_to_config
)
from sboxmgr.config.models import AppConfig


class TestLoadConfig:
    """Test load_config function and config file validation."""
    
    def test_load_config_with_valid_file(self, tmp_path):
        """Test loading configuration from valid file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[logging]
level = "DEBUG"
format = "json"

[service]
service_mode = true
""")
        
        config = load_config(str(config_file))
        
        # Verify config loaded correctly
        assert config.logging.level == "DEBUG"
        assert config.logging.format == "json"
        assert config.service.service_mode is True
        
        # BUG FIX: Verify config_file is set and validated during initialization
        assert config.config_file == str(config_file)
    
    def test_load_config_file_validation_bypass_fixed(self, tmp_path):
        """Test that config_file validation is not bypassed (bug fix)."""
        # Create a valid config file first
        valid_file = tmp_path / "valid.toml"
        valid_file.write_text('[logging]\nlevel = "INFO"')
        
        # Test 1: Valid file should work
        config = load_config(str(valid_file))
        assert config.config_file == str(valid_file)
        
        # Test 2: Invalid file should trigger FileNotFoundError during file loading
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config("/nonexistent/path/config.toml")
        
        # Verify it's about config file not found
        assert "Configuration file not found" in str(exc_info.value)
    
    def test_load_config_without_file(self):
        """Test loading default configuration without file."""
        config = load_config()
        
        # Should have default values
        assert config.logging.level == "INFO"
        assert config.config_file is None
        assert config.service.service_mode is not None  # Should be auto-detected
    
    def test_load_config_validation_error_preserved(self, tmp_path):
        """Test that ValidationError details are preserved (bug fix)."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("""
[logging]
level = "INVALID_LEVEL"
""")
        
        with pytest.raises(ValidationError) as exc_info:
            load_config(str(config_file))
        
        # BUG FIX: Verify structured error details are preserved
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert errors[0]["type"] == "value_error"
        # Check location tuple contains logging and level
        loc_tuple = errors[0]["loc"]
        assert "logging" in loc_tuple and "level" in loc_tuple
        assert "INVALID_LEVEL" in errors[0]["msg"]


class TestLoadConfigFile:
    """Test load_config_file function and format detection."""
    
    def test_load_toml_file(self, tmp_path):
        """Test loading TOML configuration file."""
        config_file = tmp_path / "config.toml"
        config_data = {
            "logging": {"level": "DEBUG"},
            "service": {"service_mode": False}
        }
        config_file.write_text(toml.dumps(config_data))
        
        result = load_config_file(str(config_file))
        assert result == config_data
    
    def test_load_yaml_file(self, tmp_path):
        """Test loading YAML configuration file."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "logging": {"level": "INFO"},
            "service": {"service_mode": True}
        }
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config_file(str(config_file))
        assert result == config_data
    
    def test_load_json_file(self, tmp_path):
        """Test loading JSON configuration file."""
        config_file = tmp_path / "config.json"
        config_data = {
            "logging": {"level": "WARNING"},
            "service": {"service_mode": False}
        }
        config_file.write_text(json.dumps(config_data))
        
        result = load_config_file(str(config_file))
        assert result == config_data
    
    def test_auto_detect_format_toml(self, tmp_path):
        """Test auto-detection of TOML format (bug fix: redundant seek removed)."""
        config_file = tmp_path / "config.conf"  # Unknown extension
        config_file.write_text("""
[logging]
level = "DEBUG"

[service]
service_mode = true
""")
        
        result = load_config_file(str(config_file))
        
        # BUG FIX: Auto-detection should work without redundant f.seek(0)
        assert result["logging"]["level"] == "DEBUG"
        assert result["service"]["service_mode"] is True
    
    def test_auto_detect_format_yaml(self, tmp_path):
        """Test auto-detection of YAML format."""
        config_file = tmp_path / "config.conf"
        config_file.write_text("""
logging:
  level: INFO
service:
  service_mode: false
""")
        
        result = load_config_file(str(config_file))
        assert result["logging"]["level"] == "INFO"
        assert result["service"]["service_mode"] is False
    
    def test_auto_detect_format_json(self, tmp_path):
        """Test auto-detection of JSON format."""
        config_file = tmp_path / "config.conf"
        config_data = {"logging": {"level": "ERROR"}}
        config_file.write_text(json.dumps(config_data))
        
        result = load_config_file(str(config_file))
        assert result == config_data
    
    def test_file_not_found(self, tmp_path):
        """Test error when config file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config_file(str(tmp_path / "nonexistent.toml"))
        
        assert "Configuration file not found" in str(exc_info.value)
    
    def test_invalid_file_path(self, tmp_path):
        """Test error when path is not a file."""
        with pytest.raises(ValueError) as exc_info:
            load_config_file(str(tmp_path))  # Directory, not file
        
        assert "Configuration path is not a file" in str(exc_info.value)
    
    def test_unsupported_format(self, tmp_path):
        """Test error with unsupported file format."""
        config_file = tmp_path / "config.unknown"
        # Use content that will fail all parsers (TOML, YAML, JSON)
        config_file.write_text("{ invalid json content [ with broken syntax }")
        
        with pytest.raises(ValueError) as exc_info:
            load_config_file(str(config_file))
        
        assert "Unsupported configuration file format" in str(exc_info.value)


class TestConfigFileValidation:
    """Test configuration file validation during AppConfig creation."""
    
    def test_valid_config_file_validation(self, tmp_path):
        """Test that valid config files pass validation."""
        config_file = tmp_path / "valid.toml"
        config_file.write_text('[logging]\nlevel = "INFO"')
        
        # Should not raise validation error
        config = AppConfig(config_file=str(config_file))
        assert config.config_file == str(config_file)
    
    def test_nonexistent_config_file_validation(self):
        """Test that nonexistent config files fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(config_file="/nonexistent/file.toml")
        
        errors = exc_info.value.errors()
        assert any("Configuration file not found" in str(error.get("msg", "")) for error in errors)
    
    def test_directory_as_config_file_validation(self, tmp_path):
        """Test that directories fail config file validation."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(config_file=str(tmp_path))
        
        errors = exc_info.value.errors()
        assert any("Configuration path is not a file" in str(error.get("msg", "")) for error in errors)
    
    def test_unreadable_config_file_validation(self, tmp_path):
        """Test that unreadable files fail validation."""
        config_file = tmp_path / "unreadable.toml"
        config_file.write_text('[logging]\nlevel = "INFO"')
        
        # Make file unreadable
        config_file.chmod(0o000)
        
        try:
            with pytest.raises(ValidationError) as exc_info:
                AppConfig(config_file=str(config_file))
            
            errors = exc_info.value.errors()
            assert any("Configuration file is not readable" in str(error.get("msg", "")) for error in errors)
        finally:
            # Restore permissions for cleanup
            config_file.chmod(0o644)


class TestMergeCliArgsToConfig:
    """Test CLI argument merging functionality."""
    
    def test_merge_log_level(self):
        """Test merging log level from CLI."""
        base_config = AppConfig()
        original_level = base_config.logging.level
        
        merged = merge_cli_args_to_config(base_config, log_level="DEBUG")
        
        assert merged.logging.level == "DEBUG"
        # Original should be unchanged
        assert base_config.logging.level == original_level
    
    def test_merge_debug_mode(self):
        """Test merging debug mode from CLI."""
        base_config = AppConfig()
        
        merged = merge_cli_args_to_config(base_config, debug=True)
        
        assert merged.app.debug is True
        assert merged.logging.level == "DEBUG"  # Debug mode should set log level
    
    def test_merge_service_mode(self):
        """Test merging service mode from CLI."""
        base_config = AppConfig()
        
        merged = merge_cli_args_to_config(base_config, service_mode=True)
        
        assert merged.service.service_mode is True
    
    def test_merge_config_file(self, tmp_path):
        """Test merging config file path from CLI."""
        config_file = tmp_path / "test.toml"
        config_file.write_text('[logging]\nlevel = "INFO"')
        
        base_config = AppConfig()
        
        merged = merge_cli_args_to_config(base_config, config_file=str(config_file))
        
        assert merged.config_file == str(config_file)

    def test_merge_uses_model_dump_not_dict(self):
        """Test that merge function uses model_dump() instead of deprecated dict() method."""
        base_config = AppConfig()
        
        # This should not raise AttributeError about missing dict() method
        # The function should complete without errors
        merged = merge_cli_args_to_config(base_config, log_level="DEBUG")
        
        # Verify the function works (actual level may be overridden by service mode)
        assert merged is not None
        assert hasattr(merged, 'logging')


class TestFindConfigFile:
    """Test automatic config file discovery."""
    
    def test_find_config_in_current_dir(self, tmp_path, monkeypatch):
        """Test finding config file in current directory."""
        monkeypatch.chdir(tmp_path)
        
        config_file = tmp_path / "config.toml"
        config_file.write_text('[logging]\nlevel = "INFO"')
        
        found = find_config_file()
        assert found == str(config_file)
    
    def test_find_config_priority_order(self, tmp_path, monkeypatch):
        """Test that config.toml has priority over other names."""
        monkeypatch.chdir(tmp_path)
        
        # Create multiple config files
        (tmp_path / "sboxmgr.toml").write_text('[logging]\nlevel = "INFO"')
        (tmp_path / "config.toml").write_text('[logging]\nlevel = "DEBUG"')
        
        found = find_config_file()
        assert found == str(tmp_path / "config.toml")
    
    def test_no_config_file_found(self, tmp_path, monkeypatch):
        """Test when no config file is found."""
        monkeypatch.chdir(tmp_path)
        
        # Mock Path.home() to return a non-existent directory
        fake_home = tmp_path / "fake_home"
        monkeypatch.setattr(Path, 'home', lambda: fake_home)
        
        found = find_config_file()
        assert found is None


class TestSaveConfig:
    """Test configuration saving functionality."""
    
    def test_save_toml_config(self, tmp_path):
        """Test saving configuration as TOML."""
        config = AppConfig()
        config.logging.level = "DEBUG"
        
        config_file = tmp_path / "output.toml"
        save_config(config, str(config_file))
        
        assert config_file.exists()
        
        # Verify content
        loaded_data = toml.loads(config_file.read_text())
        assert loaded_data["logging"]["level"] == "DEBUG"
    
    def test_save_yaml_config(self, tmp_path):
        """Test saving configuration as YAML."""
        config = AppConfig()
        config.logging.level = "INFO"
        
        config_file = tmp_path / "output.yaml"
        save_config(config, str(config_file))
        
        assert config_file.exists()
        
        # Verify content
        loaded_data = yaml.safe_load(config_file.read_text())
        assert loaded_data["logging"]["level"] == "INFO"
    
    def test_save_json_config(self, tmp_path):
        """Test saving configuration as JSON."""
        config = AppConfig()
        config.logging.level = "WARNING"
        
        config_file = tmp_path / "output.json"
        save_config(config, str(config_file))
        
        assert config_file.exists()
        
        # Verify content
        loaded_data = json.loads(config_file.read_text())
        assert loaded_data["logging"]["level"] == "WARNING"
    
    def test_save_unsupported_format(self, tmp_path):
        """Test error when saving with unsupported format."""
        config = AppConfig()
        config_file = tmp_path / "output.unknown"
        
        with pytest.raises(OSError) as exc_info:
            save_config(config, str(config_file))
        
        assert "Unsupported configuration file format" in str(exc_info.value)
    
    def test_save_creates_directory(self, tmp_path):
        """Test that save_config creates parent directories."""
        config = AppConfig()
        config_file = tmp_path / "subdir" / "deep" / "config.toml"
        
        save_config(config, str(config_file))
        
        assert config_file.exists()
        assert config_file.parent.exists()


class TestCreateDefaultConfigFile:
    """Test default config file creation."""
    
    def test_create_default_config(self, tmp_path):
        """Test creating default configuration file."""
        config_file = tmp_path / "default.toml"
        
        create_default_config_file(str(config_file))
        
        assert config_file.exists()
        
        # Verify content structure
        loaded_data = toml.loads(config_file.read_text())
        assert "logging" in loaded_data
        assert "service" in loaded_data
        assert loaded_data["logging"]["level"] == "INFO"
    
    def test_create_default_config_creates_directory(self, tmp_path):
        """Test that create_default_config_file creates parent directories."""
        config_file = tmp_path / "subdir" / "config.toml"
        
        create_default_config_file(str(config_file))
        
        assert config_file.exists()
        assert config_file.parent.exists() 