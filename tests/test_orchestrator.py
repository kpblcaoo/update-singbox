"""Tests for Orchestrator facade functionality.

This module tests the Orchestrator class and its dependency injection,
unified interface, and error handling capabilities.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict

from sboxmgr.core import (
    Orchestrator, 
    OrchestratorConfig, 
    OrchestratorError,
    SubscriptionManagerInterface,
    ExportManagerInterface,
    ExclusionManagerInterface
)
from sboxmgr.subscription.models import PipelineResult, PipelineContext


class MockSubscriptionManager(SubscriptionManagerInterface):
    """Mock subscription manager for testing."""
    
    def __init__(self, mock_result: PipelineResult = None):
        self.get_servers_calls = []
        self.export_config_calls = []
        self.mock_result = mock_result or PipelineResult(
            config=[{"type": "vmess", "tag": "test-server"}],
            context=PipelineContext(),
            errors=[],
            success=True
        )
    
    def get_servers(self, user_routes=None, exclusions=None, mode=None, 
                   context=None, force_reload=False):
        """Mock get_servers method."""
        self.get_servers_calls.append({
            'user_routes': user_routes,
            'exclusions': exclusions,
            'mode': mode,
            'context': context,
            'force_reload': force_reload
        })
        return self.mock_result
    
    def export_config(self, exclusions=None, user_routes=None, context=None,
                     routing_plugin=None, export_manager=None, skip_version_check=False):
        """Mock export_config method."""
        self.export_config_calls.append({
            'exclusions': exclusions,
            'user_routes': user_routes,
            'context': context,
            'routing_plugin': routing_plugin,
            'export_manager': export_manager,
            'skip_version_check': skip_version_check
        })
        return {"outbounds": [{"tag": "exported"}]}


class MockExportManager(ExportManagerInterface):
    """Mock export manager for testing."""
    
    def __init__(self, mock_config: Dict = None):
        self.mock_config = mock_config or {"outbounds": []}
    
    def export(self, servers, exclusions=None, user_routes=None, context=None,
              client_profile=None, skip_version_check=False):
        """Mock export method."""
        return self.mock_config


class MockExclusionManager(ExclusionManagerInterface):
    """Mock exclusion manager for testing."""
    
    def __init__(self):
        self.exclusions = set()
    
    def add(self, server_id: str, name=None, reason=None):
        """Mock add method."""
        self.exclusions.add(server_id)
        return True
    
    def remove(self, server_id: str):
        """Mock remove method."""
        was_present = server_id in self.exclusions
        self.exclusions.discard(server_id)
        return was_present  # Возвращаем boolean как ожидает orchestrator

    def contains(self, server_id: str):
        """Mock contains method."""
        return server_id in self.exclusions

    def list_all(self):
        """Mock list_all method."""
        return list(self.exclusions)

    def clear(self):
        """Mock clear method."""
        count = len(self.exclusions)
        self.exclusions.clear()
        return count  # Возвращаем int как ожидает orchestrator

    def filter_servers(self, servers):
        """Mock filter_servers method."""
        return [s for s in servers if s.get("tag") not in self.exclusions]


class TestOrchestratorConfig:
    """Test OrchestratorConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = OrchestratorConfig()
        
        assert config.default_mode == "tolerant"
        assert config.debug_level == 0
        assert config.cache_enabled is True
        assert config.timeout_seconds == 30
        assert config.fail_safe is True
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = OrchestratorConfig(
            default_mode="strict",
            debug_level=2,
            cache_enabled=False,
            timeout_seconds=60,
            fail_safe=False
        )
        
        assert config.default_mode == "strict"
        assert config.debug_level == 2
        assert config.cache_enabled is False
        assert config.timeout_seconds == 60
        assert config.fail_safe is False


class TestOrchestratorError:
    """Test OrchestratorError exception class."""
    
    def test_basic_error(self):
        """Test basic error creation."""
        error = OrchestratorError("Test error")
        
        assert str(error) == "Test error"
        assert error.operation is None
        assert error.cause is None
    
    def test_error_with_context(self):
        """Test error with operation and cause."""
        cause = ValueError("Original error")
        error = OrchestratorError("Orchestrator error", operation="test_op", cause=cause)
        
        assert str(error) == "Orchestrator error"
        assert error.operation == "test_op"
        assert error.cause is cause


class TestOrchestrator:
    """Test Orchestrator main functionality."""
    
    def test_init_basic(self):
        """Test basic Orchestrator initialization."""
        config = OrchestratorConfig(debug_level=1)
        orchestrator = Orchestrator(config=config)
        
        assert orchestrator.config.debug_level == 1
        assert orchestrator._subscription_manager is None
        assert orchestrator._export_manager is None
        assert orchestrator._exclusion_manager is None
    
    def test_create_default_factory(self):
        """Test factory method for default creation."""
        orchestrator = Orchestrator.create_default(debug_level=2, fail_safe=False)
        
        assert orchestrator.config.debug_level == 2
        assert orchestrator.config.fail_safe is False
        assert orchestrator._subscription_manager is None  # Lazy loaded
    
    def test_lazy_loading_exclusion_manager(self):
        """Test lazy loading of exclusion manager."""
        orchestrator = Orchestrator()
        
        # Should be None initially
        assert orchestrator._exclusion_manager is None
        
        # Access should trigger lazy loading
        with patch('sboxmgr.core.factory.create_default_exclusion_manager') as mock_factory:
            mock_manager = Mock()
            mock_factory.return_value = mock_manager
            
            result = orchestrator.exclusion_manager
            
            assert result is mock_manager
            mock_factory.assert_called_once()
    
    def test_manage_exclusions_basic(self):
        """Test basic exclusion management."""
        mock_exclusion_mgr = Mock()
        mock_exclusion_mgr.add.return_value = True
        
        orchestrator = Orchestrator(exclusion_manager=mock_exclusion_mgr)
        
        result = orchestrator.manage_exclusions(
            action="add",
            server_id="test-server"
        )
        
        assert result["success"] is True
        assert result["action"] == "add"
        assert "test-server" in result["message"]
        mock_exclusion_mgr.add.assert_called_once_with("test-server", None, None)
    
    def test_manage_exclusions_list(self):
        """Test exclusion list operation."""
        mock_exclusion_mgr = Mock()
        mock_exclusion_mgr.list_all.return_value = [
            {"server_id": "server1", "name": "Test Server"}
        ]
        
        orchestrator = Orchestrator(exclusion_manager=mock_exclusion_mgr)
        
        result = orchestrator.manage_exclusions(action="list")
        
        assert result["success"] is True
        assert result["data"]["count"] == 1
        assert len(result["data"]["exclusions"]) == 1
    
    def test_manage_exclusions_invalid_action(self):
        """Test invalid exclusion action."""
        orchestrator = Orchestrator()
        
        config = OrchestratorConfig(fail_safe=False)
        orchestrator.config = config
        
        with pytest.raises(OrchestratorError):
            orchestrator.manage_exclusions(action="invalid")
    
    def test_manage_exclusions_fail_safe(self):
        """Test exclusion management in fail-safe mode."""
        mock_exclusion_mgr = Mock()
        mock_exclusion_mgr.add.side_effect = Exception("Mock error")
        
        config = OrchestratorConfig(fail_safe=True)
        orchestrator = Orchestrator(exclusion_manager=mock_exclusion_mgr, config=config)
        
        result = orchestrator.manage_exclusions(action="add", server_id="test")
        
        assert result["success"] is False
        assert "Mock error" in result["message"]
    
    def test_get_subscription_servers_success(self):
        """Test successful subscription server retrieval."""
        mock_sub_mgr = MockSubscriptionManager()
        exclusion_mgr = MockExclusionManager()
        
        orchestrator = Orchestrator(exclusion_manager=exclusion_mgr)
        
        # Patch SubscriptionManager constructor to return our mock
        with patch("sboxmgr.subscription.manager.SubscriptionManager", return_value=mock_sub_mgr):
            result = orchestrator.get_subscription_servers(
                url="https://example.com/sub",
                user_routes=["route1"],
                exclusions=["excluded1"],
                mode="strict",
                force_reload=True
            )
        
        assert result.success is True
        assert len(result.config) == 1
        assert result.config[0]["tag"] == "test-server"
        
        # Check that subscription manager was called correctly
        assert len(mock_sub_mgr.get_servers_calls) == 1
        call = mock_sub_mgr.get_servers_calls[0]
        assert call['user_routes'] == ["route1"]
        assert call['exclusions'] == ["excluded1"]
        assert call['mode'] == "strict"
        assert call['force_reload'] is True
    
    def test_get_subscription_servers_with_exclusion_filtering(self):
        """Test subscription servers with exclusion filtering."""
        # Create mock result with servers
        mock_result = PipelineResult(
            config=[
                {"type": "vmess", "tag": "server1", "server": "example1.com"},
                {"type": "vmess", "tag": "server2", "server": "example2.com"}
            ],
            context=PipelineContext(),
            errors=[],
            success=True
        )
        
        mock_sub_mgr = MockSubscriptionManager(mock_result)
        exclusion_mgr = MockExclusionManager()
        exclusion_mgr.add("server1")  # Exclude server1
        
        orchestrator = Orchestrator(exclusion_manager=exclusion_mgr)
        
        # Patch SubscriptionManager constructor to return our mock
        with patch("sboxmgr.subscription.manager.SubscriptionManager", return_value=mock_sub_mgr):
            result = orchestrator.get_subscription_servers(url="https://example.com/sub")
        
        # Should have filtered out server1
        assert result.success is True
        assert len(result.config) == 1
        assert result.config[0]["tag"] == "server2"
    
    def test_get_subscription_servers_fail_safe_mode(self):
        """Test fail-safe mode for subscription errors."""
        mock_sub_mgr = MockSubscriptionManager(PipelineResult(
            config=None,
            context=PipelineContext(),
            errors=["Mock error"],
            success=False
        ))
        
        config = OrchestratorConfig(fail_safe=True)
        orchestrator = Orchestrator(config=config)
        
        # Patch SubscriptionManager constructor to return our mock
        with patch("sboxmgr.subscription.manager.SubscriptionManager", return_value=mock_sub_mgr):
            result = orchestrator.get_subscription_servers(url="https://example.com/sub")
        
        assert result.success is False
        assert result.config is None
        assert "Mock error" in result.errors
    
    def test_get_subscription_servers_strict_mode(self):
        """Test strict mode raises exceptions."""
        mock_sub_mgr = Mock()
        mock_sub_mgr.get_servers.side_effect = Exception("Mock error")
        
        config = OrchestratorConfig(fail_safe=False)
        orchestrator = Orchestrator(config=config)
        
        # Patch SubscriptionManager constructor to return our mock
        with patch("sboxmgr.subscription.manager.SubscriptionManager", return_value=mock_sub_mgr):
            with pytest.raises(OrchestratorError) as exc_info:
                orchestrator.get_subscription_servers(url="https://example.com/sub")
        
        assert "Mock error" in str(exc_info.value)
        assert exc_info.value.operation == "get_subscription_servers"
    
    def test_manage_exclusions_add(self):
        """Test exclusion management - add operation."""
        exclusion_mgr = MockExclusionManager()
        orchestrator = Orchestrator(exclusion_manager=exclusion_mgr)
        
        result = orchestrator.manage_exclusions(
            action="add",
            server_id="test-server",
            name="Test Server",
            reason="Testing"
        )
        
        assert result["success"] is True
        assert result["action"] == "add"
        assert "added to" in result["message"]
        assert exclusion_mgr.contains("test-server")
    
    def test_manage_exclusions_remove(self):
        """Test exclusion management - remove operation."""
        exclusion_mgr = MockExclusionManager()
        exclusion_mgr.add("test-server")
        orchestrator = Orchestrator(exclusion_manager=exclusion_mgr)
        
        result = orchestrator.manage_exclusions(action="remove", server_id="test-server")
        
        assert result["success"] is True
        assert result["action"] == "remove"
        assert "removed from" in result["message"]
        assert not exclusion_mgr.contains("test-server")
    
    def test_manage_exclusions_clear(self):
        """Test exclusion management - clear operation."""
        exclusion_mgr = MockExclusionManager()
        exclusion_mgr.add("server1")
        exclusion_mgr.add("server2")
        orchestrator = Orchestrator(exclusion_manager=exclusion_mgr)
        
        result = orchestrator.manage_exclusions(action="clear")
        
        assert result["success"] is True
        assert result["action"] == "clear"
        assert result["data"]["cleared_count"] == 2
        assert len(exclusion_mgr.exclusions) == 0
    
    def test_export_configuration_success(self):
        """Test successful configuration export."""
        # Mock subscription result
        mock_servers_result = PipelineResult(
            config=[{"type": "vmess", "tag": "test-server"}],
            context=PipelineContext(),
            errors=[],
            success=True
        )
        
        mock_sub_mgr = MockSubscriptionManager(mock_servers_result)
        export_mgr = MockExportManager({"outbounds": [{"tag": "exported"}]})
        
        orchestrator = Orchestrator(export_manager=export_mgr)
        
        # Patch SubscriptionManager constructor to return our mock
        with patch("sboxmgr.subscription.manager.SubscriptionManager", return_value=mock_sub_mgr):
            result = orchestrator.export_configuration(
                source_url="https://example.com/sub",
                export_format="singbox",
                exclusions=["excluded1"],
                skip_version_check=True
            )
        
        assert result["success"] is True
        assert result["format"] == "singbox"
        assert result["server_count"] == 1
        assert result["config"]["outbounds"][0]["tag"] == "exported"
        assert result["metadata"]["exclusions_applied"] == 1
    
    def test_export_configuration_servers_failure(self):
        """Test export when server retrieval fails."""
        mock_failed_result = PipelineResult(
            config=None,
            context=PipelineContext(),
            errors=["Server fetch failed"],
            success=False
        )
        
        sub_mgr = MockSubscriptionManager(mock_failed_result)
        config = OrchestratorConfig(fail_safe=False)  # Настраиваем strict режим
        orchestrator = Orchestrator(subscription_manager=sub_mgr, config=config)
        
        with patch.object(orchestrator, 'get_subscription_servers', return_value=mock_failed_result):
            with pytest.raises(OrchestratorError) as exc_info:
                orchestrator.export_configuration(source_url="https://example.com/sub")
            
            assert "Failed to retrieve servers" in str(exc_info.value)
    
    def test_with_custom_managers(self):
        """Test builder pattern for custom managers."""
        original_orchestrator = Orchestrator.create_default()
        custom_exclusion_mgr = MockExclusionManager()
        
        new_orchestrator = original_orchestrator.with_custom_managers(
            exclusion_manager=custom_exclusion_mgr
        )
        
        assert new_orchestrator is not original_orchestrator
        assert new_orchestrator._exclusion_manager is custom_exclusion_mgr
        assert new_orchestrator.config is original_orchestrator.config 