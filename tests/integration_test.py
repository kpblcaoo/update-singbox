#!/usr/bin/env python3
"""Integration test for sboxmgr <-> sboxagent communication.

This test verifies that the Phase 2 integration works correctly:
- Unix socket communication
- Event sending
- Agent bridge functionality
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sboxmgr.agent.event_sender import EventSender, ping_agent, send_event
from sboxmgr.agent.ipc.socket_client import SocketClient
from sboxmgr.logging import get_logger

logger = get_logger(__name__)


def test_socket_connection():
    """Test basic socket connection to sboxagent."""
    print("🔌 Testing socket connection...")
    
    result = ping_agent()
    if result:
        print("✅ Socket connection successful")
        return True
    else:
        print("❌ Socket connection failed")
        return False


def test_event_sending():
    """Test sending events to sboxagent."""
    print("📡 Testing event sending...")
    
    test_events = [
        ("test_event", {"test": True, "timestamp": time.time()}),
        ("subscription_updated", {
            "subscription_url": "https://example.com/sub",
            "servers_count": 42,
            "status": "success"
        }),
        ("config_generated", {
            "client_type": "sing-box",
            "config_size": 1024,
            "generation_time_ms": 250
        })
    ]
    
    success_count = 0
    for event_type, event_data in test_events:
        try:
            result = send_event(event_type, event_data, source="integration_test")
            if result:
                print(f"✅ Event '{event_type}' sent successfully")
                success_count += 1
            else:
                print(f"❌ Event '{event_type}' failed to send")
        except Exception as e:
            print(f"❌ Event '{event_type}' failed with error: {e}")
    
    print(f"📊 Event sending: {success_count}/{len(test_events)} successful")
    return success_count == len(test_events)


def test_heartbeat():
    """Test heartbeat functionality."""
    print("💓 Testing heartbeat...")
    
    sender = EventSender()
    try:
        result = sender.send_heartbeat(
            agent_id="integration_test",
            status="healthy",
            version="test-1.0.0"
        )
        if result:
            print("✅ Heartbeat successful")
            return True
        else:
            print("❌ Heartbeat failed")
            return False
    except Exception as e:
        print(f"❌ Heartbeat failed with error: {e}")
        return False
    finally:
        sender.disconnect()


def test_command_execution():
    """Test command execution via socket."""
    print("⚡ Testing command execution...")
    
    sender = EventSender()
    try:
        # Test ping command
        response = sender.send_command("ping", {})
        if response and response.get("pong"):
            print("✅ Ping command successful")
            
            # Test status command
            status = sender.get_agent_status()
            if status:
                print("✅ Status command successful")
                print(f"   Agent status: {status}")
                return True
            else:
                print("❌ Status command failed")
                return False
        else:
            print("❌ Ping command failed")
            return False
    except Exception as e:
        print(f"❌ Command execution failed with error: {e}")
        return False
    finally:
        sender.disconnect()


def test_framed_json_protocol():
    """Test framed JSON protocol directly."""
    print("📋 Testing framed JSON protocol...")
    
    try:
        client = SocketClient("/tmp/sboxagent.sock", timeout=5.0)
        client.connect()
        
        # Create test message
        message = {
            "id": "test-123",
            "type": "command",
            "timestamp": "2025-01-28T10:00:00Z",
            "command": {
                "command": "ping",
                "params": {}
            }
        }
        
        # Send message
        client.send_message(message)
        print("✅ Message sent successfully")
        
        # Receive response
        response = client.recv_message()
        print(f"✅ Response received: {response.get('type')}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Framed JSON protocol test failed: {e}")
        return False


def main():
    """Run all integration tests."""
    print("🚀 Starting Phase 2 Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Socket Connection", test_socket_connection),
        ("Event Sending", test_event_sending),
        ("Heartbeat", test_heartbeat),
        ("Command Execution", test_command_execution),
        ("Framed JSON Protocol", test_framed_json_protocol),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running test: {test_name}")
        print("-" * 30)
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Phase 2 integration is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check sboxagent status and configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 