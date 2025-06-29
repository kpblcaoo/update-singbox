"""Debug event handlers for monitoring and troubleshooting."""

from .types import EventType, EventData
from .core import EventHandler, get_event_manager
from .decorators import event_handler


class EventStatistics(EventHandler):
    """Event handler that collects statistics about events."""
    
    def __init__(self):
        self.event_counts = {}
        self.error_counts = {}
        self.source_counts = {}
    
    def can_handle(self, event_data: EventData) -> bool:
        """Always handle events for statistics."""
        return True
    
    def handle(self, event_data: EventData) -> None:
        """Collect statistics from the event."""
        event_type = event_data.event_type.value
        self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1
        
        source = event_data.source
        self.source_counts[source] = self.source_counts.get(source, 0) + 1
        
        if event_data.event_type == EventType.ERROR_OCCURRED:
            error_type = event_data.payload.get("error_type", "Unknown")
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def get_statistics(self) -> dict:
        """Get collected statistics."""
        return {
            "total_events": sum(self.event_counts.values()),
            "event_counts": self.event_counts.copy(),
            "error_counts": self.error_counts.copy(),
            "source_counts": self.source_counts.copy(),
        }


# Global statistics collector
_stats_collector = EventStatistics()


def get_event_statistics() -> dict:
    """Get global event statistics."""
    return _stats_collector.get_statistics()


@event_handler(EventType.ERROR_OCCURRED, EventType.WARNING_ISSUED, priority=90)
def log_errors_and_warnings(event_data: EventData) -> None:
    """Log error and warning events."""
    print(f"[{event_data.event_type.value}] {event_data.source}: {event_data.payload}")


@event_handler(EventType.CONFIG_UPDATED, EventType.CONFIG_VALIDATED, priority=70)
def log_config_events(event_data: EventData) -> None:
    """Log configuration-related events."""
    print(f"[CONFIG] {event_data.event_type.value}: {event_data.payload}")


# Register global statistics collector
get_event_manager().register_handler(_stats_collector)

