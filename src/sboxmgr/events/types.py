"""Event types and data structures for the event system."""

from enum import Enum, IntEnum
from typing import Any, Dict, Optional, Union, Callable
from datetime import datetime
from dataclasses import dataclass


class EventType(str, Enum):
    """Available event types in sboxmgr.
    
    These events cover the main lifecycle operations and can be used
    for monitoring, debugging, and plugin integration.
    """
    
    # Configuration events
    CONFIG_UPDATED = "config.updated"
    CONFIG_VALIDATED = "config.validated"
    CONFIG_GENERATED = "config.generated"
    CONFIG_BACKUP_CREATED = "config.backup.created"
    
    # Subscription events
    SUBSCRIPTION_FETCHED = "subscription.fetched"
    SUBSCRIPTION_PARSED = "subscription.parsed"
    SUBSCRIPTION_FILTERED = "subscription.filtered"
    
    # Service events
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"
    SERVICE_RESTARTED = "service.restarted"
    SERVICE_FAILED = "service.failed"
    
    # Agent events
    AGENT_VALIDATION_STARTED = "agent.validation.started"
    AGENT_VALIDATION_COMPLETED = "agent.validation.completed"
    AGENT_INSTALLATION_STARTED = "agent.installation.started"
    AGENT_INSTALLATION_COMPLETED = "agent.installation.completed"
    AGENT_CHECK_COMPLETED = "agent.check.completed"
    
    # Error events
    ERROR_OCCURRED = "error.occurred"
    WARNING_ISSUED = "warning.issued"
    
    # Plugin events
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"
    PLUGIN_ERROR = "plugin.error"
    
    # Debug events
    DEBUG_INFO = "debug.info"
    TRACE_POINT = "trace.point"


class EventPriority(IntEnum):
    """Event priority levels.
    
    Higher numbers indicate higher priority. Critical events are processed
    first, while debug events are processed last.
    """
    
    CRITICAL = 100
    HIGH = 80
    NORMAL = 50
    LOW = 20
    DEBUG = 10


@dataclass
class EventData:
    """Container for event data and metadata.
    
    This class holds all information related to an event, including
    the event payload, source information, and timing data.
    """
    
    event_type: EventType
    payload: Dict[str, Any]
    source: str
    timestamp: datetime
    priority: EventPriority = EventPriority.NORMAL
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from event payload.
        
        Args:
            key: Key to retrieve from payload
            default: Default value if key not found
            
        Returns:
            Value from payload or default
        """
        return self.payload.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set value in event payload.
        
        Args:
            key: Key to set in payload
            value: Value to set
        """
        self.payload[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event data to dictionary.
        
        Returns:
            Dictionary representation of event data
        """
        return {
            'event_type': self.event_type.value,
            'payload': self.payload,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'trace_id': self.trace_id,
            'session_id': self.session_id,
        }


# Type aliases for convenience
EventPayload = Dict[str, Any]
EventCallback = Union[Callable[..., Any], Any] 