from unittest.mock import patch, MagicMock, mock_open
import typer
from sboxmgr.cli.main import is_ai_lang, SUPPORTED_PROTOCOLS


class TestIsAiLang:
    """Test is_ai_lang function."""
    
    def test_is_ai_lang_true(self, tmp_path):
        """Test is_ai_lang returns True for AI-generated language."""
        # Create mock i18n directory structure
        i18n_dir = tmp_path / "i18n"
        i18n_dir.mkdir()
        
        # Create language file with AI marker
        {
            "cli": {"help": "Hilfe"},
            "__note__": "AI-generated translations - needs review"
        }
        
        with patch('sboxmgr.cli.main.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            with patch('builtins.open', mock_open(read_data='{"cli": {"help": "Hilfe"}, "__note__": "AI-generated translations - needs review"}')):
                result = is_ai_lang("de")
                assert result is True
    
    def test_is_ai_lang_false(self, tmp_path):
        """Test is_ai_lang returns False for human-reviewed language."""
        with patch('sboxmgr.cli.main.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            with patch('builtins.open', mock_open(read_data='{"cli": {"help": "Help"}, "__note__": "Human-reviewed"}')):
                result = is_ai_lang("en")
                assert result is False
    
    def test_is_ai_lang_no_note(self, tmp_path):
        """Test is_ai_lang returns False when no __note__ field."""
        with patch('sboxmgr.cli.main.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            with patch('builtins.open', mock_open(read_data='{"cli": {"help": "Help"}}')):
                result = is_ai_lang("en")
                assert result is False
    
    def test_is_ai_lang_file_not_exists(self, tmp_path):
        """Test is_ai_lang returns False when language file doesn't exist."""
        with patch('sboxmgr.cli.main.Path') as mock_path:
            # Mock the path construction
            mock_lang_file = MagicMock()
            mock_lang_file.exists.return_value = False
            mock_path.return_value.parent.parent.__truediv__.return_value.__truediv__.return_value = mock_lang_file
            result = is_ai_lang("nonexistent")
            assert result is False
    
    def test_is_ai_lang_json_error(self, tmp_path):
        """Test is_ai_lang handles JSON parsing errors."""
        with patch('sboxmgr.cli.main.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            with patch('builtins.open', mock_open(read_data='invalid json')):
                result = is_ai_lang("de")
                assert result is False


class TestSupportedProtocols:
    """Test SUPPORTED_PROTOCOLS constant."""
    
    def test_supported_protocols_constant(self):
        """Test that SUPPORTED_PROTOCOLS constant is properly defined."""
        expected_protocols = {"vless", "shadowsocks", "vmess", "trojan", "tuic", "hysteria2"}
        assert SUPPORTED_PROTOCOLS == expected_protocols
        assert len(SUPPORTED_PROTOCOLS) == 6
        assert isinstance(SUPPORTED_PROTOCOLS, set)


class TestMainModuleIntegration:
    """Integration tests for main module."""
    
    def test_app_typer_instance(self):
        """Test that app is properly configured Typer instance."""
        from sboxmgr.cli.main import app
        
        assert isinstance(app, typer.Typer)
    
    def test_is_ai_lang_file_read_error(self, tmp_path):
        """Test is_ai_lang handles file read errors."""
        with patch('sboxmgr.cli.main.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            with patch('builtins.open', side_effect=IOError("Permission denied")):
                result = is_ai_lang("de")
                assert result is False

    def test_import_main_no_output(self, capsys):
        """Smoke test: importing cli.main should not print anything to stdout/stderr."""
        import importlib
        import sys
        # Remove from sys.modules to force re-import
        sys.modules.pop("sboxmgr.cli.main", None)
        importlib.import_module("sboxmgr.cli.main")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "" 