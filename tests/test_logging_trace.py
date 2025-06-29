"""Tests for trace ID propagation system."""

import pytest
from unittest.mock import patch
import uuid

from sboxmgr.logging.trace import (
    get_trace_id,
    set_trace_id,
    with_trace_id,
    generate_trace_id,
    clear_trace_id,
    copy_trace_context,
)


class TestTraceId:
    """Test trace ID functionality."""
    
    def setup_method(self):
        """Clear trace ID before each test."""
        clear_trace_id()
    
    def test_get_trace_id_generates_new_id(self):
        """Test that get_trace_id generates new ID when none exists."""
        trace_id = get_trace_id()
        
        assert trace_id
        assert len(trace_id) == 8
        assert isinstance(trace_id, str)
    
    def test_get_trace_id_returns_same_id(self):
        """Test that subsequent calls return same trace ID."""
        trace_id1 = get_trace_id()
        trace_id2 = get_trace_id()
        
        assert trace_id1 == trace_id2
    
    def test_set_trace_id(self):
        """Test setting custom trace ID."""
        custom_id = "test1234"
        set_trace_id(custom_id)
        
        assert get_trace_id() == custom_id
    
    def test_set_trace_id_truncates_long_id(self):
        """Test that long trace IDs are truncated to 8 characters."""
        long_id = "verylongtraceidentifier"
        set_trace_id(long_id)
        
        result = get_trace_id()
        assert len(result) == 8
        assert result == long_id[:8]
    
    def test_clear_trace_id(self):
        """Test clearing trace ID."""
        set_trace_id("test1234")
        assert get_trace_id() == "test1234"
        
        clear_trace_id()
        
        # Next call should generate new ID
        new_id = get_trace_id()
        assert new_id != "test1234"
        assert len(new_id) == 8
    
    def test_generate_trace_id_no_side_effects(self):
        """Test that generate_trace_id doesn't affect current context."""
        set_trace_id("current")
        
        new_id = generate_trace_id()
        
        assert len(new_id) == 8
        assert new_id != "current"
        assert get_trace_id() == "current"  # Context unchanged
    
    def test_copy_trace_context(self):
        """Test copying current trace context."""
        set_trace_id("test1234")
        
        copied = copy_trace_context()
        
        assert copied == "test1234"
        assert copied == get_trace_id()
    
    def test_copy_trace_context_generates_if_none(self):
        """Test that copy_trace_context generates ID if none exists."""
        clear_trace_id()
        
        copied = copy_trace_context()
        
        assert len(copied) == 8
        assert copied == get_trace_id()


class TestWithTraceId:
    """Test trace ID context manager."""
    
    def setup_method(self):
        """Clear trace ID before each test."""
        clear_trace_id()
    
    def test_with_trace_id_custom_id(self):
        """Test context manager with custom trace ID."""
        with with_trace_id("custom12") as trace_id:
            assert trace_id == "custom12"
            assert get_trace_id() == "custom12"
        
        # Context should be reset after exiting
        new_id = get_trace_id()
        assert new_id != "custom12"
    
    def test_with_trace_id_auto_generate(self):
        """Test context manager with auto-generated trace ID."""
        with with_trace_id() as trace_id:
            assert len(trace_id) == 8
            assert get_trace_id() == trace_id
        
        # Context should be reset after exiting
        new_id = get_trace_id()
        assert new_id != trace_id
    
    def test_with_trace_id_nested_contexts(self):
        """Test nested trace ID contexts."""
        set_trace_id("outer123")
        
        with with_trace_id("inner456") as inner_id:
            assert get_trace_id() == "inner456"
            assert inner_id == "inner456"
            
            with with_trace_id("nested78") as nested_id:
                assert get_trace_id() == "nested78"
                assert nested_id == "nested78"
            
            # Back to inner context
            assert get_trace_id() == "inner456"
        
        # Back to outer context
        assert get_trace_id() == "outer123"
    
    def test_with_trace_id_exception_handling(self):
        """Test that context is properly reset even if exception occurs."""
        set_trace_id("original")
        
        try:
            with with_trace_id("temp1234"):
                assert get_trace_id() == "temp1234"
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Context should be reset to original
        assert get_trace_id() == "original"
    
    def test_with_trace_id_truncates_long_id(self):
        """Test that context manager truncates long trace IDs."""
        long_id = "verylongtraceidentifier"
        
        with with_trace_id(long_id) as trace_id:
            assert len(trace_id) == 8
            assert trace_id == long_id[:8]
            assert get_trace_id() == long_id[:8]


class TestTraceIdPropagation:
    """Test trace ID propagation across function calls."""
    
    def setup_method(self):
        """Clear trace ID before each test."""
        clear_trace_id()
    
    def test_trace_id_propagates_through_calls(self):
        """Test that trace ID propagates through function calls."""
        def inner_function():
            return get_trace_id()
        
        def outer_function():
            return inner_function()
        
        set_trace_id("propag12")  # 8 characters exactly
        
        result = outer_function()
        assert result == "propag12"
    
    def test_trace_id_isolation_between_contexts(self):
        """Test that different contexts have isolated trace IDs."""
        results = []
        
        def capture_trace_id(context_name):
            results.append((context_name, get_trace_id()))
        
        # Context 1
        with with_trace_id("context1"):
            capture_trace_id("ctx1")
        
        # Context 2
        with with_trace_id("context2"):
            capture_trace_id("ctx2")
        
        assert len(results) == 2
        assert results[0] == ("ctx1", "context1")
        assert results[1] == ("ctx2", "context2")
    
    @patch('uuid.uuid4')
    def test_uuid_generation_called(self, mock_uuid):
        """Test that UUID generation is called for new trace IDs."""
        mock_uuid.return_value = uuid.UUID('12345678-1234-5678-9012-123456789012')
        
        clear_trace_id()
        trace_id = get_trace_id()
        
        mock_uuid.assert_called_once()
        assert trace_id == "12345678"  # First 8 characters of UUID
    
    def test_contextvar_isolation(self):
        """Test that ContextVar properly isolates trace IDs."""
        import asyncio
        
        async def async_task(task_id):
            set_trace_id(f"task{task_id:04d}")
            await asyncio.sleep(0.01)  # Yield control
            return get_trace_id()
        
        async def run_concurrent_tasks():
            tasks = [async_task(i) for i in range(3)]
            results = await asyncio.gather(*tasks)
            return results
        
        # Run test if asyncio is available
        try:
            results = asyncio.run(run_concurrent_tasks())
            expected = ["task0000", "task0001", "task0002"]
            assert results == expected
        except RuntimeError:
            # Skip if no event loop (some test environments)
            pytest.skip("Asyncio not available in test environment") 