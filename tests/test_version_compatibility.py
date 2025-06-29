"""Tests for version compatibility utilities."""

import subprocess
from unittest.mock import patch, MagicMock
from sboxmgr.utils.version import (
    get_singbox_version,
    check_version_compatibility,
    should_use_legacy_outbounds,
    get_version_warning_message
)


class TestGetSingboxVersion:
    """Tests for get_singbox_version function."""
    
    def test_version_detection_standard_format(self):
        """Test version detection with standard 'sing-box version X.Y.Z' format."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="sing-box version 1.11.5\nBuilt with go1.21.3"
            )
            result = get_singbox_version()
            assert result == "1.11.5"
    
    def test_version_detection_minimal_format(self):
        """Test version detection with minimal format (just version number)."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="1.10.2"
            )
            result = get_singbox_version()
            assert result == "1.10.2"
    
    def test_version_detection_failure_not_found(self):
        """Test version detection when sing-box is not found."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = get_singbox_version()
            assert result is None
    
    def test_version_detection_failure_timeout(self):
        """Test version detection when command times out."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("sing-box", 5)):
            result = get_singbox_version()
            assert result is None
    
    def test_version_detection_failure_bad_return_code(self):
        """Test version detection when command returns error."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = get_singbox_version()
            assert result is None
    
    def test_version_detection_no_version_in_output(self):
        """Test version detection when output doesn't contain version."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Some other output without version"
            )
            result = get_singbox_version()
            assert result is None


class TestCheckVersionCompatibility:
    """Tests for check_version_compatibility function."""
    
    def test_compatible_version(self):
        """Test with compatible version (>= 1.11.0)."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value="1.11.5"):
            is_compatible, current_version, message = check_version_compatibility()
            assert is_compatible is True
            assert current_version == "1.11.5"
            assert "совместима" in message
    
    def test_incompatible_version(self):
        """Test with incompatible version (< 1.11.0)."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value="1.10.2"):
            is_compatible, current_version, message = check_version_compatibility()
            assert is_compatible is False
            assert current_version == "1.10.2"
            assert "устарела" in message
    
    def test_version_not_detected(self):
        """Test when version cannot be detected."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value=None):
            is_compatible, current_version, message = check_version_compatibility()
            assert is_compatible is False
            assert current_version is None
            assert "Не удалось определить версию" in message
    
    def test_custom_required_version(self):
        """Test with custom required version."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value="1.12.0"):
            is_compatible, current_version, message = check_version_compatibility("1.13.0")
            assert is_compatible is False
            assert current_version == "1.12.0"
            assert "1.13.0" in message
    
    def test_version_parsing_error(self):
        """Test when version parsing fails."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value="invalid-version"):
            is_compatible, current_version, message = check_version_compatibility()
            assert is_compatible is False
            assert current_version == "invalid-version"
            assert "Ошибка при сравнении версий" in message


class TestShouldUseLegacyOutbounds:
    """Tests for should_use_legacy_outbounds function."""
    
    def test_legacy_required_old_version(self):
        """Test that legacy outbounds are required for old versions."""
        result = should_use_legacy_outbounds("1.10.5")
        assert result is True
    
    def test_legacy_not_required_new_version(self):
        """Test that legacy outbounds are not required for new versions."""
        result = should_use_legacy_outbounds("1.11.0")
        assert result is False
    
    def test_legacy_not_required_newer_version(self):
        """Test that legacy outbounds are not required for newer versions."""
        result = should_use_legacy_outbounds("1.12.5")
        assert result is False
    
    def test_auto_detection_old_version(self):
        """Test auto-detection with old version."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value="1.9.0"):
            result = should_use_legacy_outbounds()
            assert result is True
    
    def test_auto_detection_new_version(self):
        """Test auto-detection with new version."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value="1.11.2"):
            result = should_use_legacy_outbounds()
            assert result is False
    
    def test_auto_detection_no_version(self):
        """Test auto-detection when version cannot be determined."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value=None):
            result = should_use_legacy_outbounds()
            assert result is False  # Default to modern syntax
    
    def test_invalid_version_parsing(self):
        """Test with invalid version string."""
        result = should_use_legacy_outbounds("not-a-version")
        assert result is False  # Default to modern syntax on error


class TestGetVersionWarningMessage:
    """Tests for get_version_warning_message function."""
    
    def test_warning_message_format(self):
        """Test that warning message contains expected elements."""
        message = get_version_warning_message("1.10.5")
        assert "⚠️" in message
        assert "ПРЕДУПРЕЖДЕНИЕ" in message
        assert "1.10.5" in message
        assert "1.11.0" in message
        assert "rule actions" in message
        assert "https://sing-box.sagernet.org/installation/" in message
    
    def test_warning_message_different_version(self):
        """Test warning message with different version."""
        message = get_version_warning_message("1.9.3")
        assert "1.9.3" in message


# Integration tests
class TestVersionIntegration:
    """Integration tests for version functionality."""
    
    def test_version_workflow_compatible(self):
        """Test complete workflow with compatible version."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value="1.11.5"):
            # Check compatibility
            is_compatible, version, message = check_version_compatibility()
            assert is_compatible is True
            
            # Should not use legacy
            use_legacy = should_use_legacy_outbounds(version)
            assert use_legacy is False
    
    def test_version_workflow_incompatible(self):
        """Test complete workflow with incompatible version."""
        with patch('sboxmgr.utils.version.get_singbox_version', return_value="1.10.2"):
            # Check compatibility
            is_compatible, version, message = check_version_compatibility()
            assert is_compatible is False
            
            # Should use legacy
            use_legacy = should_use_legacy_outbounds(version)
            assert use_legacy is True
            
            # Should have warning message
            warning = get_version_warning_message(version)
            assert "1.10.2" in warning


# Fix import for subprocess 