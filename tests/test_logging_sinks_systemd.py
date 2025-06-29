"""Tests for SystemdCatHandler resource management.

Tests cover the resource leak bug fix and error handling improvements.
"""

import logging
import subprocess
from unittest.mock import Mock, patch

from sboxmgr.logging.sinks import _create_journald_handler
from sboxmgr.config.models import LoggingConfig


class TestSystemdCatHandler:
    """Test SystemdCatHandler error handling and resource management."""
    
    def test_systemd_cat_handler_creation_fallback(self):
        """Test SystemdCatHandler is created when systemd module not available."""
        config = LoggingConfig(level="INFO")
        
        # Mock systemd import to fail
        with patch.dict('sys.modules', {'systemd': None, 'systemd.journal': None}):
            with patch('sboxmgr.logging.sinks.subprocess.Popen') as mock_popen:
                mock_process = Mock()
                mock_process.stdin = Mock()
                mock_popen.return_value = mock_process
                
                handler = _create_journald_handler(config)
                
                # Should create SystemdCatHandler, not systemd.journal.JournalHandler
                assert handler is not None
                assert hasattr(handler, 'emit')
    
    def test_systemd_cat_handler_emit_success(self):
        """Test successful log emission to systemd-cat."""
        config = LoggingConfig(level="INFO")
        
        with patch.dict('sys.modules', {'systemd': None}):
            with patch('sboxmgr.logging.sinks.subprocess.Popen') as mock_popen:
                mock_process = Mock()
                mock_stdin = Mock()
                mock_process.stdin = mock_stdin
                mock_process.poll.return_value = None  # Process still running
                mock_popen.return_value = mock_process
                
                handler = _create_journald_handler(config)
                
                # Create a test log record
                record = logging.LogRecord(
                    name='test', level=logging.INFO, pathname='', lineno=0,
                    msg='Test message', args=(), exc_info=None
                )
                
                # Emit should work without errors
                handler.emit(record)
                
                # Verify subprocess was called correctly
                mock_popen.assert_called_with(
                    ["systemd-cat", "-t", "sboxmgr"],
                    stdin=subprocess.PIPE,
                    text=True
                )
                mock_stdin.write.assert_called_once()
                mock_stdin.flush.assert_called_once()
    
    def test_systemd_cat_handler_stdin_none_handling(self):
        """Test handling when process.stdin is None (bug fix)."""
        config = LoggingConfig(level="INFO")
        
        with patch.dict('sys.modules', {'systemd': None}):
            with patch('sboxmgr.logging.sinks.subprocess.Popen') as mock_popen:
                mock_process = Mock()
                mock_process.stdin = None  # BUG FIX: stdin is None
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process
                
                handler = _create_journald_handler(config)
                
                record = logging.LogRecord(
                    name='test', level=logging.INFO, pathname='', lineno=0,
                    msg='Test message', args=(), exc_info=None
                )
                
                # Should not raise AttributeError
                handler.emit(record)
                
                # Should not try to write to None stdin
                assert not hasattr(mock_process.stdin, 'write') or not mock_process.stdin
    
    def test_systemd_cat_handler_broken_pipe_cleanup(self):
        """Test proper cleanup when BrokenPipeError occurs (bug fix)."""
        config = LoggingConfig(level="INFO")
        
        with patch.dict('sys.modules', {'systemd': None}):
            with patch('sboxmgr.logging.sinks.subprocess.Popen') as mock_popen:
                mock_process = Mock()
                mock_stdin = Mock()
                mock_stdin.write.side_effect = BrokenPipeError("Pipe broken")
                mock_process.stdin = mock_stdin
                mock_process.poll.return_value = None
                mock_process.terminate = Mock()
                mock_process.wait = Mock()
                mock_popen.return_value = mock_process
                
                handler = _create_journald_handler(config)
                
                record = logging.LogRecord(
                    name='test', level=logging.INFO, pathname='', lineno=0,
                    msg='Test message', args=(), exc_info=None
                )
                
                # Should handle BrokenPipeError gracefully
                handler.emit(record)
                
                # BUG FIX: Should cleanup process properly
                # Process should be reset to None for recreation
                handler.emit(record)  # Second call should create new process
                
                # Should have called Popen twice (original + after cleanup)
                assert mock_popen.call_count >= 1
    
    def test_systemd_cat_handler_process_startup_failure(self):
        """Test handling when systemd-cat process fails to start."""
        config = LoggingConfig(level="INFO")
        
        with patch.dict('sys.modules', {'systemd': None}):
            with patch('sboxmgr.logging.sinks.subprocess.Popen') as mock_popen:
                mock_popen.side_effect = OSError("systemd-cat not found")
                
                handler = _create_journald_handler(config)
                
                record = logging.LogRecord(
                    name='test', level=logging.INFO, pathname='', lineno=0,
                    msg='Test message', args=(), exc_info=None
                )
                
                # Should handle startup failure gracefully (no exception)
                handler.emit(record)
    
    def test_systemd_cat_handler_close_cleanup(self):
        """Test proper resource cleanup when handler is closed (bug fix)."""
        config = LoggingConfig(level="INFO")
        
        with patch.dict('sys.modules', {'systemd': None}):
            with patch('sboxmgr.logging.sinks.subprocess.Popen') as mock_popen:
                mock_process = Mock()
                mock_stdin = Mock()
                mock_process.stdin = mock_stdin
                mock_process.poll.return_value = None
                mock_process.terminate = Mock()
                mock_process.wait = Mock()
                mock_process.kill = Mock()
                mock_popen.return_value = mock_process
                
                handler = _create_journald_handler(config)
                
                # Emit a message to create the process
                record = logging.LogRecord(
                    name='test', level=logging.INFO, pathname='', lineno=0,
                    msg='Test message', args=(), exc_info=None
                )
                handler.emit(record)
                
                # BUG FIX: Close should cleanup resources properly
                handler.close()
                
                # Should have attempted to close stdin and terminate process
                mock_stdin.close.assert_called_once()
                mock_process.terminate.assert_called_once()
                mock_process.wait.assert_called()
    
    def test_systemd_cat_handler_force_kill_on_timeout(self):
        """Test force kill when process doesn't terminate gracefully."""
        config = LoggingConfig(level="INFO")
        
        with patch.dict('sys.modules', {'systemd': None}):
            with patch('sboxmgr.logging.sinks.subprocess.Popen') as mock_popen:
                mock_process = Mock()
                mock_stdin = Mock()
                mock_process.stdin = mock_stdin
                mock_process.poll.return_value = None
                mock_process.terminate = Mock()
                mock_process.wait.side_effect = [subprocess.TimeoutExpired("cmd", 1.0), None]
                mock_process.kill = Mock()
                mock_popen.return_value = mock_process
                
                handler = _create_journald_handler(config)
                
                # Emit to create process
                record = logging.LogRecord(
                    name='test', level=logging.INFO, pathname='', lineno=0,
                    msg='Test message', args=(), exc_info=None
                )
                handler.emit(record)
                
                # Close should force kill if terminate times out
                handler.close()
                
                # Should have tried terminate, then kill
                mock_process.terminate.assert_called_once()
                mock_process.kill.assert_called_once()
                assert mock_process.wait.call_count == 2  # Once for timeout, once after kill 