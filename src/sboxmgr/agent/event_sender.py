"""Event sender for sboxmgr -> sboxagent communication.

This module implements the EventSender class that sends events from sboxmgr
to sboxagent via Unix socket using the framed JSON protocol.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .ipc.socket_client import SocketClient
from sboxmgr.logging import get_logger


def _get_logger():
    """Get logger with lazy initialization."""
    try:
        return get_logger(__name__)
    except RuntimeError:
        # Fallback to basic logger if logging not initialized
        import logging
        return logging.getLogger(__name__)


logger = _get_logger()


class EventSenderError(Exception):
    """Base exception for event sender errors."""
    pass


class AgentNotConnectedError(EventSenderError):
    """Raised when agent is not connected."""
    pass


class EventSender:
    """Sends events to sboxagent via Unix socket.
    
    This class handles sending structured events from sboxmgr to sboxagent
    using the standardized framed JSON protocol over Unix socket.
    
    Args:
        socket_path: Path to Unix socket (default: /tmp/sboxagent.sock)
        timeout: Connection timeout in seconds
        
    Example:
        >>> sender = EventSender()
        >>> if sender.is_connected():
        ...     sender.send_event("subscription_updated", {
        ...         "subscription_url": "https://...",
        ...         "servers_count": 150
        ...     })
    """
    
    def __init__(self, socket_path: str = "/tmp/sboxagent.sock", timeout: float = 5.0):
        """Initialize the event sender.
        
        Args:
            socket_path: Path to Unix socket
            timeout: Connection timeout in seconds
        """
        self.socket_path = socket_path
        self.timeout = timeout
        self._client: Optional[SocketClient] = None
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to sboxagent.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self._client:
                self._client.close()
            
            self._client = SocketClient(self.socket_path, self.timeout)
            self._client.connect()
            self._connected = True
            
            _get_logger().info("Connected to sboxagent", extra={
                "socket_path": self.socket_path
            })
            
            return True
            
        except Exception as e:
            _get_logger().debug(f"Failed to connect to sboxagent: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from sboxagent."""
        if self._client:
            self._client.close()
            self._client = None
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to sboxagent.
        
        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._client is not None
    
    def send_event(self, 
                   event_type: str,
                   event_data: Dict[str, Any],
                   source: str = "sboxmgr",
                   priority: str = "normal",
                   correlation_id: Optional[str] = None) -> bool:
        """Send an event to sboxagent.
        
        Args:
            event_type: Type of event (e.g., "subscription_updated")
            event_data: Event data dictionary
            source: Event source component
            priority: Event priority (low, normal, high, critical)
            correlation_id: Optional correlation ID
            
        Returns:
            True if event sent successfully, False otherwise
            
        Raises:
            AgentNotConnectedError: If not connected to agent
            EventSenderError: If sending fails
            
        Example:
            >>> sender.send_event("config_generated", {
            ...     "client_type": "sing-box",
            ...     "config_size": 1024,
            ...     "generation_time_ms": 250
            ... })
        """
        if not self.is_connected():
            if not self.connect():
                raise AgentNotConnectedError("Cannot connect to sboxagent")
        
        # Create event message
        message = self._create_event_message(
            event_type=event_type,
            event_data=event_data,
            source=source,
            priority=priority,
            correlation_id=correlation_id
        )
        
        try:
            # Send message
            self._client.send_message(message)
            
            # Wait for acknowledgment
            response = self._client.recv_message()
            
            if response.get("type") == "response":
                response_data = response.get("response", {})
                if response_data.get("status") == "success":
                    _get_logger().debug("Event sent successfully", extra={
                        "event_type": event_type,
                        "message_id": message["id"]
                    })
                    return True
                else:
                    error = response_data.get("error", {})
                    _get_logger().error("Event sending failed", extra={
                        "event_type": event_type,
                        "error_code": error.get("code"),
                        "error_message": error.get("message")
                    })
                    return False
            else:
                _get_logger().warning("Unexpected response type", extra={
                    "expected": "response",
                    "received": response.get("type")
                })
                return False
                
        except Exception as e:
            _get_logger().error("Failed to send event", extra={
                "event_type": event_type,
                "error": str(e)
            })
            self._connected = False
            raise EventSenderError(f"Failed to send event: {e}") from e
    
    def send_heartbeat(self, 
                      agent_id: str = "sboxmgr",
                      status: str = "healthy",
                      version: Optional[str] = None) -> bool:
        """Send a heartbeat to sboxagent.
        
        Args:
            agent_id: Agent identifier
            status: Agent status (healthy, degraded, error)
            version: Optional version string
            
        Returns:
            True if heartbeat sent successfully, False otherwise
        """
        if not self.is_connected():
            if not self.connect():
                return False
        
        # Create heartbeat message
        message = self._create_heartbeat_message(
            agent_id=agent_id,
            status=status,
            version=version
        )
        
        try:
            # Send heartbeat
            self._client.send_message(message)
            
            # Wait for heartbeat response
            response = self._client.recv_message()
            
            if response.get("type") == "heartbeat":
                _get_logger().debug("Heartbeat exchange successful", extra={
                    "agent_id": agent_id
                })
                return True
            else:
                _get_logger().warning("Unexpected heartbeat response", extra={
                    "expected": "heartbeat",
                    "received": response.get("type")
                })
                return False
                
        except Exception as e:
            _get_logger().error("Failed to send heartbeat", extra={
                "agent_id": agent_id,
                "error": str(e)
            })
            self._connected = False
            return False
    
    def send_command(self,
                    command: str,
                    params: Dict[str, Any],
                    correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Send a command to sboxagent and wait for response.
        
        Args:
            command: Command to execute
            params: Command parameters
            correlation_id: Optional correlation ID
            
        Returns:
            Response data if successful, None otherwise
        """
        if not self.is_connected():
            if not self.connect():
                return None
        
        # Create command message
        message = self._create_command_message(
            command=command,
            params=params,
            correlation_id=correlation_id
        )
        
        try:
            # Send command
            self._client.send_message(message)
            
            # Wait for response
            response = self._client.recv_message()
            
            if response.get("type") == "response":
                response_data = response.get("response", {})
                if response_data.get("status") == "success":
                    return response_data.get("data")
                else:
                    error = response_data.get("error", {})
                    _get_logger().error("Command failed", extra={
                        "command": command,
                        "error_code": error.get("code"),
                        "error_message": error.get("message")
                    })
                    return None
            else:
                _get_logger().warning("Unexpected command response", extra={
                    "expected": "response",
                    "received": response.get("type")
                })
                return None
                
        except Exception as e:
            _get_logger().error("Failed to send command", extra={
                "command": command,
                "error": str(e)
            })
            self._connected = False
            return None
    
    def ping(self) -> bool:
        """Ping sboxagent to check connectivity.
        
        Returns:
            True if ping successful, False otherwise
        """
        response = self.send_command("ping", {})
        return response is not None and response.get("pong") is True
    
    def get_agent_status(self) -> Optional[Dict[str, Any]]:
        """Get sboxagent status.
        
        Returns:
            Agent status data if successful, None otherwise
        """
        return self.send_command("status", {})
    
    def _create_event_message(self,
                             event_type: str,
                             event_data: Dict[str, Any],
                             source: str,
                             priority: str,
                             correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Create an event message."""
        message = {
            "id": str(uuid.uuid4()),
            "type": "event",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "event": {
                "event_type": event_type,
                "source": source,
                "priority": priority,
                "data": event_data
            }
        }
        
        if correlation_id:
            message["correlation_id"] = correlation_id
        
        return message
    
    def _create_command_message(self,
                               command: str,
                               params: Dict[str, Any],
                               correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a command message."""
        message = {
            "id": str(uuid.uuid4()),
            "type": "command",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "command": {
                "command": command,
                "params": params
            }
        }
        
        if correlation_id:
            message["correlation_id"] = correlation_id
        
        return message
    
    def _create_heartbeat_message(self,
                                 agent_id: str,
                                 status: str,
                                 version: Optional[str] = None) -> Dict[str, Any]:
        """Create a heartbeat message."""
        message: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "heartbeat": {
                "agent_id": agent_id,
                "status": status
            }
        }
        
        if version:
            message["heartbeat"]["version"] = version
        
        return message


# Global event sender instance
_event_sender: Optional[EventSender] = None


def get_event_sender() -> EventSender:
    """Get global event sender instance.
    
    Returns:
        EventSender instance
    """
    global _event_sender
    if _event_sender is None:
        _event_sender = EventSender()
    return _event_sender


def send_event(event_type: str,
               event_data: Dict[str, Any],
               source: str = "sboxmgr",
               priority: str = "normal") -> bool:
    """Convenience function to send an event.
    
    Args:
        event_type: Type of event
        event_data: Event data
        source: Event source
        priority: Event priority
        
    Returns:
        True if sent successfully, False otherwise
    """
    sender = get_event_sender()
    try:
        return sender.send_event(event_type, event_data, source, priority)
    except Exception as e:
        _get_logger().debug(f"Failed to send event: {e}")
        return False


def send_heartbeat() -> bool:
    """Convenience function to send a heartbeat.
    
    Returns:
        True if sent successfully, False otherwise
    """
    sender = get_event_sender()
    return sender.send_heartbeat()


def ping_agent() -> bool:
    """Convenience function to ping the agent.
    
    Returns:
        True if ping successful, False otherwise
    """
    sender = get_event_sender()
    return sender.ping() 