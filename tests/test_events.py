"""Tests for the event system."""

from datetime import datetime

from src.sboxmgr.events import (
    EventManager, EventHandler, EventType, EventPriority, EventData,
    TypeFilter, get_event_manager, emit_event
)


class TestEventHandler(EventHandler):
    """Test event handler for testing."""
    
    def __init__(self, event_types=None):
        self.event_types = event_types or {EventType.CONFIG_UPDATED}
        self.handled_events = []
    
    def can_handle(self, event_data: EventData) -> bool:
        return event_data.event_type in self.event_types
    
    def handle(self, event_data: EventData):
        self.handled_events.append(event_data)
        return f"handled_{event_data.event_type.value}"


class TestEventTypes:
    """Test event type definitions."""
    
    def test_event_types_exist(self):
        """Test that all expected event types are defined."""
        assert EventType.CONFIG_UPDATED == "config.updated"
        assert EventType.CONFIG_VALIDATED == "config.validated"
        assert EventType.ERROR_OCCURRED == "error.occurred"


class TestEventData:
    """Test EventData class."""
    
    def test_event_data_creation(self):
        """Test EventData creation and basic functionality."""
        payload = {"key": "value", "count": 42}
        timestamp = datetime.now()
        
        event_data = EventData(
            event_type=EventType.CONFIG_UPDATED,
            payload=payload,
            source="test",
            timestamp=timestamp,
            priority=EventPriority.HIGH
        )
        
        assert event_data.event_type == EventType.CONFIG_UPDATED
        assert event_data.payload == payload
        assert event_data.source == "test"
        assert event_data.priority == EventPriority.HIGH
    
    def test_event_data_get_set(self):
        """Test EventData get/set methods."""
        event_data = EventData(
            event_type=EventType.CONFIG_UPDATED,
            payload={"existing": "value"},
            source="test",
            timestamp=datetime.now()
        )
        
        assert event_data.get("existing") == "value"
        assert event_data.get("missing", "default") == "default"
        
        event_data.set("new_key", "new_value")
        assert event_data.get("new_key") == "new_value"


class TestEventManager:
    """Test EventManager class."""
    
    def test_event_manager_creation(self):
        """Test EventManager creation."""
        manager = EventManager(max_handlers=50)
        assert len(manager._handlers) == 0
        assert manager._max_handlers == 50
    
    def test_handler_registration(self):
        """Test handler registration."""
        manager = EventManager()
        handler = TestEventHandler()
        
        manager.register_handler(handler)
        assert handler in manager._handlers
    
    def test_event_emission(self):
        """Test basic event emission."""
        manager = EventManager()
        handler = TestEventHandler({EventType.CONFIG_UPDATED})
        
        manager.register_handler(handler)
        
        event = manager.emit(
            EventType.CONFIG_UPDATED,
            {"key": "value"},
            source="test"
        )
        
        assert event.processed is True
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0].event_type == EventType.CONFIG_UPDATED


class TestEventFilters:
    """Test event filter classes."""
    
    def test_type_filter(self):
        """Test TypeFilter functionality."""
        filter_obj = TypeFilter(EventType.CONFIG_UPDATED)
        
        config_event = EventData(
            event_type=EventType.CONFIG_UPDATED,
            payload={},
            source="test",
            timestamp=datetime.now()
        )
        
        agent_event = EventData(
            event_type=EventType.AGENT_VALIDATION_STARTED,
            payload={},
            source="test",
            timestamp=datetime.now()
        )
        
        assert filter_obj.matches(config_event) is True
        assert filter_obj.matches(agent_event) is False


class TestGlobalEventManager:
    """Test global event manager functions."""
    
    def test_get_event_manager_singleton(self):
        """Test that get_event_manager returns singleton."""
        manager1 = get_event_manager()
        manager2 = get_event_manager()
        
        assert manager1 is manager2
    
    def test_emit_event_function(self):
        """Test emit_event convenience function."""
        manager = get_event_manager()
        manager.clear_handlers()
        
        handler = TestEventHandler({EventType.CONFIG_UPDATED})
        manager.register_handler(handler)
        
        event = emit_event(
            EventType.CONFIG_UPDATED,
            {"test": "data"},
            source="test_source"
        )
        
        assert event.processed is True
        assert len(handler.handled_events) == 1

