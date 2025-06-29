"""Tests for additional bug fixes in Stage 3: Pydantic validation bypass and Exception handling.

This file tests the specific bugs found in follow-up review.
"""

import pytest
import logging
from unittest.mock import patch, Mock
from pydantic import ValidationError

from sboxmgr.config.models import AppConfig, LoggingConfig
from sboxmgr.logging.sinks import create_handler, LogSink


class TestBugFixPydanticValidationBypass:
    """Test Bug Fix: Pydantic validation bypass in adjust_for_service_mode."""
    
    def test_service_mode_preserves_explicit_debug_level(self):
        """Test that explicit DEBUG level is preserved in service mode."""
        # Create config with explicit DEBUG level and service mode
        config = AppConfig(
            logging={'level': 'DEBUG', 'format': 'text'},
            service={'service_mode': True},
            app={'debug': False}  # debug=False but explicit DEBUG level should be kept
        )
        
        # BUG FIX: DEBUG level should be preserved even in service mode
        assert config.logging.level == "DEBUG"
        assert config.service.service_mode is True
        
        # Format should be adjusted to JSON for service mode
        assert config.logging.format == "json"
    
    def test_service_mode_format_adjustment_uses_model_copy(self):
        """Test that format adjustment uses model_copy to maintain validation."""
        config = AppConfig(
            logging={'level': 'INFO', 'format': 'text'},
            service={'service_mode': True}
        )
        
        # Should adjust format while maintaining validation
        assert config.logging.format == "json"
        assert config.logging.level == "INFO"
        
        # Verify the logging config is still a valid LoggingConfig instance
        assert isinstance(config.logging, LoggingConfig)
        
        # Test that validation still works on the new instance
        # Try to create invalid config - should raise ValidationError
        with pytest.raises(ValidationError):
            LoggingConfig(level='INVALID_LEVEL')
    
    def test_service_mode_sinks_adjustment_uses_model_copy(self):
        """Test that sinks adjustment uses model_copy to maintain validation."""
        config = AppConfig(
            logging={'sinks': ['auto']},
            service={'service_mode': True}
        )
        
        # Should adjust sinks while maintaining validation
        assert config.logging.sinks == ["journald"]
        
        # Verify the logging config is still a valid LoggingConfig instance
        assert isinstance(config.logging, LoggingConfig)
        
        # Test that validation still works - try to create invalid config
        with pytest.raises(ValidationError):
            LoggingConfig(sinks=['invalid_sink'])
    
    def test_non_service_mode_no_adjustments(self):
        """Test that non-service mode doesn't make any adjustments."""
        config = AppConfig(
            logging={'level': 'DEBUG', 'format': 'text', 'sinks': ['auto']},
            service={'service_mode': False}
        )
        
        # No adjustments should be made
        assert config.logging.level == "DEBUG"
        assert config.logging.format == "text"
        assert config.logging.sinks == ["auto"]


class TestBugFixBroadExceptionHandling:
    """Test Bug Fix: Broad Exception handling in logging sinks."""
    
    def test_sink_creation_specific_exception_handling(self):
        """Test that sink creation handles specific exceptions correctly."""
        from sboxmgr.config.models import LoggingConfig
        
        config = LoggingConfig(level="INFO")
        
        # Test that specific exceptions are caught and handled
        with patch('sboxmgr.logging.sinks._create_stdout_handler') as mock_stdout:
            with patch('sboxmgr.logging.sinks._create_journald_handler') as mock_journald:
                # Simulate OSError (specific exception)
                mock_journald.side_effect = OSError("systemd not available")
                mock_stdout.return_value = Mock()
                
                # Should catch OSError and fallback to stdout
                create_handler(LogSink.JOURNALD, config)
                
                # Should have attempted journald first, then fallen back
                mock_journald.assert_called_once()
                mock_stdout.assert_called_once()
    
    def test_sink_creation_does_not_catch_system_exceptions(self):
        """Test that system exceptions like KeyboardInterrupt are not caught."""
        from sboxmgr.config.models import LoggingConfig
        
        config = LoggingConfig(level="INFO")
        
        with patch('sboxmgr.logging.sinks._create_journald_handler') as mock_journald:
            # Simulate KeyboardInterrupt (should not be caught)
            mock_journald.side_effect = KeyboardInterrupt("User interrupted")
            
            # Should not catch KeyboardInterrupt
            with pytest.raises(KeyboardInterrupt):
                create_handler(LogSink.JOURNALD, config)
    
    def test_systemd_cat_handler_specific_exception_handling(self):
        """Test that SystemdCatHandler handles specific exceptions correctly."""
        from sboxmgr.logging.sinks import _create_journald_handler
        from sboxmgr.config.models import LoggingConfig
        
        config = LoggingConfig(level="INFO")
        
        with patch.dict('sys.modules', {'systemd': None}):
            with patch('sboxmgr.logging.sinks.subprocess.Popen') as mock_popen:
                mock_process = Mock()
                mock_stdin = Mock()
                mock_process.stdin = mock_stdin
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process
                
                handler = _create_journald_handler(config)
                
                # Test BrokenPipeError handling (specific exception)
                mock_stdin.write.side_effect = BrokenPipeError("Pipe broken")
                
                record = logging.LogRecord(
                    name='test', level=logging.INFO, pathname='', lineno=0,
                    msg='Test message', args=(), exc_info=None
                )
                
                # Should handle BrokenPipeError gracefully
                handler.emit(record)
                
                # Should have attempted to write and then cleaned up
                mock_stdin.write.assert_called_once()
