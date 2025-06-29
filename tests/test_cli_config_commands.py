"""Tests for CLI configuration commands.

Tests cover the unsupported format handling bug fix and return type annotations.
"""

import pytest
import json
import yaml
from typer.testing import CliRunner

from sboxmgr.cli.commands.config import config_app, _output_env_format


class TestConfigDumpCommand:
    """Test config dump command functionality."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()
    
    def test_dump_config_yaml_format(self):
        """Test config dump with YAML format."""
        result = self.runner.invoke(config_app, ["dump", "--format", "yaml"])
        
        assert result.exit_code == 0
        # Should produce valid YAML output
        try:
            yaml.safe_load(result.stdout)
        except yaml.YAMLError:
            pytest.fail("Output is not valid YAML")
    
    def test_dump_config_json_format(self):
        """Test config dump with JSON format."""
        result = self.runner.invoke(config_app, ["dump", "--format", "json"])
        
        assert result.exit_code == 0
        # Should produce valid JSON output
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
    
    def test_dump_config_env_format(self):
        """Test config dump with environment variable format."""
        result = self.runner.invoke(config_app, ["dump", "--format", "env"])
        
        assert result.exit_code == 0
        # Should contain environment variable assignments
        assert "SBOXMGR" in result.stdout
        assert "=" in result.stdout
    
    def test_dump_config_unsupported_format_error(self):
        """Test error handling for unsupported format (bug fix)."""
        result = self.runner.invoke(config_app, ["dump", "--format", "unknown"])
        
        # BUG FIX: Should exit with error code 1
        assert result.exit_code == 1
        
        # Should show clear error message (typer outputs to stderr by default)
        output = result.output
        assert "Unsupported format: 'unknown'" in output
        assert "Supported formats: yaml, json, env" in output
    
    def test_dump_config_with_include_defaults(self):
        """Test config dump with include defaults flag."""
        result = self.runner.invoke(config_app, ["dump", "--include-defaults"])
        
        assert result.exit_code == 0
        # Should include more configuration values
        config_data = yaml.safe_load(result.stdout)
        assert "_metadata" in config_data
    
    def test_dump_config_with_env_info(self):
        """Test config dump with environment info flag."""
        result = self.runner.invoke(config_app, ["dump", "--include-env-info"])
        
        assert result.exit_code == 0
        config_data = yaml.safe_load(result.stdout)
        assert "_environment_info" in config_data
    
    def test_dump_config_with_config_file(self, tmp_path):
        """Test config dump with specific config file."""
        config_file = tmp_path / "test.toml"
        config_file.write_text("""
[logging]
level = "DEBUG"
""")
        
        result = self.runner.invoke(config_app, ["dump", "--config-file", str(config_file)])
        
        assert result.exit_code == 0
        config_data = yaml.safe_load(result.stdout)
        assert config_data["logging"]["level"] == "DEBUG"
        assert config_data["_metadata"]["config_file"] == str(config_file)
    
    def test_dump_config_with_invalid_config_file(self):
        """Test config dump with invalid config file."""
        result = self.runner.invoke(config_app, ["dump", "--config-file", "/nonexistent.toml"])
        
        assert result.exit_code == 1
        # Check the actual error message format
        output = result.output
        assert "Configuration file not found" in output


class TestConfigValidateCommand:
    """Test config validate command functionality."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()
    
    def test_validate_valid_config(self, tmp_path):
        """Test validating a valid configuration file."""
        config_file = tmp_path / "valid.toml"
        config_file.write_text("""
[logging]
level = "INFO"
format = "json"

[service]
service_mode = false
""")
        
        result = self.runner.invoke(config_app, ["validate", str(config_file)])
        
        assert result.exit_code == 0
        assert f"Configuration file '{config_file}' is valid" in result.stdout
        assert "Service mode:" in result.stdout
        assert "Log level:" in result.stdout
    
    def test_validate_invalid_config(self, tmp_path):
        """Test validating an invalid configuration file."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("""
[logging]
level = "INVALID_LEVEL"
""")
        
        result = self.runner.invoke(config_app, ["validate", str(config_file)])
        
        assert result.exit_code == 1
        output = result.output
        assert "Configuration validation failed" in output
        assert "logging -> level" in output
    
    def test_validate_nonexistent_config(self):
        """Test validating a nonexistent configuration file."""
        result = self.runner.invoke(config_app, ["validate", "/nonexistent.toml"])
        
        assert result.exit_code == 1
        output = result.output
        assert "Error validating configuration" in output


class TestConfigSchemaCommand:
    """Test config schema command functionality."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()
    
    def test_generate_schema_stdout(self):
        """Test generating schema to stdout."""
        result = self.runner.invoke(config_app, ["schema"])
        
        assert result.exit_code == 0
        # Should produce valid JSON schema
        try:
            schema = json.loads(result.stdout)
            assert "properties" in schema
            assert "type" in schema
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON schema")
    
    def test_generate_schema_to_file(self, tmp_path):
        """Test generating schema to file."""
        output_file = tmp_path / "schema.json"
        
        result = self.runner.invoke(config_app, ["schema", "--output", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        assert f"JSON schema written to {output_file}" in result.stdout
        
        # Verify file contains valid JSON schema
        schema_data = json.loads(output_file.read_text())
        assert "properties" in schema_data


class TestConfigEnvInfoCommand:
    """Test config env-info command functionality."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()
    
    def test_env_info_display(self):
        """Test environment info display."""
        result = self.runner.invoke(config_app, ["env-info"])
        
        assert result.exit_code == 0
        assert "Environment Detection Results" in result.stdout
        assert "Service Mode:" in result.stdout
        assert "Container Environment:" in result.stdout
        assert "Systemd Environment:" in result.stdout


class TestOutputEnvFormat:
    """Test _output_env_format function."""
    
    def test_output_env_format_return_type(self):
        """Test that _output_env_format has proper return type annotation (bug fix)."""
        from typing import get_type_hints
        
        # BUG FIX: Function should have -> None return type annotation
        # Use get_type_hints instead of inspect.signature for proper type annotation handling
        hints = get_type_hints(_output_env_format)
        assert hints.get("return") is type(None)
    
    def test_output_env_format_basic_data(self, capsys):
        """Test environment variable format output."""
        test_data = {
            "logging": {"level": "DEBUG"},
            "service": {"service_mode": True}
        }
        
        _output_env_format(test_data, prefix="TEST")
        
        captured = capsys.readouterr()
        assert "TEST__LOGGING__LEVEL=DEBUG" in captured.out
        assert "TEST__SERVICE__SERVICE_MODE=True" in captured.out
    
    def test_output_env_format_skips_metadata(self, capsys):
        """Test that metadata fields are skipped."""
        test_data = {
            "logging": {"level": "INFO"},
            "_metadata": {"internal": "value"}
        }
        
        _output_env_format(test_data, prefix="TEST")
        
        captured = capsys.readouterr()
        assert "TEST__LOGGING__LEVEL=INFO" in captured.out
        assert "_metadata" not in captured.out
        assert "internal" not in captured.out
    
    def test_output_env_format_list_handling(self, capsys):
        """Test list values are converted to comma-separated strings."""
        test_data = {
            "logging": {"sinks": ["stdout", "journald"]}
        }
        
        _output_env_format(test_data, prefix="TEST")
        
        captured = capsys.readouterr()
        assert "TEST__LOGGING__SINKS=stdout,journald" in captured.out 