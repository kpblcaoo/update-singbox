"""Logging formatters for different output formats.

Implements LOG-02 from ADR-0010: Structured logging with basic fields.
Provides formatters for JSON, human-readable, and service mode outputs.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from .trace import get_trace_id


class StructuredFormatter(logging.Formatter):
    """Base formatter that adds structured fields to log records.
    
    Implements LOG-02 structured fields: timestamp, level, message, component, op, trace_id, pid.
    Provides foundation for JSON and human-readable formatters.
    """
    
    def __init__(self, component: str = "sboxmgr", **kwargs):
        """Initialize structured formatter.
        
        Args:
            component: Component name for structured logging
            **kwargs: Additional arguments passed to parent formatter
        """
        super().__init__(**kwargs)
        self.component = component
        self.pid = os.getpid()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured fields.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted log message
        """
        # Add structured fields to record
        self._add_structured_fields(record)
        
        # Call parent formatter
        return super().format(record)
    
    def _add_structured_fields(self, record: logging.LogRecord) -> None:
        """Add structured fields to log record.
        
        Args:
            record: Log record to enhance
        """
        # Basic structured fields from LOG-02 (UTC timestamps for structured logging)
        record.timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        record.component = self.component
        record.trace_id = get_trace_id()
        record.pid = self.pid
        
        # Operation context (extracted from logger name)
        record.op = self._extract_operation(record.name)
        
        # Additional context from record extras
        if hasattr(record, 'extra_fields'):
            for key, value in record.extra_fields.items():
                setattr(record, key, value)
    
    def _extract_operation(self, logger_name: str) -> str:
        """Extract operation name from logger name.
        
        Args:
            logger_name: Full logger name (e.g., 'sboxmgr.module.operation')
            
        Returns:
            str: Operation name (e.g., 'fetch')
        """
        parts = logger_name.split('.')
        if len(parts) >= 3:  # sboxmgr.module.operation
            return parts[-1]
        elif len(parts) == 2:  # sboxmgr.operation
            return parts[-1]
        else:
            return "unknown"


class JSONFormatter(StructuredFormatter):
    """JSON formatter for structured logging.
    
    Outputs log records as JSON objects with all structured fields.
    Ideal for service mode and log aggregation systems.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            str: JSON-formatted log message
        """
        # Add structured fields
        self._add_structured_fields(record)
        
        # Build JSON object with structured fields using getattr for safety
        log_obj = {
            "timestamp": getattr(record, 'timestamp', ''),
            "level": record.levelname,
            "message": record.getMessage(),
            "component": getattr(record, 'component', 'unknown'),
            "op": getattr(record, 'op', 'unknown'),
            "trace_id": getattr(record, 'trace_id', ''),
            "pid": getattr(record, 'pid', 0),
        }
        
        # Add logger name if different from component
        if record.name != self.component:
            log_obj["logger"] = record.name
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # Add stack trace if present
        if record.stack_info:
            log_obj["stack"] = record.stack_info
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in log_obj and not key.startswith('_') and key not in [
                'name', 'msg', 'args', 'levelno', 'levelname', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'exc_info', 'exc_text',
                'stack_info', 'timestamp', 'component', 'op', 'trace_id', 'pid'
            ]:
                log_obj[key] = value
        
        return json.dumps(log_obj, ensure_ascii=False, separators=(',', ':'))


class HumanFormatter(StructuredFormatter):
    """Human-readable formatter for CLI mode.
    
    Outputs log records in readable format with essential structured fields.
    Ideal for interactive CLI usage and development.
    """
    
    def __init__(self, component: str = "sboxmgr", show_trace_id: bool = True, **kwargs):
        """Initialize human formatter.
        
        Args:
            component: Component name for structured logging
            show_trace_id: Whether to show trace ID in output
            **kwargs: Additional arguments passed to parent formatter
        """
        super().__init__(component, **kwargs)
        self.show_trace_id = show_trace_id
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human reading.
        
        Args:
            record: Log record to format.
            
        Returns:
            str: Human-readable log message.
        """
        # Add structured fields
        self._add_structured_fields(record)
        
        # Build human-readable format
        parts = []
        
        # Timestamp (short format)
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        parts.append(timestamp)
        
        # Level with color
        level_colored = self._colorize_level(record.levelname)
        parts.append(f"[{level_colored}]")
        
        # Operation context
        op = getattr(record, 'op', 'unknown')
        if op != "unknown":
            parts.append(f"({op})")
        
        # Trace ID (if enabled)
        if self.show_trace_id:
            trace_id = getattr(record, 'trace_id', '')
            parts.append(f"[{trace_id}]")
        
        # Main message
        message = record.getMessage()
        parts.append(message)
        
        # Exception info (if present)
        if record.exc_info:
            exception_text = self.formatException(record.exc_info)
            parts.append(f"\n{exception_text}")
        
        return " ".join(parts)
    
    def _colorize_level(self, level: str) -> str:
        """Add color to log level for terminal output.
        
        Args:
            level: Log level name
            
        Returns:
            str: Colorized level name (if terminal supports colors)
        """
        # Skip coloring if not a TTY or NO_COLOR is set
        if not sys.stderr.isatty() or os.environ.get('NO_COLOR'):
            return level
        
        colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
        }
        
        reset = '\033[0m'
        color = colors.get(level, '')
        return f"{color}{level}{reset}" if color else level


class CompactFormatter(StructuredFormatter):
    """Compact formatter for high-volume logging.
    
    Outputs essential information in minimal format.
    Useful for performance-critical scenarios or log shipping.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record in compact format.
        
        Args:
            record: Log record to format.
            
        Returns:
            str: Compact log message.
        """
        # Add structured fields
        self._add_structured_fields(record)
        
        # Compact format: level:trace_id:op:message
        trace_id = getattr(record, 'trace_id', '')
        op = getattr(record, 'op', 'unknown')
        return f"{record.levelname[0]}:{trace_id}:{op}:{record.getMessage()}"


def create_formatter(
    format_type: str,
    component: str = "sboxmgr",
    **kwargs
) -> logging.Formatter:
    """Create formatter based on type.
    
    Factory function for creating appropriate formatter based on configuration.
    
    Args:
        format_type: Type of formatter ('json', 'text', 'compact')
        component: Component name for structured logging
        **kwargs: Additional arguments passed to formatter
        
    Returns:
        logging.Formatter: Configured formatter
        
    Raises:
        ValueError: If format_type is not supported
        
    Example:
        >>> formatter = create_formatter('json', component='test')
        >>> isinstance(formatter, JSONFormatter)
        True
    """
    formatters = {
        'json': JSONFormatter,
        'text': HumanFormatter,
        'human': HumanFormatter,  # Alias for backward compatibility
        'compact': CompactFormatter,
    }
    
    formatter_class = formatters.get(format_type.lower())
    if not formatter_class:
        available = ', '.join(formatters.keys())
        raise ValueError(f"Unknown formatter type '{format_type}'. Available: {available}")
    
    return formatter_class(component=component, **kwargs)


def get_default_formatter(service_mode: bool = False, component: str = "sboxmgr") -> logging.Formatter:
    """Get default formatter based on execution mode.
    
    Args:
        service_mode: Whether running in service mode
        component: Component name for structured logging
        
    Returns:
        logging.Formatter: Default formatter for the mode
    """
    if service_mode:
        return JSONFormatter(component=component)
    else:
        return HumanFormatter(component=component) 