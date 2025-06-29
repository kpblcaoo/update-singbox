"""Tests for SocketClient."""

import pytest
import tempfile
import socket
from pathlib import Path
from unittest.mock import Mock, patch

# Add sboxmgr to path
import sys
sys.path.append(str(Path(__file__).parent.parent / "src"))

from sboxmgr.agent.ipc.socket_client import SocketClient


class TestSocketClient:
    """Test cases for SocketClient."""

    def test_init(self):
        """Test SocketClient initialization."""
        client = SocketClient("/tmp/test.sock", timeout=10.0)
        assert client.socket_path == "/tmp/test.sock"
        assert client.timeout == 10.0
        assert client.sock is None
        assert client.protocol is not None

    def test_connect_success(self):
        """Test successful connection."""
        with tempfile.NamedTemporaryFile(suffix='.sock') as tmp:
            socket_path = tmp.name
        
        # Mock socket to simulate successful connection
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value = mock_sock
            
            client = SocketClient(socket_path)
            client.connect()
            
            mock_socket.assert_called_once_with(socket.AF_UNIX, socket.SOCK_STREAM)
            mock_sock.settimeout.assert_called_once_with(client.timeout)
            mock_sock.connect.assert_called_once_with(socket_path)
            assert client.sock == mock_sock

    def test_connect_failure(self):
        """Test connection failure."""
        client = SocketClient("/nonexistent/path.sock")
        
        with pytest.raises(FileNotFoundError):
            client.connect()

    def test_send_message_not_connected(self):
        """Test sending message without connection."""
        client = SocketClient("/tmp/test.sock")
        
        with pytest.raises(RuntimeError, match="Socket is not connected"):
            client.send_message({"test": "message"})

    def test_recv_message_not_connected(self):
        """Test receiving message without connection."""
        client = SocketClient("/tmp/test.sock")
        
        with pytest.raises(RuntimeError, match="Socket is not connected"):
            client.recv_message()

    def test_close(self):
        """Test closing connection."""
        client = SocketClient("/tmp/test.sock")
        client.sock = Mock()
        
        client.close()
        
        client.sock.close.assert_called_once()
        assert client.sock is None

    def test_close_no_socket(self):
        """Test closing when no socket exists."""
        client = SocketClient("/tmp/test.sock")
        
        # Should not raise any exception
        client.close()

    def test_protocol_creation(self):
        """Test that protocol is properly initialized."""
        client = SocketClient("/tmp/test.sock")
        
        assert hasattr(client.protocol, 'encode_message')
        assert hasattr(client.protocol, 'decode_message')
        assert hasattr(client.protocol, 'create_event_message')
        assert hasattr(client.protocol, 'create_command_message')

    def test_message_creation_methods(self):
        """Test that protocol can create different message types."""
        client = SocketClient("/tmp/test.sock")
        
        # Test event message
        event_msg = client.protocol.create_event_message(
            {"type": "test_event", "data": "test_data"}
        )
        assert event_msg["type"] == "event"
        assert "event" in event_msg
        
        # Test command message
        cmd_msg = client.protocol.create_command_message(
            "test_command", {"param": "value"}
        )
        assert cmd_msg["type"] == "command"
        assert "command" in cmd_msg
        
        # Test response message
        resp_msg = client.protocol.create_response_message(
            "req-123", "success", {"result": "ok"}
        )
        assert resp_msg["type"] == "response"
        assert "response" in resp_msg
        
        # Test heartbeat message
        hb_msg = client.protocol.create_heartbeat_message(
            "agent-123", "healthy", 3600.0, "1.0.0"
        )
        assert hb_msg["type"] == "heartbeat"
        assert "heartbeat" in hb_msg 