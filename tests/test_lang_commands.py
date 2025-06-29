import pytest
from unittest.mock import patch, MagicMock
import typer
from sboxmgr.cli.commands.lang import lang_cmd, LANG_NAMES


class TestLangCmd:
    """Test lang_cmd function."""
    
    def test_lang_cmd_display_current_config_file_source(self, tmp_path):
        """Test lang_cmd displays current language from config file."""
        with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("de", "config file")), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.get.return_value = "Test help message"
            mock_loader.list_languages.return_value = ["en", "ru", "de"]
            mock_loader_class.return_value = mock_loader
            
            lang_cmd(set_lang=None)
            
            mock_echo.assert_any_call("Current language: de (source: config file)")
            mock_echo.assert_any_call("Test help message")
    
    def test_lang_cmd_display_system_lang_bilingual(self, tmp_path):
        """Test lang_cmd displays bilingual output for system LANG source."""
        with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("ru", "system LANG")), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('typer.echo') as mock_echo:
            
            # Mock English loader
            en_loader = MagicMock()
            en_loader.get.side_effect = lambda key: f"EN: {key}"
            
            # Mock Russian loader  
            ru_loader = MagicMock()
            ru_loader.get.side_effect = lambda key: f"RU: {key}"
            ru_loader.list_languages.return_value = ["en", "ru"]
            
            def loader_side_effect(lang_code):
                if lang_code == "en":
                    return en_loader
                return ru_loader
            
            mock_loader_class.side_effect = loader_side_effect
            
            lang_cmd(set_lang=None)
            
            mock_echo.assert_any_call("Current language: ru (source: system LANG)")
            mock_echo.assert_any_call("--- English ---")
            mock_echo.assert_any_call("EN: cli.lang.help")
            mock_echo.assert_any_call("--- Русский ---")
            mock_echo.assert_any_call("RU: cli.lang.help")
    
    def test_lang_cmd_display_default_source_bilingual(self, tmp_path):
        """Test lang_cmd displays bilingual output for default source."""
        with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("en", "default")), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('typer.echo') as mock_echo:
            
            en_loader = MagicMock()
            en_loader.get.side_effect = lambda key: f"EN: {key}"
            en_loader.list_languages.return_value = ["en", "ru"]
            mock_loader_class.return_value = en_loader
            
            lang_cmd(set_lang=None)
            
            mock_echo.assert_any_call("Current language: en (source: default)")
            mock_echo.assert_any_call("--- English ---")
            mock_echo.assert_any_call("EN: cli.lang.help")
    
    def test_lang_cmd_list_available_languages(self):
        """Test lang_cmd lists available languages with names."""
        with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("en", "config file")), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('sboxmgr.cli.commands.lang.is_ai_lang') as mock_is_ai, \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.get.return_value = "Help message"
            mock_loader.list_languages.return_value = ["en", "ru", "de", "unknown"]
            mock_loader_class.return_value = mock_loader
            
            # Mock AI language detection
            mock_is_ai.side_effect = lambda code: code == "de"
            
            lang_cmd(set_lang=None)
            
            mock_echo.assert_any_call("Available languages:")
            mock_echo.assert_any_call("  en - English")
            mock_echo.assert_any_call("  ru - Русский")
            mock_echo.assert_any_call("  de - Deutsch [AI]")
            mock_echo.assert_any_call("  unknown - unknown")
            mock_echo.assert_any_call("Note: [AI] = machine-translated, not reviewed. Contributions welcome!")
    
    def test_lang_cmd_set_language_success(self, tmp_path):
        """Test lang_cmd successfully sets language."""
        config_file = tmp_path / ".sboxmgr" / "config.toml"
        
        with patch('sboxmgr.cli.commands.lang.Path.home', return_value=tmp_path), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.exists.return_value = True
            mock_loader_class.return_value = mock_loader
            
            lang_cmd(set_lang="ru")
            
            mock_loader.exists.assert_called_once_with("ru")
            mock_echo.assert_called_with(f"Language set to 'ru' and persisted in {config_file}.")
            
            # Check config file was created
            assert config_file.exists()
            import toml
            config_data = toml.load(config_file)
            assert config_data["default_lang"] == "ru"
    
    def test_lang_cmd_set_language_not_found(self):
        """Test lang_cmd handles setting non-existent language."""
        with patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.exists.return_value = False
            mock_loader.list_languages.return_value = ["en", "ru", "de"]
            mock_loader_class.return_value = mock_loader
            
            with pytest.raises(typer.Exit):
                lang_cmd(set_lang="invalid")
            
            mock_echo.assert_any_call("Language 'invalid' not found in i18n folder.")
            mock_echo.assert_any_call("Available: en, ru, de")
    
    def test_lang_cmd_set_language_config_write_error(self, tmp_path):
        """Test lang_cmd handles config file write errors."""
        with patch('sboxmgr.cli.commands.lang.Path.home', return_value=tmp_path), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('builtins.open', side_effect=PermissionError("Access denied")), \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.exists.return_value = True
            mock_loader_class.return_value = mock_loader
            
            with pytest.raises(typer.Exit):
                lang_cmd(set_lang="ru")
            
            mock_echo.assert_any_call("[Error] Failed to write config: Access denied", err=True)


class TestLangCmdConstants:
    """Test constants and imports in lang module."""
    
    def test_lang_names_constant(self):
        """Test that LANG_NAMES constant is properly defined."""
        assert isinstance(LANG_NAMES, dict)
        assert "en" in LANG_NAMES
        assert LANG_NAMES["en"] == "English"
        assert "ru" in LANG_NAMES
        assert LANG_NAMES["ru"] == "Русский"
    
    def test_lang_names_completeness(self):
        """Test that LANG_NAMES contains expected languages."""
        expected_langs = ["en", "ru", "de", "zh", "fa", "tr", "uk", "es", "fr", "ar", "pl"]
        for lang in expected_langs:
            assert lang in LANG_NAMES, f"Language {lang} missing from LANG_NAMES"


class TestLangCmdIntegration:
    """Integration tests for lang_cmd."""
    
    def test_lang_cmd_full_workflow(self, tmp_path):
        """Test complete workflow of setting and displaying language."""
        config_file = tmp_path / ".sboxmgr" / "config.toml"
        
        with patch('sboxmgr.cli.commands.lang.Path.home', return_value=tmp_path), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.exists.return_value = True
            mock_loader.get.return_value = "Test message"
            mock_loader.list_languages.return_value = ["en", "ru"]
            mock_loader_class.return_value = mock_loader
            
            # First, set language
            lang_cmd(set_lang="ru")
            assert config_file.exists()
            
            # Then display current settings
            with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("ru", "config file")):
                lang_cmd(set_lang=None)
            
            mock_echo.assert_any_call("Current language: ru (source: config file)")
    
    def test_lang_cmd_ai_language_detection(self):
        """Test AI language detection and display."""
        with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("en", "config file")), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('sboxmgr.cli.commands.lang.is_ai_lang') as mock_is_ai, \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.get.return_value = "Help message"
            mock_loader.list_languages.return_value = ["en", "de", "fr"]
            mock_loader_class.return_value = mock_loader
            
            # Mock some languages as AI-generated
            mock_is_ai.side_effect = lambda code: code in ["de", "fr"]
            
            lang_cmd(set_lang=None)
            
            # Should show AI markers
            mock_echo.assert_any_call("  de - Deutsch [AI]")
            mock_echo.assert_any_call("  fr - Français [AI]")
            mock_echo.assert_any_call("Note: [AI] = machine-translated, not reviewed. Contributions welcome!")
    
    def test_lang_cmd_no_ai_languages(self):
        """Test display when no AI languages are present."""
        with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("en", "config file")), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('sboxmgr.cli.commands.lang.is_ai_lang', return_value=False), \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.get.return_value = "Help message"
            mock_loader.list_languages.return_value = ["en", "ru"]
            mock_loader_class.return_value = mock_loader
            
            lang_cmd(set_lang=None)
            
            # Should not show AI note when no AI languages
            echo_calls = [call[0][0] for call in mock_echo.call_args_list]
            ai_note = "Note: [AI] = machine-translated, not reviewed. Contributions welcome!"
            assert ai_note not in echo_calls


class TestLangCmdEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_lang_cmd_empty_language_list(self):
        """Test behavior when no languages are available."""
        with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("en", "default")), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.get.return_value = "Help message"
            mock_loader.list_languages.return_value = []
            mock_loader_class.return_value = mock_loader
            
            lang_cmd(set_lang=None)
            
            mock_echo.assert_any_call("Available languages:")
            # Should handle empty list gracefully
    
    def test_lang_cmd_config_directory_creation(self, tmp_path):
        """Test that config directory is created if it doesn't exist."""
        config_dir = tmp_path / ".sboxmgr"
        assert not config_dir.exists()
        
        with patch('sboxmgr.cli.commands.lang.Path.home', return_value=tmp_path), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('typer.echo'):
            
            mock_loader = MagicMock()
            mock_loader.exists.return_value = True
            mock_loader_class.return_value = mock_loader
            
            lang_cmd(set_lang="ru")
            
            # Config directory should be created
            assert config_dir.exists()
            assert config_dir.is_dir()
    
    def test_lang_cmd_usage_instructions(self):
        """Test that usage instructions are displayed."""
        with patch('sboxmgr.cli.commands.lang.detect_lang_source', return_value=("en", "config file")), \
             patch('sboxmgr.cli.commands.lang.LanguageLoader') as mock_loader_class, \
             patch('sboxmgr.cli.commands.lang.is_ai_lang', return_value=False), \
             patch('typer.echo') as mock_echo:
            
            mock_loader = MagicMock()
            mock_loader.get.return_value = "Help message"
            mock_loader.list_languages.return_value = ["en", "ru"]
            mock_loader_class.return_value = mock_loader
            
            lang_cmd(set_lang=None)
            
            # Should show usage instructions
            mock_echo.assert_any_call("To set language persistently: sboxctl lang --set ru")
            mock_echo.assert_any_call("Or for one-time use: SBOXMGR_LANG=ru sboxctl ...") 