"""Core logging system with structured logging and multi-sink support.

Implements ADR-0010 Logging Core Architecture with automatic sink detection,
structured logging, and trace ID propagation.
"""

import logging
import logging.config
from typing import Dict, Optional

from ..config.models import LoggingConfig
from .sinks import LogSink, create_handler, detect_available_sinks
from .formatters import create_formatter
from .trace import get_trace_id


class LoggingCore:
    """Central logging system with multi-sink support and structured logging.
    
    Provides unified interface for configuring and managing logging across
    all sboxmgr components. Handles automatic sink detection, formatter
    selection, and trace ID propagation.
    """
    
    def __init__(self, config: LoggingConfig):
        """Initialize logging core with configuration.
        
        Args:
            config: Logging configuration object
        """
        self.config = config
        self._configured = False
        self._handlers: Dict[str, logging.Handler] = {}
        self._root_logger = logging.getLogger('sboxmgr')
    
    def configure(self) -> None:
        """Configure logging system based on configuration.
        
        Sets up handlers, formatters, and log levels according to
        configuration. Safe to call multiple times.
        """
        if self._configured:
            return
        
        # Clear existing handlers
        self._clear_existing_handlers()
        
        # Configure root logger level
        self._root_logger.setLevel(self.config.level)
        
        # Set up sinks
        self._setup_sinks()
        
        # Configure third-party loggers
        self._configure_third_party_loggers()
        
        self._configured = True
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get logger with structured logging support.
        
        Args:
            name: Logger name (e.g., 'sboxmgr.subscription.fetch')
            
        Returns:
            logging.Logger: Configured logger with trace ID support
            
        Example:
            >>> core = LoggingCore(config)
            >>> logger = core.get_logger('sboxmgr.test')
            >>> logger.info("Test message")
        """
        # Ensure logging is configured
        self.configure()
        
        # Get logger from standard hierarchy
        logger = logging.getLogger(name)
        
        # Add structured logging adapter if not already present
        structured_adapter = getattr(logger, '_structured_adapter', None)
        if structured_adapter is None:
            structured_adapter = StructuredLoggerAdapter(logger)
            setattr(logger, '_structured_adapter', structured_adapter)
        
        return structured_adapter
    
    def reconfigure(self, new_config: LoggingConfig) -> None:
        """Reconfigure logging with new settings.
        
        Args:
            new_config: New logging configuration
        """
        self.config = new_config
        self._configured = False
        self.configure()
    
    def _clear_existing_handlers(self) -> None:
        """Clear existing handlers from root logger."""
        for handler in self._root_logger.handlers[:]:
            self._root_logger.removeHandler(handler)
            handler.close()
        
        self._handlers.clear()
    
    def _setup_sinks(self) -> None:
        """Set up logging sinks based on configuration."""
        sinks_to_setup = self._determine_sinks()
        
        for sink_name, sink_config in sinks_to_setup.items():
            try:
                handler = self._create_sink_handler(sink_name, sink_config)
                self._handlers[sink_name] = handler
                self._root_logger.addHandler(handler)
            except Exception as e:
                # Log error but continue with other sinks
                # Use stderr directly since logging may not be fully initialized
                import sys
                print(f"Warning: Failed to setup {sink_name} sink: {e}", file=sys.stderr)
    
    def _determine_sinks(self) -> Dict[str, Dict]:
        """Determine which sinks to set up based on configuration.
        
        Returns:
            Dict[str, Dict]: Mapping of sink names to their configurations
        """
        sinks = {}
        
        # Process all configured sinks
        for i, sink_name in enumerate(self.config.sinks):
            # Convert string to LogSink enum
            if sink_name == "auto":
                available_sinks = detect_available_sinks()
                sink_enum = available_sinks[0] if available_sinks else LogSink.STDOUT
            else:
                sink_enum = LogSink(sink_name)
            
            # Get level override for this sink
            sink_level = self.config.sink_levels.get(sink_name, self.config.level)
            
            sinks[f'sink_{i}'] = {
                'sink': sink_enum,
                'level': sink_level,
                'format': self.config.format
            }
        
        return sinks
    
    def _create_sink_handler(self, sink_name: str, sink_config: Dict) -> logging.Handler:
        """Create handler for a specific sink.
        
        Args:
            sink_name: Name of the sink
            sink_config: Sink configuration
            
        Returns:
            logging.Handler: Configured handler
        """
        sink = sink_config['sink']
        level = sink_config.get('level', self.config.level)
        format_type = sink_config.get('format', self.config.format)
        
        # Create handler
        handler = create_handler(sink, self.config, level)
        
        # Create and set formatter
        formatter = self._create_formatter(format_type, sink)
        handler.setFormatter(formatter)
        
        return handler
    
    def _create_formatter(self, format_type: str, sink: LogSink) -> logging.Formatter:
        """Create formatter for sink.
        
        Args:
            format_type: Type of formatter
            sink: Target sink
            
        Returns:
            logging.Formatter: Configured formatter
        """
        # Auto-select formatter based on sink if format is 'auto'
        if format_type == 'auto':
            if sink in [LogSink.JOURNALD, LogSink.SYSLOG]:
                format_type = 'json'
            else:
                # Default to text format (human readable)
                format_type = 'text'
        
        return create_formatter(format_type, component='sboxmgr')
    
    def _configure_third_party_loggers(self) -> None:
        """Configure third-party library loggers."""
        # Suppress noisy third-party loggers
        noisy_loggers = [
            'urllib3.connectionpool',
            'requests.packages.urllib3',
            'httpx',
        ]
        
        for logger_name in noisy_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds structured logging capabilities.
    
    Automatically includes trace ID and provides convenience methods
    for structured logging with extra fields.
    """
    
    def __init__(self, logger: logging.Logger):
        """Initialize structured logger adapter.
        
        Args:
            logger: Base logger to wrap
        """
        super().__init__(logger, {})
    
    def process(self, msg, kwargs):
        """Process log message and add structured fields.
        
        Args:
            msg: Log message
            kwargs: Keyword arguments
            
        Returns:
            Tuple[str, Dict]: Processed message and extra fields
        """
        # Ensure 'extra' dict exists
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        # Add trace ID to extra fields
        kwargs['extra']['trace_id'] = get_trace_id()
        
        return msg, kwargs
    
    def log_operation(self, level: int, operation: str, message: str, **extra_fields) -> None:
        """Log with operation context.
        
        Args:
            level: Log level
            operation: Operation name
            message: Log message
            **extra_fields: Additional structured fields
        """
        extra = {'operation': operation}
        extra.update(extra_fields)
        self.log(level, message, extra=extra)
    
    def info_op(self, operation: str, message: str, **extra_fields) -> None:
        """Log info message with operation context.
        
        Args:
            operation: Operation name
            message: Log message
            **extra_fields: Additional structured fields
        """
        self.log_operation(logging.INFO, operation, message, **extra_fields)
    
    def error_op(self, operation: str, message: str, **extra_fields) -> None:
        """Log error message with operation context.
        
        Args:
            operation: Operation name
            message: Log message
            **extra_fields: Additional structured fields
        """
        self.log_operation(logging.ERROR, operation, message, **extra_fields)
    
    def debug_op(self, operation: str, message: str, **extra_fields) -> None:
        """Log debug message with operation context.
        
        Args:
            operation: Operation name
            message: Log message
            **extra_fields: Additional structured fields
        """
        self.log_operation(logging.DEBUG, operation, message, **extra_fields)


# Global logging core instance
_logging_core: Optional[LoggingCore] = None


def initialize_logging(config: LoggingConfig) -> LoggingCore:
    """Initialize global logging system.
    
    Args:
        config: Logging configuration
        
    Returns:
        LoggingCore: Configured logging core
    """
    global _logging_core
    _logging_core = LoggingCore(config)
    _logging_core.configure()
    return _logging_core


def get_logger(name: str) -> logging.Logger:
    """Get logger from global logging system.
    
    Args:
        name: Logger name
        
    Returns:
        logging.Logger: Configured logger
        
    Raises:
        RuntimeError: If logging not initialized
    """
    if _logging_core is None:
        raise RuntimeError("Logging not initialized. Call initialize_logging() first.")
    
    return _logging_core.get_logger(name)


def reconfigure_logging(config: LoggingConfig) -> None:
    """Reconfigure global logging system.
    
    Args:
        config: New logging configuration
        
    Raises:
        RuntimeError: If logging not initialized
    """
    if _logging_core is None:
        raise RuntimeError("Logging not initialized. Call initialize_logging() first.")
    
    _logging_core.reconfigure(config) 