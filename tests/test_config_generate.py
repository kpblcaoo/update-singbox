import pytest
import json
from unittest.mock import patch
from sboxmgr.config.generate import generate_config, generate_temp_config
from sboxmgr.config.validation import validate_config_file, ConfigValidationError


class TestGenerateConfig:
    """Test generate_config function."""
    
    @pytest.fixture
    def sample_template(self):
        """Sample template for testing."""
        return {
            "outbounds": [
                {"type": "urltest", "tag": "auto", "outbounds": []},
                {"type": "direct", "tag": "direct"}
            ],
            "route": {
                "rules": [
                    {"ip_cidr": "$excluded_servers", "outbound": "direct"}
                ]
            }
        }
    
    @pytest.fixture
    def sample_outbounds(self):
        """Sample outbounds for testing."""
        return [
            {'server': 'test1.com', 'tag': 'vless-1', 'type': 'vless'},
            {'server': 'test2.com', 'tag': 'vmess-1', 'type': 'vmess', 'uuid': '12345678-1234-1234-1234-123456789abc'}
        ]
    
    def test_generate_config_template_not_found(self, tmp_path):
        """Test generate_config raises error when template not found."""
        template_file = tmp_path / "nonexistent.json"
        config_file = tmp_path / "config.json"
        backup_file = tmp_path / "backup.json"
        
        with pytest.raises(FileNotFoundError, match="Template file not found"):
            generate_config([], str(template_file), str(config_file), str(backup_file), [])
    
    def test_generate_config_success(self, tmp_path, sample_template, sample_outbounds):
        """Test successful config generation."""
        # Create template file
        template_file = tmp_path / "template.json"
        template_file.write_text(json.dumps(sample_template, indent=2))
        
        config_file = tmp_path / "config.json"
        backup_file = tmp_path / "backup.json"
        excluded_ips = ["1.1.1.1", "2.2.2.2"]
        
        with patch('sboxmgr.config.generate.info') as mock_info:
            result = generate_config(
                sample_outbounds, str(template_file), str(config_file), 
                str(backup_file), excluded_ips
            )
            
            assert result is True
            assert config_file.exists()
            
            # Check generated config
            config_data = json.loads(config_file.read_text())
            assert len(config_data["outbounds"]) == 4  # urltest + 2 outbounds + direct
            assert config_data["outbounds"][0]["tag"] == "auto"
            assert config_data["outbounds"][0]["outbounds"] == ["vless-1", "vmess-1"]
            assert config_data["outbounds"][1]["tag"] == "vless-1"
            assert config_data["outbounds"][2]["tag"] == "vmess-1"
            
            # Check excluded IPs
            assert config_data["route"]["rules"][0]["ip_cidr"] == ["1.1.1.1/32", "2.2.2.2/32"]
            
            mock_info.assert_called()
    
    def test_generate_config_no_change(self, tmp_path, sample_template, sample_outbounds):
        """Test config generation when no changes needed."""
        # Create template file
        template_file = tmp_path / "template.json"
        template_file.write_text(json.dumps(sample_template, indent=2))
        
        config_file = tmp_path / "config.json"
        backup_file = tmp_path / "backup.json"
        
        # Pre-populate config file with expected content
        expected_config = sample_template.copy()
        expected_config["outbounds"] = [
            {"type": "urltest", "tag": "auto", "outbounds": ["vless-1", "vmess-1"]},
            sample_outbounds[0],
            sample_outbounds[1],
            {"type": "direct", "tag": "direct"}
        ]
        expected_config["route"]["rules"][0]["ip_cidr"] = []
        config_file.write_text(json.dumps(expected_config, indent=2))
        
        with patch('sboxmgr.config.generate.info') as mock_info:
            result = generate_config(
                sample_outbounds, str(template_file), str(config_file), 
                str(backup_file), []
            )
            
            assert result is False
            mock_info.assert_called_with("Configuration has not changed. Skipping update.")
    
    def test_generate_config_validation_failure(self, tmp_path, sample_template, sample_outbounds):
        """Test config generation with validation failure."""
        template_file = tmp_path / "template.json"
        
        # Create invalid template that will pass template processing but fail validation
        # Use a template with missing required 'type' field in outbound
        invalid_template = {
            "outbounds": [
                {"tag": "invalid"}  # Missing required 'type' field
            ],
            "route": {
                "rules": [
                    {"ip_cidr": "$excluded_servers", "outbound": "direct"}
                ]
            }
        }
        template_file.write_text(json.dumps(invalid_template, indent=2))
        
        config_file = tmp_path / "config.json"
        backup_file = tmp_path / "backup.json"
        
        # Should raise ConfigValidationError for invalid config
        with pytest.raises(ConfigValidationError):
            generate_config(
                [], str(template_file), str(config_file), 
                str(backup_file), []
            )
    
    def test_generate_config_internal_validation_success(self, tmp_path, sample_template, sample_outbounds):
        """Test that internal validation works correctly (no external dependencies)."""
        template_file = tmp_path / "template.json"
        template_file.write_text(json.dumps(sample_template, indent=2))
        
        config_file = tmp_path / "config.json"
        backup_file = tmp_path / "backup.json"
        
        # This should succeed without any external sing-box binary
        result = generate_config(
            sample_outbounds, str(template_file), str(config_file), 
            str(backup_file), []
        )
        
        assert result is True
        assert config_file.exists()
        
        # Verify the generated config is valid according to our internal validation
        config_data = json.loads(config_file.read_text())
        assert len(config_data["outbounds"]) >= 1  # Should have at least one outbound
    
    def test_generate_config_config_dir_not_exists(self, tmp_path, sample_template, sample_outbounds):
        """Test config generation when config directory doesn't exist."""
        template_file = tmp_path / "template.json"
        template_file.write_text(json.dumps(sample_template, indent=2))
        
        config_file = tmp_path / "nonexistent" / "config.json"
        backup_file = tmp_path / "backup.json"
        
        with pytest.raises(FileNotFoundError, match="Config directory does not exist"):
            generate_config(
                sample_outbounds, str(template_file), str(config_file), 
                str(backup_file), []
            )
    
    def test_generate_config_with_backup(self, tmp_path, sample_template, sample_outbounds):
        """Test config generation creates backup of existing config."""
        template_file = tmp_path / "template.json"
        template_file.write_text(json.dumps(sample_template, indent=2))
        
        config_file = tmp_path / "config.json"
        backup_file = tmp_path / "backup.json"
        
        # Create existing config
        existing_config = {"old": "config"}
        config_file.write_text(json.dumps(existing_config))
        
        with patch('sboxmgr.config.generate.info') as mock_info:
            result = generate_config(
                sample_outbounds, str(template_file), str(config_file), 
                str(backup_file), []
            )
            
            assert result is True
            assert backup_file.exists()
            
            # Check backup contains old config
            backup_data = json.loads(backup_file.read_text())
            assert backup_data == existing_config
            
            mock_info.assert_any_call(f"Created backup: {backup_file}")


class TestGenerateTempConfig:
    """Test generate_temp_config function."""
    
    @pytest.fixture
    def sample_template(self):
        """Sample template for testing."""
        return {
            "outbounds": [
                {"type": "urltest", "tag": "auto", "outbounds": []},
                {"type": "direct", "tag": "direct"}
            ],
            "route": {
                "rules": [
                    {"ip_cidr": "$excluded_servers", "outbound": "direct"}
                ]
            }
        }
    
    def test_generate_temp_config_success(self, tmp_path, sample_template):
        """Test successful temp config generation."""
        outbounds = [{"type": "vless", "tag": "vless-1"}]
        
        # Use template_data directly instead of file path
        config_data = generate_temp_config(sample_template, outbounds, [])
        
        assert len(config_data["outbounds"]) >= 1  # Should have at least one outbound
        assert config_data["outbounds"][0]["tag"] == "vless-1"
        assert config_data["outbounds"][0]["type"] == "vless"
    
    def test_generate_temp_config_template_not_found(self, tmp_path):
        """Test generate_temp_config with invalid template."""
        # Test with invalid template data
        with pytest.raises(ValueError, match="Template data must be a dictionary"):
            generate_temp_config([], [], [])
    
    def test_generate_temp_config_empty_outbounds(self, tmp_path, sample_template):
        """Test generate_temp_config with empty outbounds."""
        config_data = generate_temp_config(sample_template, [], [])
        
        # Should still have outbounds from template
        assert "outbounds" in config_data
        assert len(config_data["outbounds"]) == 0  # No servers added


class TestValidateConfigFile:
    """Test validate_config_file function using internal validation."""
    
    def test_validate_config_file_success(self, tmp_path):
        """Test successful config validation with valid sing-box config."""
        config = {
            "outbounds": [
                {"type": "direct", "tag": "direct"}
            ]
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config, indent=2))
        
        # Should not raise exception for valid config
        validate_config_file(str(config_file))
        # If we get here, validation passed
    
    def test_validate_config_file_invalid(self, tmp_path):
        """Test config validation failure with invalid config."""
        config = {
            "outbounds": []  # Invalid: empty outbounds
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config, indent=2))
        
        # Should raise ConfigValidationError for invalid config
        with pytest.raises(ConfigValidationError):
            validate_config_file(str(config_file))
    
    def test_validate_config_file_not_found(self, tmp_path):
        """Test config validation when file doesn't exist."""
        config_file = tmp_path / "nonexistent.json"
        
        with pytest.raises(ConfigValidationError, match="not found"):
            validate_config_file(str(config_file))
    
    def test_validate_config_file_invalid_json(self, tmp_path):
        """Test config validation with invalid JSON."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"invalid": json}')  # Invalid JSON
        
        with pytest.raises(ConfigValidationError, match="Invalid TOML syntax"):
            validate_config_file(str(config_file))
    
    def test_validate_config_file_complex_valid(self, tmp_path):
        """Test validation of complex but valid configuration."""
        config = {
            "log": {"level": "info"},
            "inbounds": [
                {"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": 1080}
            ],
            "outbounds": [
                {"type": "urltest", "tag": "auto", "outbounds": ["direct"]},
                {"type": "direct", "tag": "direct"}
            ],
            "route": {
                "rules": [
                    {"domain": ["example.com"], "outbound": "direct"}
                ],
                "final": "auto"
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config, indent=2))
        
        # Should not raise exception for valid config
        validate_config_file(str(config_file))
        # If we get here, validation passed 