import pytest
import json
from unittest.mock import patch, MagicMock
from sboxmgr.cli.commands.exclusions import (
    exclusions, _view_exclusions, _get_server_id, SUPPORTED_PROTOCOLS
)


class TestExclusionsBasic:
    """Test basic functionality of exclusions."""
    
    @pytest.fixture
    def mock_manager(self):
        """Mock ExclusionManager for testing."""
        manager = MagicMock()
        manager.list_all.return_value = []
        manager.clear.return_value = 0
        manager.set_servers_cache.return_value = None
        return manager
    
    def test_exclusions_view_mode(self, mock_manager):
        """Test exclusions in view mode."""
        with patch('sboxmgr.cli.commands.exclusions.ExclusionManager.default', return_value=mock_manager), \
             patch('sboxmgr.cli.commands.exclusions._view_exclusions') as mock_view:
            
            exclusions(
                url="http://test.com", view=True, add=None, remove=None,
                clear=False, list_servers=False, interactive=False,
                reason="test", json_output=False, show_excluded=True, debug=0
            )
            
            mock_view.assert_called_once_with(mock_manager, False)
    
    def test_exclusions_clear_mode_confirmed(self, mock_manager):
        """Test exclusions clear mode with confirmation."""
        mock_manager.clear.return_value = 5
        
        with patch('sboxmgr.cli.commands.exclusions.ExclusionManager.default', return_value=mock_manager), \
             patch('sboxmgr.cli.commands.exclusions.Confirm.ask', return_value=True), \
             patch('sboxmgr.cli.commands.exclusions.rprint') as mock_rprint:
            
            exclusions(
                url="http://test.com", view=False, add=None, remove=None,
                clear=True, list_servers=False, interactive=False,
                reason="test", json_output=False, show_excluded=True, debug=0
            )
            
            mock_manager.clear.assert_called_once()
            # Check that success message was called with green formatting and contains number
            mock_rprint.assert_called_once()
            call_args = mock_rprint.call_args[0][0]
            assert "[green]✅" in call_args
            assert "5" in call_args  # Should contain the count
    
    def test_exclusions_clear_mode_cancelled(self, mock_manager):
        """Test exclusions clear mode with cancellation."""
        with patch('sboxmgr.cli.commands.exclusions.ExclusionManager.default', return_value=mock_manager), \
             patch('sboxmgr.cli.commands.exclusions.Confirm.ask', return_value=False), \
             patch('sboxmgr.cli.commands.exclusions.rprint') as mock_rprint:
            
            exclusions(
                url="http://test.com", view=False, add=None, remove=None,
                clear=True, list_servers=False, interactive=False,
                reason="test", json_output=False, show_excluded=True, yes=False, debug=0
            )
            
            mock_manager.clear.assert_not_called()
            # Check that cancellation message was called with yellow formatting
            mock_rprint.assert_called_once()
            call_args = mock_rprint.call_args[0][0]
            assert "[yellow]" in call_args
    
    def test_exclusions_no_action_help(self, mock_manager):
        """Test exclusions shows help when no action specified."""
        sample_json_data = {"outbounds": [{"type": "vless", "tag": "test"}]}
        
        with patch('sboxmgr.cli.commands.exclusions.ExclusionManager.default', return_value=mock_manager), \
             patch('sboxmgr.cli.commands.exclusions.fetch_json', return_value=sample_json_data), \
             patch('sboxmgr.cli.commands.exclusions.rprint') as mock_rprint:
            
            exclusions(
                url="http://test.com", view=False, add=None, remove=None,
                clear=False, list_servers=False, interactive=False,
                reason="test", json_output=False, show_excluded=True, debug=0
            )
            
            # Should show help message with yellow formatting and contains command options
            mock_rprint.assert_called()
            calls = [call[0][0] for call in mock_rprint.call_args_list]
            help_call = next((call for call in calls if "[yellow]💡" in call), None)
            assert help_call is not None
            # Should mention the available options
            assert any(option in help_call for option in ["--add", "--remove", "--view", "--clear"])


class TestViewExclusions:
    """Test _view_exclusions function."""
    
    def test_view_exclusions_empty_json(self):
        """Test _view_exclusions with empty exclusions in JSON format."""
        manager = MagicMock()
        manager.list_all.return_value = []
        
        with patch('builtins.print') as mock_print:
            _view_exclusions(manager, json_output=True)
            
            expected_output = {"total": 0, "exclusions": []}
            mock_print.assert_called_once_with(json.dumps(expected_output, indent=2))
    
    def test_view_exclusions_empty_table(self):
        """Test _view_exclusions with empty exclusions in table format."""
        manager = MagicMock()
        manager.list_all.return_value = []
        
        with patch('sboxmgr.cli.commands.exclusions.rprint') as mock_rprint:
            _view_exclusions(manager, json_output=False)
            
            mock_rprint.assert_called_once_with("[dim]📝 No exclusions found.[/dim]")
    
    def test_view_exclusions_with_data_json(self):
        """Test _view_exclusions with data in JSON format."""
        manager = MagicMock()
        exclusions_data = [
            {"id": "test-id-123", "name": "test-server", "reason": "testing", "timestamp": "2024-01-01T00:00:00Z"}
        ]
        manager.list_all.return_value = exclusions_data
        
        with patch('builtins.print') as mock_print:
            _view_exclusions(manager, json_output=True)
            
            expected_output = {"total": 1, "exclusions": exclusions_data}
            mock_print.assert_called_once_with(json.dumps(expected_output, indent=2))
    
    def test_view_exclusions_with_data_table(self):
        """Test _view_exclusions with data in table format."""
        manager = MagicMock()
        exclusions_data = [
            {"id": "test-id-123456789", "name": "test-server", "reason": "testing", "timestamp": "2024-01-01T00:00:00Z"}
        ]
        manager.list_all.return_value = exclusions_data
        
        with patch('sboxmgr.cli.commands.exclusions.console.print') as mock_console_print:
            _view_exclusions(manager, json_output=False)
            
            mock_console_print.assert_called_once()


class TestGetServerId:
    """Test _get_server_id function."""
    
    def test_get_server_id_success(self):
        """Test _get_server_id with valid server data."""
        server = {"type": "vless", "tag": "test-server", "server": "test.com"}
        
        result = _get_server_id(server)
        
        # Should return some string ID (actual implementation generates hash)
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_get_server_id_with_empty_dict(self):
        """Test _get_server_id with empty dict."""
        server = {}
        
        result = _get_server_id(server)
        
        # Should return some fallback ID even with empty data
        assert isinstance(result, str)
        assert len(result) > 0


class TestExclusionsIntegration:
    """Integration tests for exclusions with realistic scenarios."""
    
    def test_exclusions_json_output_clear_mode(self):
        """Test JSON output for clear mode."""
        manager = MagicMock()
        manager.clear.return_value = 3
        
        # Test clear mode with JSON output
        with patch('sboxmgr.cli.commands.exclusions.ExclusionManager.default', return_value=manager), \
             patch('sboxmgr.cli.commands.exclusions.Confirm.ask', return_value=True), \
             patch('builtins.print') as mock_print:
            
            exclusions(
                url="http://test.com", view=False, add=None, remove=None,
                clear=True, list_servers=False, interactive=False,
                reason="test", json_output=True, show_excluded=True, debug=0
            )
            
            expected_output = {"action": "clear", "removed_count": 3}
            mock_print.assert_called_once_with(json.dumps(expected_output))
    
    def test_exclusions_successful_operation(self):
        """Test successful operation with server data."""
        manager = MagicMock()
        sample_data = {"outbounds": [{"type": "vless", "tag": "test-server"}]}
        
        with patch('sboxmgr.cli.commands.exclusions.ExclusionManager.default', return_value=manager), \
             patch('sboxmgr.cli.commands.exclusions.fetch_json', return_value=sample_data), \
             patch('sboxmgr.cli.commands.exclusions._list_servers') as mock_list:
            
            exclusions(
                url="http://test.com", view=False, add=None, remove=None,
                clear=False, list_servers=True, interactive=False,
                reason="test", json_output=False, show_excluded=True, debug=0
            )
            
            manager.set_servers_cache.assert_called_once()
            mock_list.assert_called_once()


class TestExclusionsConstants:
    """Test constants and basic imports."""
    
    def test_supported_protocols_constant(self):
        """Test that SUPPORTED_PROTOCOLS is defined."""
        
        assert isinstance(SUPPORTED_PROTOCOLS, list)
        assert len(SUPPORTED_PROTOCOLS) > 0
        assert "vless" in SUPPORTED_PROTOCOLS
        assert "vmess" in SUPPORTED_PROTOCOLS


class TestExclusionsViewMode:
    """Test view mode functionality."""
    
    def test_view_mode_with_json_output(self):
        """Test view mode with JSON output."""
        manager = MagicMock()
        manager.list_all.return_value = [
            {"id": "test1", "name": "server1", "reason": "test"}
        ]
        
        with patch('sboxmgr.cli.commands.exclusions.ExclusionManager.default', return_value=manager), \
             patch('builtins.print') as mock_print:
            
            exclusions(
                url="http://test.com", view=True, add=None, remove=None,
                clear=False, list_servers=False, interactive=False,
                reason="test", json_output=True, show_excluded=True, debug=0
            )
            
            # Should output JSON with exclusions data
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            parsed_output = json.loads(call_args)
            assert "total" in parsed_output
            assert "exclusions" in parsed_output
            assert parsed_output["total"] == 1


class TestExclusionsHelperFunctions:
    """Test helper functions used by exclusions."""
    
    def test_view_exclusions_handles_missing_fields(self):
        """Test _view_exclusions handles missing fields gracefully."""
        manager = MagicMock()
        exclusions_data = [
            {"id": "test-id-123"}  # Missing name, reason, timestamp
        ]
        manager.list_all.return_value = exclusions_data
        
        with patch('sboxmgr.cli.commands.exclusions.console.print') as mock_console_print:
            _view_exclusions(manager, json_output=False)
            
            # Should not crash and should call console.print
            mock_console_print.assert_called_once()
    
    def test_get_server_id_with_minimal_data(self):
        """Test _get_server_id with minimal server data."""
        server = {"tag": "minimal"}
        
        result = _get_server_id(server)
        
        assert isinstance(result, str)
        assert len(result) > 0 