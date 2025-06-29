"""Tests for logging sinks detection and handler creation."""

import pytest
import logging
import sys
from unittest.mock import patch

from sboxmgr.logging.sinks import (
    LogSink,
    detect_available_sinks,
    create_handler,
    _is_journald_available,
    _is_syslog_available,
    _create_file_handler,
)
from sboxmgr.config.models import LoggingConfig


class TestLogSink:
    """Test LogSink enum."""
    
    def test_log_sink_values(self):
        """Test that LogSink has expected values."""
        assert LogSink.AUTO.value == "auto"
        assert LogSink.JOURNALD.value == "journald"
        assert LogSink.SYSLOG.value == "syslog"
        assert LogSink.STDOUT.value == "stdout"
        assert LogSink.STDERR.value == "stderr"
        assert LogSink.FILE.value == "file"


class TestDetectAvailableSinks:
    """Test sink detection functionality."""
    
    @patch('sboxmgr.logging.sinks._is_journald_available')
    @patch('sboxmgr.logging.sinks._is_syslog_available')
    def test_detect_all_available(self, mock_syslog, mock_journald):
        """Test detection when all sinks are available."""
        mock_journald.return_value = True
        mock_syslog.return_value = True
        
        sinks = detect_available_sinks()
        
        expected = [LogSink.JOURNALD, LogSink.SYSLOG, LogSink.STDOUT, LogSink.STDERR, LogSink.FILE]
        assert sinks == expected
    
    @patch('sboxmgr.logging.sinks._is_journald_available')
    @patch('sboxmgr.logging.sinks._is_syslog_available')
    def test_detect_minimal_available(self, mock_syslog, mock_journald):
        """Test detection when only basic sinks are available."""
        mock_journald.return_value = False
        mock_syslog.return_value = False
        
        sinks = detect_available_sinks()
        
        expected = [LogSink.STDOUT, LogSink.STDERR, LogSink.FILE]
        assert sinks == expected
    
    @patch('sboxmgr.logging.sinks._is_journald_available')
    @patch('sboxmgr.logging.sinks._is_syslog_available')
    def test_detect_partial_available(self, mock_syslog, mock_journald):
        """Test detection when some sinks are available."""
        mock_journald.return_value = False
        mock_syslog.return_value = True
        
        sinks = detect_available_sinks()
        
        expected = [LogSink.SYSLOG, LogSink.STDOUT, LogSink.STDERR, LogSink.FILE]
        assert sinks == expected


class TestJournaldDetection:
    """Test journald availability detection."""
    
    @patch('sboxmgr.logging.sinks.detect_systemd_environment')
    def test_journald_not_available_no_systemd(self, mock_systemd):
        """Test journald detection when systemd not available."""
        mock_systemd.return_value = False
        
        result = _is_journald_available()
        
        assert result is False
    
    @patch('sboxmgr.logging.sinks.detect_systemd_environment')
    @patch('subprocess.run')
    def test_journald_available_with_systemd_cat(self, mock_run, mock_systemd):
        """Test journald detection when systemd-cat is available."""
        mock_systemd.return_value = True
        mock_run.return_value.returncode = 0
        
        result = _is_journald_available()
        
        assert result is True
        mock_run.assert_called_once_with(
            ["systemd-cat", "--version"],
            capture_output=True,
            timeout=2
        )
    
    @patch('sboxmgr.logging.sinks.detect_systemd_environment')
    @patch('subprocess.run')
    def test_journald_not_available_systemd_cat_fails(self, mock_run, mock_systemd):
        """Test journald detection when systemd-cat fails."""
        mock_systemd.return_value = True
        mock_run.return_value.returncode = 1
        
        result = _is_journald_available()
        
        assert result is False
    
    @patch('sboxmgr.logging.sinks.detect_systemd_environment')
    @patch('subprocess.run')
    def test_journald_not_available_exception(self, mock_run, mock_systemd):
        """Test journald detection when subprocess raises exception."""
        mock_systemd.return_value = True
        mock_run.side_effect = FileNotFoundError()
        
        result = _is_journald_available()
        
        assert result is False


class TestSyslogDetection:
    """Test syslog availability detection."""
    
    @patch('os.path.exists')
    def test_syslog_available_dev_log(self, mock_exists):
        """Test syslog detection when /dev/log exists."""
        mock_exists.side_effect = lambda path: path == "/dev/log"
        
        result = _is_syslog_available()
        
        assert result is True
        mock_exists.assert_called_with("/dev/log")
    
    @patch('os.path.exists')
    def test_syslog_available_var_run_syslog(self, mock_exists):
        """Test syslog detection when /var/run/syslog exists."""
        mock_exists.side_effect = lambda path: path == "/var/run/syslog"
        
        result = _is_syslog_available()
        
        assert result is True
    
    @patch('os.path.exists')
    def test_syslog_not_available(self, mock_exists):
        """Test syslog detection when no syslog socket exists."""
        mock_exists.return_value = False
        
        result = _is_syslog_available()
        
        assert result is False


class TestCreateHandler:
    """Test handler creation functionality."""
    
    def test_create_stdout_handler(self):
        """Test creating stdout handler."""
        config = LoggingConfig()
        
        handler = create_handler(LogSink.STDOUT, config)
        
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stdout
        assert handler.level == logging.INFO  # Default level
    
    def test_create_stderr_handler(self):
        """Test creating stderr handler."""
        config = LoggingConfig()
        
        handler = create_handler(LogSink.STDERR, config)
        
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stderr
    
    def test_create_handler_with_level_override(self):
        """Test creating handler with level override."""
        config = LoggingConfig()
        
        handler = create_handler(LogSink.STDOUT, config, level="DEBUG")
        
        assert handler.level == logging.DEBUG
    
    @patch('sboxmgr.logging.sinks.detect_available_sinks')
    def test_create_auto_handler(self, mock_detect):
        """Test creating handler with AUTO sink."""
        config = LoggingConfig()
        mock_detect.return_value = [LogSink.STDOUT, LogSink.STDERR]
        
        handler = create_handler(LogSink.AUTO, config)
        
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stdout  # First available
    
    def test_create_handler_fallback_on_error(self):
        """Test that handler creation falls back to stdout on error."""
        config = LoggingConfig()
        
        # Force an error by using invalid sink (this should trigger fallback)
        with patch('sboxmgr.logging.sinks._create_journald_handler') as mock_journald:
            mock_journald.side_effect = RuntimeError("Journald not available")
            
            handler = create_handler(LogSink.JOURNALD, config)
            
            # Should fallback to stdout
            assert isinstance(handler, logging.StreamHandler)
            assert handler.stream is sys.stdout
    
    def test_create_handler_unknown_sink(self):
        """Test creating handler with unknown sink type."""
        config = LoggingConfig()
        
        # Create a mock sink that doesn't exist
        class UnknownSink:
            value = "unknown"
        
        unknown_sink = UnknownSink()
        
        # Should fallback to stdout
        handler = create_handler(unknown_sink, config)
        assert isinstance(handler, logging.StreamHandler)


class TestFileHandler:
    """Test file handler creation."""
    
    def test_create_file_handler_success(self, tmp_path):
        """Test creating file handler successfully."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(file_path=str(log_file))
        
        handler = _create_file_handler(config)
        
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.baseFilename == str(log_file)
    
    def test_create_file_handler_creates_directory(self, tmp_path):
        """Test that file handler creates parent directories."""
        log_file = tmp_path / "logs" / "subdir" / "test.log"
        # Create a minimal config that bypasses validation
        config = LoggingConfig()
        config.file_path = str(log_file)
        
        handler = _create_file_handler(config)
        
        assert log_file.parent.exists()
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
    
    def test_create_file_handler_no_path(self):
        """Test file handler creation without file path."""
        config = LoggingConfig(file_path=None)
        
        with pytest.raises(ValueError, match="File path not configured"):
            _create_file_handler(config)
    
    def test_create_file_handler_with_rotation(self, tmp_path):
        """Test file handler with rotation settings."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            file_path=str(log_file),
            max_file_size=1024 * 1024,  # 1MB
            backup_count=5
        )
        
        handler = _create_file_handler(config)
        
        assert handler.maxBytes == 1024 * 1024
        assert handler.backupCount == 5


class TestHandlerIntegration:
    """Test handler integration with formatters."""
    
    def test_handler_receives_formatter(self):
        """Test that created handlers can be configured with formatters."""
        config = LoggingConfig()
        
        handler = create_handler(LogSink.STDOUT, config)
        
        # Handler should be created without formatter initially
        assert handler.formatter is None
        
        # Should be able to set formatter
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        
        assert handler.formatter is formatter
    
    def test_handler_level_configuration(self):
        """Test handler level configuration."""
        config = LoggingConfig(level="WARNING")
        
        handler = create_handler(LogSink.STDOUT, config)
        
        assert handler.level == logging.WARNING
    
    def test_multiple_handlers_independent(self):
        """Test that multiple handlers are independent."""
        config = LoggingConfig()
        
        handler1 = create_handler(LogSink.STDOUT, config, level="INFO")
        handler2 = create_handler(LogSink.STDERR, config, level="ERROR")
        
        assert handler1.level == logging.INFO
        assert handler2.level == logging.ERROR
        assert handler1 is not handler2 