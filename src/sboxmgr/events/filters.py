"""Event filters for advanced event handling."""

from abc import ABC, abstractmethod
from typing import Optional, Set, Pattern, Any
import re

from .types import EventType, EventData


class EventFilter(ABC):
    """Abstract base class for event filters.
    
    Event filters are used to determine whether an event should be
    processed by a particular handler or system component.
    """
    
    @abstractmethod
    def matches(self, event_data: EventData) -> bool:
        """Check if event data matches this filter.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if event matches filter criteria
        """
        pass


class TypeFilter(EventFilter):
    """Filter events by type."""
    
    def __init__(self, *event_types: EventType):
        """Initialize type filter.
        
        Args:
            *event_types: Event types to match
        """
        self.event_types: Set[EventType] = set(event_types)
    
    def matches(self, event_data: EventData) -> bool:
        """Check if event type matches filter.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if event type is in filter set
        """
        return event_data.event_type in self.event_types


class SourceFilter(EventFilter):
    """Filter events by source."""
    
    def __init__(self, source: str, exact_match: bool = True):
        """Initialize source filter.
        
        Args:
            source: Source string or pattern to match
            exact_match: Whether to use exact string matching
        """
        self.source = source
        self.exact_match = exact_match
        self.pattern: Optional[Pattern] = None
        
        if not exact_match:
            self.pattern = re.compile(source)
    
    def matches(self, event_data: EventData) -> bool:
        """Check if event source matches filter.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if source matches filter criteria
        """
        if self.exact_match:
            return event_data.source == self.source
        else:
            return bool(self.pattern and self.pattern.search(event_data.source))


class PayloadFilter(EventFilter):
    """Filter events by payload content."""
    
    def __init__(self, key: str, value: Any = None, key_exists: bool = True):
        """Initialize payload filter.
        
        Args:
            key: Payload key to check
            value: Expected value (if None, only checks key existence)
            key_exists: Whether key should exist or not exist
        """
        self.key = key
        self.value = value
        self.key_exists = key_exists
    
    def matches(self, event_data: EventData) -> bool:
        """Check if event payload matches filter.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if payload matches filter criteria
        """
        has_key = self.key in event_data.payload
        
        # Check key existence requirement
        if has_key != self.key_exists:
            return False
        
        # If we only care about key existence, we're done
        if self.value is None:
            return True
        
        # Check value match
        if has_key:
            return event_data.payload[self.key] == self.value
        
        return False


class CompositeFilter(EventFilter):
    """Combine multiple filters with logical operations."""
    
    def __init__(self, *filters: EventFilter, operation: str = "AND"):
        """Initialize composite filter.
        
        Args:
            *filters: Filters to combine
            operation: Logical operation ("AND", "OR", "NOT")
        """
        self.filters = list(filters)
        self.operation = operation.upper()
        
        if self.operation not in ("AND", "OR", "NOT"):
            raise ValueError(f"Invalid operation: {operation}")
        
        if self.operation == "NOT" and len(self.filters) != 1:
            raise ValueError("NOT operation requires exactly one filter")
    
    def matches(self, event_data: EventData) -> bool:
        """Check if event matches composite filter.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if event matches composite criteria
        """
        if not self.filters:
            return True
        
        if self.operation == "AND":
            return all(f.matches(event_data) for f in self.filters)
        elif self.operation == "OR":
            return any(f.matches(event_data) for f in self.filters)
        elif self.operation == "NOT":
            return not self.filters[0].matches(event_data)
        
        return False


class PriorityFilter(EventFilter):
    """Filter events by priority level."""
    
    def __init__(self, min_priority: int = 0, max_priority: int = 100):
        """Initialize priority filter.
        
        Args:
            min_priority: Minimum priority level (inclusive)
            max_priority: Maximum priority level (inclusive)
        """
        self.min_priority = min_priority
        self.max_priority = max_priority
    
    def matches(self, event_data: EventData) -> bool:
        """Check if event priority matches filter.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if priority is within range
        """
        priority = event_data.priority.value
        return self.min_priority <= priority <= self.max_priority


class TraceFilter(EventFilter):
    """Filter events by trace ID."""
    
    def __init__(self, trace_id: str):
        """Initialize trace filter.
        
        Args:
            trace_id: Trace ID to match
        """
        self.trace_id = trace_id
    
    def matches(self, event_data: EventData) -> bool:
        """Check if event trace ID matches filter.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if trace ID matches
        """
        return event_data.trace_id == self.trace_id 