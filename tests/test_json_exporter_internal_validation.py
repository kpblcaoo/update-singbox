"""Test JSON exporter with internal validation."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from sboxmgr.json_export import JSONExporter
from sboxmgr.config.validation import ConfigValidationError


class TestJSONExporterInternalValidation:
    """Test JSON exporter internal validation functionality."""
    
    def test_export_config_with_validation(self):
        """Test exporting configuration with internal validation."""
        exporter = JSONExporter(validate=True)
        
        # Valid sing-box config
        config_data = {
            "outbounds": [
                {
                    "type": "shadowsocks",
                    "server": "example.com",
                    "server_port": 8388,
                    "method": "aes-256-gcm",
                    "password": "password123"  # pragma: allowlist secret
                }
            ]
        }
        
        result = exporter.export_config("sing-box", config_data)
        
        assert result["client"] == "sing-box"
        assert result["config"] == config_data
        assert "metadata" in result
        assert "checksum" in result["metadata"]
    
    def test_export_config_invalid_singbox(self):
        """Test exporting invalid sing-box configuration."""
        exporter = JSONExporter(validate=True)
        
        # Invalid sing-box config (missing required fields)
        config_data = {
            "outbounds": [
                {
                    "type": "shadowsocks",
                    # Missing required fields
                }
            ]
        }
        
        with pytest.raises(ConfigValidationError, match="Shadowsocks outbound"):
            exporter.export_config("sing-box", config_data)
    
    def test_export_config_unsupported_client(self):
        """Test exporting configuration for unsupported client type."""
        exporter = JSONExporter(validate=True)
        
        config_data = {"test": "data"}
        
        with pytest.raises(ConfigValidationError, match="Unsupported client type"):
            exporter.export_config("unsupported-client", config_data)
    
    def test_export_config_validation_disabled(self):
        """Test exporting configuration with validation disabled."""
        exporter = JSONExporter(validate=False)
        
        # Invalid config should pass when validation is disabled
        config_data = {"invalid": "config"}
        
        result = exporter.export_config("sing-box", config_data)
        assert result["client"] == "sing-box"
        assert result["config"] == config_data
    
    def test_export_to_file_with_validation(self, tmp_path):
        """Test exporting configuration to file with validation."""
        exporter = JSONExporter(validate=True)
        
        config_data = {
            "outbounds": [
                {
                    "type": "direct"
                }
            ]
        }
        
        output_file = tmp_path / "test_config.json"
        
        result_path = exporter.export_to_file(
            "sing-box", config_data, output_file
        )
        
        assert result_path.exists()
        
        # Verify file content
        with open(result_path) as f:
            data = json.load(f)
        
        assert data["client"] == "sing-box"
        assert data["config"] == config_data
    
    def test_validate_export_structure(self):
        """Test internal export structure validation."""
        exporter = JSONExporter(validate=True)
        
        # Valid export structure
        valid_export = {
            "client": "sing-box",
            "version": "1.0",
            "created_at": "2024-01-01T00:00:00Z",
            "config": {"test": "data"},
            "metadata": {"test": "metadata"}
        }
        
        # Should not raise
        exporter._validate_export(valid_export)
    
    def test_validate_export_missing_fields(self):
        """Test export validation with missing required fields."""
        exporter = JSONExporter(validate=True)
        
        # Missing required fields
        invalid_export = {
            "client": "sing-box",
            # Missing other required fields
        }
        
        with pytest.raises(ConfigValidationError, match="missing required field"):
            exporter._validate_export(invalid_export)
    
    def test_validate_export_wrong_types(self):
        """Test export validation with wrong field types."""
        exporter = JSONExporter(validate=True)
        
        # Wrong types
        invalid_export = {
            "client": 123,  # Should be string
            "version": "1.0",
            "created_at": "2024-01-01T00:00:00Z",
            "config": "not_a_dict",  # Should be dict
            "metadata": {"test": "metadata"}
        }
        
        with pytest.raises(ConfigValidationError, match="must be a string"):
            exporter._validate_export(invalid_export)
    
    def test_validate_client_config_singbox(self):
        """Test client-specific validation for sing-box."""
        exporter = JSONExporter(validate=True)
        
        # Valid sing-box config
        config_data = {
            "outbounds": [
                {
                    "type": "direct"
                }
            ]
        }
        
        # Should not raise
        exporter._validate_client_config("sing-box", config_data)
    
    def test_validate_client_config_other_clients(self):
        """Test client-specific validation for other clients."""
        exporter = JSONExporter(validate=True)
        
        config_data = {"test": "data"}
        
        # Should not raise for supported clients
        exporter._validate_client_config("clash", config_data)
        exporter._validate_client_config("xray", config_data)
        exporter._validate_client_config("mihomo", config_data)
    
    def test_validate_client_config_invalid_type(self):
        """Test client-specific validation with invalid config type."""
        exporter = JSONExporter(validate=True)
        
        config_data = "not_a_dict"
        
        with pytest.raises(ConfigValidationError, match="must be a dictionary"):
            exporter._validate_client_config("clash", config_data) 