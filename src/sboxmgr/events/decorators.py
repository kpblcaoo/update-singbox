"""Decorators for event handler registration."""

import functools
from typing import Callable, Set, Optional, Any
from .types import EventType, EventData
from .core import EventHandler, get_event_manager


class DecoratedEventHandler(EventHandler):
    """Event handler wrapper for decorated functions."""
    
    def __init__(self, func: Callable, event_types: Set[EventType], 
                 source_filter: Optional[str] = None, priority: int = 50):
        self.func = func
        self.event_types = event_types
        self.source_filter = source_filter
        self.priority = priority
    
    def can_handle(self, event_data: EventData) -> bool:
        """Check if this handler can process the event."""
        if event_data.event_type not in self.event_types:
            return False
        
        if self.source_filter and event_data.source != self.source_filter:
            return False
        
        return True
    
    def handle(self, event_data: EventData) -> Any:
        """Handle the event by calling the wrapped function."""
        return self.func(event_data)


def event_handler(*event_types: EventType, source: Optional[str] = None, 
                  priority: int = 50, auto_register: bool = True):
    """Decorator to mark a function as an event handler."""
    def decorator(func: Callable) -> Callable:
        handler = DecoratedEventHandler(
            func=func,
            event_types=set(event_types),
            source_filter=source,
            priority=priority
        )
        
        if auto_register:
            get_event_manager().register_handler(handler)
        
        setattr(func, '_event_handler', handler)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def async_event_handler(*event_types: EventType, source: Optional[str] = None,
                       priority: int = 50, auto_register: bool = True):
    """Decorator to mark an async function as an event handler."""
    def decorator(func: Callable) -> Callable:
        handler = DecoratedEventHandler(
            func=func,
            event_types=set(event_types),
            source_filter=source,
            priority=priority
        )
        
        if auto_register:
            get_event_manager().register_handler(handler)
        
        setattr(func, '_event_handler', handler)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator

