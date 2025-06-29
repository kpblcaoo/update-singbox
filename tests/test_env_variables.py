import os
from unittest.mock import patch
from pathlib import Path
from sboxmgr.utils.env import (
    get_fetch_timeout, 
    get_fetch_size_limit,
    get_log_file,
    get_config_file,
    get_debug_level,
    get_url
)

class TestEnvironmentVariables:
    """Tests for environment variable utility functions."""

    def test_get_fetch_timeout_default(self):
        """Test that get_fetch_timeout returns default value."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_fetch_timeout() == 30

    def test_get_fetch_timeout_from_env(self):
        """Test that get_fetch_timeout reads from environment variable."""
        with patch.dict(os.environ, {"SBOXMGR_FETCH_TIMEOUT": "60"}):
            assert get_fetch_timeout() == 60

    def test_get_fetch_timeout_invalid_env(self):
        """Test that invalid environment value falls back to default."""
        with patch.dict(os.environ, {"SBOXMGR_FETCH_TIMEOUT": "invalid"}):
            assert get_fetch_timeout() == 30

    def test_get_fetch_timeout_empty_env(self):
        """Test that empty environment value falls back to default."""
        with patch.dict(os.environ, {"SBOXMGR_FETCH_TIMEOUT": ""}):
            assert get_fetch_timeout() == 30

    def test_get_fetch_size_limit_default(self):
        """Test that get_fetch_size_limit returns default value (2MB)."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_fetch_size_limit() == 2097152  # 2MB

    def test_get_fetch_size_limit_from_env(self):
        """Test that get_fetch_size_limit reads from environment variable."""
        with patch.dict(os.environ, {"SBOXMGR_FETCH_SIZE_LIMIT": "1048576"}):  # 1MB
            assert get_fetch_size_limit() == 1048576

    def test_get_fetch_size_limit_invalid_env(self):
        """Test that invalid environment value falls back to default."""
        with patch.dict(os.environ, {"SBOXMGR_FETCH_SIZE_LIMIT": "invalid"}):
            assert get_fetch_size_limit() == 2097152

    def test_get_fetch_size_limit_empty_env(self):
        """Test that empty environment value falls back to default."""
        with patch.dict(os.environ, {"SBOXMGR_FETCH_SIZE_LIMIT": ""}):
            assert get_fetch_size_limit() == 2097152

    def test_all_env_functions_exist(self):
        """Regression test: ensure all expected environment functions exist."""
        # Test that functions are callable
        assert callable(get_fetch_timeout)
        assert callable(get_fetch_size_limit)
        assert callable(get_log_file)
        assert callable(get_config_file)
        assert callable(get_debug_level)

    def test_fetch_functions_return_integers(self):
        """Test that fetch-related functions return integer values."""
        assert isinstance(get_fetch_timeout(), int)
        assert isinstance(get_fetch_size_limit(), int)
        assert get_fetch_timeout() > 0
        assert get_fetch_size_limit() > 0

    def test_environment_precedence(self):
        """Test that environment variables take precedence over defaults."""
        # Test timeout
        with patch.dict(os.environ, {"SBOXMGR_FETCH_TIMEOUT": "123"}):
            assert get_fetch_timeout() == 123
            
        # Test size limit  
        with patch.dict(os.environ, {"SBOXMGR_FETCH_SIZE_LIMIT": "456"}):
            assert get_fetch_size_limit() == 456
            
    def test_numeric_edge_cases(self):
        """Test handling of numeric edge cases."""
        # Zero values
        with patch.dict(os.environ, {"SBOXMGR_FETCH_TIMEOUT": "0"}):
            assert get_fetch_timeout() == 0
            
        with patch.dict(os.environ, {"SBOXMGR_FETCH_SIZE_LIMIT": "0"}):
            assert get_fetch_size_limit() == 0
            
        # Large values
        with patch.dict(os.environ, {"SBOXMGR_FETCH_TIMEOUT": "3600"}):  # 1 hour
            assert get_fetch_timeout() == 3600
            
        with patch.dict(os.environ, {"SBOXMGR_FETCH_SIZE_LIMIT": "104857600"}):  # 100MB
            assert get_fetch_size_limit() == 104857600

    def test_get_log_file_explicit_env(self):
        """Test that SBOXMGR_LOG_FILE environment variable is used when set."""
        with patch.dict(os.environ, {"SBOXMGR_LOG_FILE": "/custom/path/test.log"}):
            assert get_log_file() == "/custom/path/test.log"

    def test_get_log_file_no_env_success(self):
        """Test log file creation in user data directory when no env var is set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, 'home') as mock_home:
                with patch.object(Path, 'mkdir') as mock_mkdir:
                    with patch.object(Path, 'touch') as mock_touch:
                        with patch.object(Path, 'unlink') as mock_unlink:
                            mock_home.return_value = Path("/home/user")
                            
                            result = get_log_file()
                            
                            # Should return the user data directory path
                            assert result == "/home/user/.local/share/sboxmgr/sboxmgr.log"
                            # Should create directory with parents=True, exist_ok=True
                            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
                            # Should test write permissions
                            mock_touch.assert_called_once()
                            mock_unlink.assert_called_once()

    def test_get_log_file_fallback_on_permission_error(self):
        """Test fallback to current directory when user data dir is not writable."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, 'home') as mock_home:
                with patch.object(Path, 'mkdir', side_effect=PermissionError("No permission")):
                    mock_home.return_value = Path("/home/user")
                    
                    result = get_log_file()
                    
                    # Should fallback to current directory
                    assert result == "./sboxmgr.log"

    def test_get_log_file_fallback_on_os_error(self):
        """Test fallback to current directory when OS error occurs."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, 'home') as mock_home:
                with patch.object(Path, 'mkdir', side_effect=OSError("Disk full")):
                    mock_home.return_value = Path("/home/user")
                    
                    result = get_log_file()
                    
                    # Should fallback to current directory
                    assert result == "./sboxmgr.log"

    def test_get_log_file_fallback_on_touch_error(self):
        """Test fallback when write test fails."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, 'home') as mock_home:
                with patch.object(Path, 'touch', side_effect=PermissionError("Cannot write")):
                    mock_home.return_value = Path("/home/user")
                    
                    result = get_log_file()
                    
                    # Should fallback to current directory
                    assert result == "./sboxmgr.log"

    def test_get_url_priority_order(self):
        """Test that get_url respects priority: SBOXMGR_URL > SINGBOX_URL > TEST_URL."""
        # Test SBOXMGR_URL has highest priority
        with patch.dict(os.environ, {
            "SBOXMGR_URL": "url1",
            "SINGBOX_URL": "url2", 
            "TEST_URL": "url3"
        }):
            assert get_url() == "url1"
            
        # Test SINGBOX_URL has second priority
        with patch.dict(os.environ, {
            "SINGBOX_URL": "url2",
            "TEST_URL": "url3"
        }, clear=True):
            assert get_url() == "url2"
            
        # Test TEST_URL is used when others are not set
        with patch.dict(os.environ, {"TEST_URL": "url3"}, clear=True):
            assert get_url() == "url3"

    def test_get_url_empty_values(self):
        """Test that empty environment variables are treated as None."""
        # Empty SBOXMGR_URL should fall through to SINGBOX_URL
        with patch.dict(os.environ, {
            "SBOXMGR_URL": "",
            "SINGBOX_URL": "url2"
        }, clear=True):
            assert get_url() == "url2"
            
        # Empty SINGBOX_URL should fall through to TEST_URL  
        with patch.dict(os.environ, {
            "SBOXMGR_URL": "",
            "SINGBOX_URL": "",
            "TEST_URL": "url3"
        }, clear=True):
            assert get_url() == "url3"

    def test_get_url_all_empty_or_none(self):
        """Test that get_url returns None when no URLs are set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_url() is None
            
        # Test all empty strings - Python's `or` returns the last falsy value
        with patch.dict(os.environ, {
            "SBOXMGR_URL": "",
            "SINGBOX_URL": "",
            "TEST_URL": ""
        }, clear=True):
            # Empty string is falsy, so `or` chain returns the last empty string
            assert get_url() == ""

    def test_get_log_file_env_var_negation(self):
        """Test the critical if condition that mutation testing found."""
        # Test that when SBOXMGR_LOG_FILE is set, it's returned immediately
        with patch.dict(os.environ, {"SBOXMGR_LOG_FILE": "/explicit/log.txt"}):
            # This should NOT call the directory creation logic
            with patch.object(Path, 'mkdir') as mock_mkdir:
                result = get_log_file()
                assert result == "/explicit/log.txt"
                # mkdir should never be called when env var is set
                mock_mkdir.assert_not_called()
                
        # Test that when SBOXMGR_LOG_FILE is NOT set, directory logic is called
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, 'home') as mock_home:
                with patch.object(Path, 'touch'):
                    with patch.object(Path, 'unlink'):
                        mock_home.return_value = Path("/home/user")
                        
                        get_log_file()
                        
                        # mkdir SHOULD be called when env var is not set
                        mock_mkdir.assert_called_once() 