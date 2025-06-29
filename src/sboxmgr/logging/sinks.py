"""Logging sink detection and handler creation.

Implements LOG-01 from ADR-0010: Hybrid sink selection with auto-detection and fallback chain.
Provides automatic detection of available logging sinks and creates appropriate handlers.
"""

import os
import sys
import logging
import logging.handlers
from enum import Enum
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING, Union, Tuple
import subprocess

from ..config.detection import detect_systemd_environment

if TYPE_CHECKING:
    from ..config.models import LoggingConfig


class LogSink(Enum):
    """Available logging sinks with priority order."""
    
    AUTO = "auto"
    JOURNALD = "journald"
    SYSLOG = "syslog"
    STDOUT = "stdout"
    STDERR = "stderr"
    FILE = "file"


def detect_available_sinks() -> List[LogSink]:
    """Detect available logging sinks in order of preference.
    
    Implements the fallback chain: journald → syslog → stdout
    Uses environment detection to determine best available sink.
    
    Returns:
        List[LogSink]: Available sinks in preference order
        
    Example:
        >>> sinks = detect_available_sinks()
        >>> LogSink.STDOUT in sinks
        True
    """
    available = []
    
    # Check for systemd/journald (highest priority for services)
    if _is_journald_available():
        available.append(LogSink.JOURNALD)
    
    # Check for syslog (second priority for system services)
    if _is_syslog_available():
        available.append(LogSink.SYSLOG)
    
    # Stdout/stderr always available (lowest priority but universal)
    available.extend([LogSink.STDOUT, LogSink.STDERR])
    
    # File sink available if filesystem is writable
    available.append(LogSink.FILE)
    
    return available


def create_handler(
    sink: LogSink, 
    config: 'LoggingConfig',
    level: Optional[str] = None
) -> logging.Handler:
    """Create logging handler for specified sink.
    
    Creates appropriate handler based on sink type and configuration.
    Handles fallback to stdout if preferred sink fails.
    
    Args:
        sink: Target logging sink
        config: Logging configuration object
        level: Optional level override for this handler
        
    Returns:
        logging.Handler: Configured logging handler
        
    Raises:
        RuntimeError: If handler creation fails and no fallback available
        
    Example:
        >>> from sboxmgr.config import LoggingConfig
        >>> config = LoggingConfig()
        >>> handler = create_handler(LogSink.STDOUT, config)
        >>> isinstance(handler, logging.StreamHandler)
        True
    """
    try:
        if sink == LogSink.AUTO:
            # Auto-detection mode: use first available sink
            available_sinks = detect_available_sinks()
            preferred_sink = available_sinks[0] if available_sinks else LogSink.STDOUT
            return create_handler(preferred_sink, config, level)
        
        elif sink == LogSink.JOURNALD:
            return _create_journald_handler(config, level)
        
        elif sink == LogSink.SYSLOG:
            return _create_syslog_handler(config, level)
        
        elif sink == LogSink.STDOUT:
            return _create_stdout_handler(config, level)
        
        elif sink == LogSink.STDERR:
            return _create_stderr_handler(config, level)
        
        elif sink == LogSink.FILE:
            return _create_file_handler(config, level)
        
        else:
            raise ValueError(f"Unknown sink type: {sink}")
    
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as e:
        # Fallback to stdout if sink creation fails
        if sink != LogSink.STDOUT:
            logging.error(f"Failed to create {sink.value} handler: {e}, falling back to stdout")
            return _create_stdout_handler(config, level)
        else:
            raise RuntimeError(f"Failed to create fallback stdout handler: {e}")


def _is_journald_available() -> bool:
    """Check if journald is available and accessible.
    
    Returns:
        bool: True if journald is available
    """
    # Check if systemd environment is detected
    if not detect_systemd_environment():
        return False
    
    # Check if systemd-cat is available (indicates journald support)
    try:
        result = subprocess.run(
            ["systemd-cat", "--version"],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _is_syslog_available() -> bool:
    """Check if syslog is available.
    
    Returns:
        bool: True if syslog is available
    """
    # Check for common syslog socket locations
    syslog_paths = [
        "/dev/log",
        "/var/run/syslog",
        "/var/run/log"
    ]
    
    for path in syslog_paths:
        if os.path.exists(path):
            return True
    
    return False


def _create_journald_handler(config: 'LoggingConfig', level: Optional[str] = None) -> logging.Handler:
    """Create journald handler using systemd-cat.
    
    Args:
        config: Logging configuration
        level: Optional level override
        
    Returns:
        logging.Handler: Journald handler
    """
    try:
        # Try to import systemd journal handler
        from systemd import journal
        
        handler = journal.JournalHandler()
        handler.setLevel(level or config.level)
        
        # Add structured fields for journald
        handler.addFilter(_add_journald_fields)
        
        return handler
    
    except ImportError:
        # Fallback to systemd-cat pipe handler
        class SystemdCatHandler(logging.Handler):
            """Custom handler that pipes to systemd-cat."""
            
            def __init__(self):
                super().__init__()
                self.process = None
            
            def emit(self, record):
                """Emit log record to systemd-cat with proper error handling."""
                if not self.process or self.process.poll() is not None:
                    try:
                        self.process = subprocess.Popen(
                            ["systemd-cat", "-t", "sboxmgr"],
                            stdin=subprocess.PIPE,
                            text=True
                        )
                    except (OSError, subprocess.SubprocessError):
                        # Failed to start systemd-cat, silently ignore
                        self.process = None
                        return
                
                if self.process is None:
                    return
                
                try:
                    msg = self.format(record)
                    if self.process.stdin is not None:
                        self.process.stdin.write(msg + '\n')
                        self.process.stdin.flush()
                except (BrokenPipeError, OSError, AttributeError):
                    # systemd-cat died or stdin is None, cleanup and reset
                    self._cleanup_process()
                except (IOError, ValueError) as e:
                    # Other I/O or formatting errors, cleanup and reset
                    logging.debug(f"SystemdCat handler error: {e}")
                    self._cleanup_process()
            
            def _cleanup_process(self):
                """Clean up the systemd-cat process to prevent resource leaks."""
                if self.process is not None:
                    try:
                        if self.process.stdin:
                            self.process.stdin.close()
                        self.process.terminate()
                        # Give it a moment to terminate gracefully
                        try:
                            self.process.wait(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            # Force kill if it doesn't terminate
                            self.process.kill()
                            self.process.wait()
                    except (OSError, subprocess.SubprocessError):
                        # Process might already be dead, ignore
                        pass
                    finally:
                        self.process = None
            
            def close(self):
                """Close the handler and cleanup resources."""
                self._cleanup_process()
                super().close()
        
        handler = SystemdCatHandler()
        handler.setLevel(level or config.level)
        return handler


def _create_syslog_handler(config: 'LoggingConfig', level: Optional[str] = None) -> logging.Handler:
    """Create syslog handler.
    
    Args:
        config: Logging configuration
        level: Optional level override
        
    Returns:
        logging.Handler: Syslog handler
    """
    # Try different syslog addresses
    addresses: List[Union[str, Tuple[str, int]]] = [
        "/dev/log",
        ("localhost", 514)
    ]
    
    for address in addresses:
        try:
            # Convert list to tuple if needed for type compatibility
            if isinstance(address, list):
                address = tuple(address)
            handler = logging.handlers.SysLogHandler(address=address)
            handler.setLevel(level or config.level)
            return handler
        except (OSError, ConnectionError):
            continue
    
    raise RuntimeError("No syslog server available")


def _create_stdout_handler(config: 'LoggingConfig', level: Optional[str] = None) -> logging.Handler:
    """Create stdout handler.
    
    Args:
        config: Logging configuration
        level: Optional level override
        
    Returns:
        logging.Handler: Stdout handler
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level or config.level)
    return handler


def _create_stderr_handler(config: 'LoggingConfig', level: Optional[str] = None) -> logging.Handler:
    """Create stderr handler.
    
    Args:
        config: Logging configuration
        level: Optional level override
        
    Returns:
        logging.Handler: Stderr handler
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level or config.level)
    return handler


def _create_file_handler(config: 'LoggingConfig', level: Optional[str] = None) -> logging.Handler:
    """Create file handler with rotation.
    
    Args:
        config: Logging configuration
        level: Optional level override
        
    Returns:
        logging.Handler: File handler with rotation
        
    Raises:
        ValueError: If file path not configured
    """
    if not config.file_path:
        raise ValueError("File path not configured for file handler")
    
    # Ensure directory exists
    log_file = Path(config.file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create rotating file handler
    handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=config.max_file_size,
        backupCount=config.backup_count
    )
    handler.setLevel(level or config.level)
    
    return handler


def _add_journald_fields(record: logging.LogRecord) -> bool:
    """Add structured fields for journald.
    
    Args:
        record: Log record to enhance
        
    Returns:
        bool: Always True (don't filter)
    """
    # Add structured fields that journald can index
    record.SYSLOG_IDENTIFIER = "sboxmgr"
    record.PRIORITY = _get_syslog_priority(record.levelno)
    
    return True


def _get_syslog_priority(level: int) -> int:
    """Convert Python log level to syslog priority.
    
    Args:
        level: Python logging level
        
    Returns:
        int: Syslog priority value
    """
    mapping = {
        logging.DEBUG: 7,    # LOG_DEBUG
        logging.INFO: 6,     # LOG_INFO
        logging.WARNING: 4,  # LOG_WARNING
        logging.ERROR: 3,    # LOG_ERR
        logging.CRITICAL: 2, # LOG_CRIT
    }
    return mapping.get(level, 6)  # Default to INFO 