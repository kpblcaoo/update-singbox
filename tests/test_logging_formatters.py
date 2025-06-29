"""Tests for logging formatters.

Tests cover the UTC timestamp bug fix and other formatter functionality.
"""

import pytest
import json
import logging
from unittest.mock import patch

from sboxmgr.logging.formatters import (
    StructuredFormatter,
    JSONFormatter,
    HumanFormatter,
    create_formatter
)


class TestStructuredFormatter:
    """Test structured formatter base functionality."""
    
    def test_utc_timestamps_in_structured_logging(self):
        """Test that structured logging uses UTC timestamps (bug fix)."""
        formatter = StructuredFormatter()
        
        # Create a log record with fixed timestamp
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        record.created = 1640995200.0  # 2022-01-01 00:00:00 UTC
        
        # Add structured fields
        formatter._add_structured_fields(record)
        
        # BUG FIX: Verify timestamp is in UTC with timezone info
        assert hasattr(record, 'timestamp')
        assert record.timestamp == "2022-01-01T00:00:00+00:00"
        assert record.timestamp.endswith("+00:00")  # UTC timezone
    
    def test_structured_fields_added(self):
        """Test that all required structured fields are added."""
        formatter = StructuredFormatter(component="test-component")
        
        record = logging.LogRecord(
            name='sboxmgr.module.operation', level=logging.INFO, 
            pathname='', lineno=0, msg='Test message', args=(), exc_info=None
        )
        record.created = 1640995200.0
        
        formatter._add_structured_fields(record)
        
        # Verify all structured fields are present
        assert hasattr(record, 'timestamp')
        assert hasattr(record, 'component')
        assert hasattr(record, 'trace_id')
        assert hasattr(record, 'pid')
        assert hasattr(record, 'op')
        
        assert record.component == "test-component"
        assert record.op == "operation"  # Extracted from logger name


class TestJSONFormatter:
    """Test JSON formatter functionality."""
    
    def test_json_format_with_utc_timestamp(self):
        """Test JSON formatter includes UTC timestamp."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        record.created = 1640995200.0
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # BUG FIX: Verify JSON output has UTC timestamp
        assert log_data['timestamp'] == "2022-01-01T00:00:00+00:00"
        assert log_data['level'] == "INFO"
        assert log_data['message'] == "Test message"
    
    def test_json_format_structure(self):
        """Test JSON formatter produces correct structure."""
        formatter = JSONFormatter(component="test-app")
        
        record = logging.LogRecord(
            name='test.module', level=logging.ERROR, pathname='', lineno=0,
            msg='Error message', args=(), exc_info=None
        )
        record.created = 1640995200.0
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # Verify required fields
        required_fields = ['timestamp', 'level', 'message', 'component', 'op', 'trace_id', 'pid']
        for field in required_fields:
            assert field in log_data
        
        assert log_data['component'] == "test-app"
        assert log_data['level'] == "ERROR"


class TestHumanFormatter:
    """Test human-readable formatter functionality."""
    
    def test_human_format_includes_trace_id(self):
        """Test human formatter includes trace ID when enabled."""
        formatter = HumanFormatter(show_trace_id=True)
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        record.created = 1640995200.0
        
        with patch('sboxmgr.logging.formatters.get_trace_id', return_value='test123'):
            formatted = formatter.format(record)
        
        # Should include trace ID in brackets
        assert '[test123]' in formatted
        assert 'Test message' in formatted
    
    def test_human_format_without_trace_id(self):
        """Test human formatter excludes trace ID when disabled."""
        formatter = HumanFormatter(show_trace_id=False)
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        record.created = 1640995200.0
        
        with patch('sboxmgr.logging.formatters.get_trace_id', return_value='test123'):
            formatted = formatter.format(record)
        
        # Should not include trace ID
        assert '[test123]' not in formatted
        assert 'Test message' in formatted


class TestCreateFormatter:
    """Test formatter factory function."""
    
    def test_create_json_formatter(self):
        """Test creating JSON formatter."""
        formatter = create_formatter('json', component='test')
        
        assert isinstance(formatter, JSONFormatter)
    
    def test_create_text_formatter(self):
        """Test creating text/human formatter."""
        formatter = create_formatter('text', component='test')
        
        assert isinstance(formatter, HumanFormatter)
    
    def test_create_unknown_formatter(self):
        """Test error when creating unknown formatter type."""
        with pytest.raises(ValueError) as exc_info:
            create_formatter('unknown', component='test')
        
        assert "Unknown formatter type 'unknown'" in str(exc_info.value) 