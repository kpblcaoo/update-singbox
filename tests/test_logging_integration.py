"""Integration tests for the complete logging system."""

import logging
import json
from io import StringIO

from sboxmgr.config.models import LoggingConfig
from sboxmgr.logging import (
    initialize_logging,
    get_logger,
    LoggingCore,
    set_trace_id,
)


class TestLoggingIntegration:
    """Test complete logging system integration."""
    
    def setup_method(self):
        """Reset logging state before each test."""
        # Clear any existing logging configuration
        logging.getLogger('sboxmgr').handlers.clear()
        logging.getLogger('sboxmgr').setLevel(logging.NOTSET)
    
    def test_initialize_and_get_logger(self):
        """Test initializing logging and getting loggers."""
        config = LoggingConfig(level="INFO", sinks=["stdout"], format="json")
        
        core = initialize_logging(config)
        
        assert isinstance(core, LoggingCore)
        
        logger = get_logger('sboxmgr.test')
        assert logger is not None
        assert hasattr(logger, 'info')
    
    def test_structured_logging_with_trace_id(self):
        """Test structured logging includes trace ID."""
        config = LoggingConfig(level="INFO", sinks=["stdout"], format="json")
        initialize_logging(config)
        
        # Get the handler and replace its stream with StringIO
        captured_output = StringIO()
        root_logger = logging.getLogger('sboxmgr')
        handler = root_logger.handlers[0]  # First handler should be stdout
        original_stream = handler.stream
        handler.stream = captured_output
        
        try:
            set_trace_id("test1234")
            logger = get_logger('sboxmgr.test')
            logger.info("Test message")
            
            output = captured_output.getvalue().strip()
            
            # Should be JSON formatted
            log_data = json.loads(output)
            assert log_data['message'] == "Test message"
            assert log_data['trace_id'] == "test1234"
            assert log_data['level'] == "INFO"
            assert log_data['component'] == "sboxmgr"
        finally:
            # Restore original stream
            handler.stream = original_stream 