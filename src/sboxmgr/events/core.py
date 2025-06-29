"""Core event system implementation."""

import asyncio
import threading
from typing import Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .types import EventType, EventPriority, EventData, EventPayload


def _get_logger():
    """Get logger lazily to avoid initialization issues."""
    try:
        from ..logging import get_logger
        return get_logger(__name__)
    except Exception:
        # Fallback to print for tests
        return None


def _get_trace_id():
    """Get trace ID lazily to avoid initialization issues."""
    try:
        from ..logging.trace import get_trace_id
        return get_trace_id()
    except Exception:
        return None


class EventHandler(ABC):
    """Abstract base class for event handlers.
    
    Event handlers can be synchronous or asynchronous and can filter
    events based on type, source, or custom criteria.
    """
    
    @abstractmethod
    def can_handle(self, event_data: EventData) -> bool:
        """Check if this handler can process the given event.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if handler can process this event
        """
        pass
    
    @abstractmethod
    def handle(self, event_data: EventData) -> Any:
        """Handle the event.
        
        Args:
            event_data: Event data to process
            
        Returns:
            Result of event processing (if any)
        """
        pass
    
    @property
    def is_async(self) -> bool:
        """Check if this handler is asynchronous.
        
        Returns:
            True if handler is async
        """
        return asyncio.iscoroutinefunction(self.handle)


@dataclass
class Event:
    """Event container with data and metadata.
    
    This class wraps EventData and provides additional functionality
    for event processing, including cancellation and result tracking.
    """
    
    data: EventData
    cancelled: bool = False
    processed: bool = False
    results: List[Any] = field(default_factory=list)
    errors: List[Exception] = field(default_factory=list)
    
    def cancel(self) -> None:
        """Cancel event processing."""
        self.cancelled = True
    
    def add_result(self, result: Any) -> None:
        """Add processing result.
        
        Args:
            result: Result from event handler
        """
        self.results.append(result)
    
    def add_error(self, error: Exception) -> None:
        """Add processing error.
        
        Args:
            error: Exception that occurred during processing
        """
        self.errors.append(error)
    
    @property
    def has_errors(self) -> bool:
        """Check if event processing had errors."""
        return len(self.errors) > 0
    
    @property
    def success(self) -> bool:
        """Check if event processing was successful."""
        return self.processed and not self.has_errors and not self.cancelled


class EventManager:
    """Central event manager for sboxmgr.
    
    This class manages event handlers, dispatches events, and provides
    both synchronous and asynchronous event processing capabilities.
    
    The manager is thread-safe and supports event filtering, priority
    handling, and error recovery.
    
    Example:
        >>> manager = EventManager()
        >>> manager.register_handler(my_handler)
        >>> manager.emit(EventType.CONFIG_UPDATED, {"path": "/config.json"})
    """
    
    def __init__(self, max_handlers: int = 100):
        """Initialize event manager.
        
        Args:
            max_handlers: Maximum number of handlers to register
        """
        self._handlers: List[EventHandler] = []
        self._max_handlers = max_handlers
        self._lock = threading.RLock()
        self._enabled = True
        self._event_history: List[Event] = []
        self._max_history = 1000
    
    def register_handler(self, handler: EventHandler) -> None:
        """Register an event handler.
        
        Args:
            handler: Event handler to register
            
        Raises:
            ValueError: If max handlers exceeded or handler already registered
        """
        with self._lock:
            if len(self._handlers) >= self._max_handlers:
                raise ValueError(f"Maximum handlers ({self._max_handlers}) exceeded")
            
            if handler in self._handlers:
                raise ValueError("Handler already registered")
            
            self._handlers.append(handler)
    
    def unregister_handler(self, handler: EventHandler) -> bool:
        """Unregister an event handler.
        
        Args:
            handler: Event handler to unregister
            
        Returns:
            True if handler was found and removed
        """
        with self._lock:
            try:
                self._handlers.remove(handler)
                return True
            except ValueError:
                return False
    
    def emit(self, event_type: EventType, payload: EventPayload, 
             source: str = "unknown", priority: EventPriority = EventPriority.NORMAL,
             trace_id: Optional[str] = None) -> Event:
        """Emit an event synchronously.
        
        Args:
            event_type: Type of event to emit
            payload: Event data payload
            source: Source component that emitted the event
            priority: Event priority level
            trace_id: Optional trace ID for correlation
            
        Returns:
            Event object with processing results
        """
        if not self._enabled:
            return self._create_cancelled_event(event_type, payload, source)
        
        event_data = EventData(
            event_type=event_type,
            payload=payload,
            source=source,
            timestamp=datetime.now(),
            priority=priority,
            trace_id=trace_id or _get_trace_id()
        )
        
        event = Event(data=event_data)
        
        try:
            self._process_event_sync(event)
        except Exception as e:
            event.add_error(e)
        finally:
            self._add_to_history(event)
        
        return event
    
    async def emit_async(self, event_type: EventType, payload: EventPayload,
                        source: str = "unknown", priority: EventPriority = EventPriority.NORMAL,
                        trace_id: Optional[str] = None) -> Event:
        """Emit an event asynchronously.
        
        Args:
            event_type: Type of event to emit
            payload: Event data payload
            source: Source component that emitted the event
            priority: Event priority level
            trace_id: Optional trace ID for correlation
            
        Returns:
            Event object with processing results
        """
        if not self._enabled:
            return self._create_cancelled_event(event_type, payload, source)
        
        event_data = EventData(
            event_type=event_type,
            payload=payload,
            source=source,
            timestamp=datetime.now(),
            priority=priority,
            trace_id=trace_id or _get_trace_id()
        )
        
        event = Event(data=event_data)
        
        try:
            await self._process_event_async(event)
        except Exception as e:
            event.add_error(e)
        finally:
            self._add_to_history(event)
        
        return event
    
    def get_handlers(self, event_type: Optional[EventType] = None) -> List[EventHandler]:
        """Get registered handlers, optionally filtered by event type.
        
        Args:
            event_type: Optional event type to filter by
            
        Returns:
            List of matching handlers
        """
        with self._lock:
            if event_type is None:
                return self._handlers.copy()
            
            # Create dummy event data for filtering
            dummy_data = EventData(
                event_type=event_type,
                payload={},
                source="filter",
                timestamp=datetime.now()
            )
            
            return [h for h in self._handlers if h.can_handle(dummy_data)]
    
    def enable(self) -> None:
        """Enable event processing."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable event processing."""
        self._enabled = False
    
    def clear_handlers(self) -> None:
        """Remove all registered handlers."""
        with self._lock:
            self._handlers.clear()
    
    def get_event_history(self, limit: Optional[int] = None) -> List[Event]:
        """Get event processing history.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of recent events
        """
        with self._lock:
            if limit is None:
                return self._event_history.copy()
            return self._event_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear event processing history."""
        with self._lock:
            self._event_history.clear()
    
    def _process_event_sync(self, event: Event) -> None:
        """Process event synchronously."""
        handlers = self._get_applicable_handlers(event.data)
        
        for handler in handlers:
            if event.cancelled:
                break
            
            try:
                if handler.is_async:
                    continue
                
                result = handler.handle(event.data)
                event.add_result(result)
                
            except Exception as e:
                event.add_error(e)
        
        event.processed = True
    
    async def _process_event_async(self, event: Event) -> None:
        """Process event asynchronously."""
        handlers = self._get_applicable_handlers(event.data)
        
        # Process sync handlers first
        for handler in handlers:
            if event.cancelled:
                break
            
            if not handler.is_async:
                try:
                    result = handler.handle(event.data)
                    event.add_result(result)
                except Exception as e:
                    event.add_error(e)
        
        # Process async handlers
        async_handlers = [h for h in handlers if h.is_async]
        if async_handlers and not event.cancelled:
            tasks = []
            for handler in async_handlers:
                task = asyncio.create_task(self._handle_async(handler, event.data))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    event.add_error(result)
                else:
                    event.add_result(result)
        
        event.processed = True
    
    async def _handle_async(self, handler: EventHandler, event_data: EventData) -> Any:
        """Handle async event handler."""
        try:
            return await handler.handle(event_data)
        except Exception as e:
            return e
    
    def _get_applicable_handlers(self, event_data: EventData) -> List[EventHandler]:
        """Get handlers that can process the given event."""
        with self._lock:
            return [h for h in self._handlers if h.can_handle(event_data)]
    
    def _create_cancelled_event(self, event_type: EventType, payload: EventPayload, source: str) -> Event:
        """Create a cancelled event when manager is disabled."""
        event_data = EventData(
            event_type=event_type,
            payload=payload,
            source=source,
            timestamp=datetime.now()
        )
        event = Event(data=event_data)
        event.cancel()
        return event
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to processing history."""
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)


# Global event manager instance
_event_manager: Optional[EventManager] = None
_manager_lock = threading.Lock()


def get_event_manager() -> EventManager:
    """Get the global event manager instance.
    
    Returns:
        Global EventManager instance
    """
    global _event_manager
    
    if _event_manager is None:
        with _manager_lock:
            if _event_manager is None:
                _event_manager = EventManager()
    
    return _event_manager


def emit_event(event_type: EventType, payload: EventPayload, 
               source: str = "unknown", priority: EventPriority = EventPriority.NORMAL) -> Event:
    """Convenience function to emit events using global manager.
    
    Args:
        event_type: Type of event to emit
        payload: Event data payload
        source: Source component that emitted the event
        priority: Event priority level
        
    Returns:
        Event object with processing results
    """
    return get_event_manager().emit(event_type, payload, source, priority) 