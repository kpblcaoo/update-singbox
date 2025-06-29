"""
Tests for socket client bug fixes.

Tests:
1. Brittle pathing fix - proper import handling
2. Incomplete data detection - connection closed scenarios
"""

import pytest
import socket
import os
from unittest.mock import Mock
from sboxmgr.agent.ipc.socket_client import SocketClient


class TestSocketClientBugFixes:
    """Test socket client bug fixes."""

    def test_import_error_handling(self):
        """Test that import error is handled gracefully."""
        # Test that import works without sys.path manipulation
        import sys
        original_path = sys.path.copy()
        
        try:
            from sboxmgr.agent.ipc.socket_client import SocketClient
            client = SocketClient('/tmp/test.sock')
            assert client is not None
        except ImportError as e:
            # This is expected if sbox-common is not installed
            assert "sbox_common package not found" in str(e)
        finally:
            # Ensure sys.path wasn't modified
            assert sys.path == original_path

    def test_connection_closed_during_header_read(self):
        """Test handling when connection closes during header read."""
        client = SocketClient('/tmp/test.sock')
        client.sock = Mock()
        
        # Simulate connection closed during header read
        client.sock.recv.return_value = b''
        
        with pytest.raises(ConnectionError) as exc_info:
            client.recv_message()
        assert "incomplete header received" in str(exc_info.value)
        assert "0/8 bytes" in str(exc_info.value)

    def test_connection_closed_during_body_read(self):
        """Test handling when connection closes during body read."""
        client = SocketClient('/tmp/test.sock')
        client.sock = Mock()
        
        # Simulate complete header but connection closed during body read
        header = b'\x00\x00\x00\x0A\x00\x00\x00\x01'  # length=10, version=1
        partial_body = b'{"test":'
        
        client.sock.recv.side_effect = [header, partial_body, b'']
        
        with pytest.raises(ConnectionError) as exc_info:
            client.recv_message()
        assert "incomplete message body received" in str(exc_info.value)
        assert "8/10 bytes" in str(exc_info.value)

    def test_recv_exact_returns_partial_data(self):
        """Test that _recv_exact properly handles partial data."""
        client = SocketClient('/tmp/test.sock')
        client.sock = Mock()
        
        # Simulate receiving partial data
        client.sock.recv.side_effect = [b'partial', b' data']
        
        result = client._recv_exact(12)
        assert result == b'partial data'
        assert len(result) == 12

    def test_recv_exact_connection_closed(self):
        """Test that _recv_exact handles connection closed."""
        client = SocketClient('/tmp/test.sock')
        client.sock = Mock()
        
        # Simulate connection closed
        client.sock.recv.return_value = b''
        
        result = client._recv_exact(10)
        assert result == b''
        assert len(result) == 0

    def test_proper_error_messages(self):
        """Test that error messages are descriptive and helpful."""
        client = SocketClient('/tmp/test.sock')
        client.sock = Mock()
        
        # Test body error
        header = b'\x00\x00\x00\x05\x00\x00\x00\x01'  # length=5, version=1
        body = b'{"a":'
        client.sock.recv.side_effect = [header, body]
        with pytest.raises(ValueError) as exc_info:
            client.recv_message()
        error_msg = str(exc_info.value)
        assert "Invalid JSON" in error_msg
        assert "Expecting value" in error_msg


class TestSocketClientIntegration:
    """Integration tests for socket client fixes."""

    def test_import_without_sys_path_manipulation(self):
        """Test that import works without sys.path manipulation."""
        # This test ensures we're not using brittle pathing
        import sys
        original_path = sys.path.copy()
        
        try:
            # Import should work without modifying sys.path
            from sboxmgr.agent.ipc.socket_client import SocketClient
            client = SocketClient('/tmp/test.sock')
            assert client is not None
        except ImportError as e:
            # This is expected if sbox-common is not installed
            assert "sbox_common package not found" in str(e)
        finally:
            # Ensure sys.path wasn't modified
            assert sys.path == original_path

    def test_error_handling_integration(self):
        """Integration test for error handling."""
        # Use a unique socket path to avoid conflicts
        socket_path = f"/tmp/test_socket_{os.getpid()}.sock"
        
        try:
            # Create a socket that will close immediately
            server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server_sock.bind(socket_path)
            server_sock.listen(1)
            server_sock.close()
            
            client = SocketClient(socket_path)
            # This should fail with ConnectionRefusedError, not ConnectionError
            with pytest.raises(ConnectionRefusedError):
                client.connect()
                
        finally:
            if os.path.exists(socket_path):
                os.unlink(socket_path) 