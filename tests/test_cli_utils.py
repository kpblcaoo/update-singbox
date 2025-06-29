import json
import os
from pathlib import Path
from unittest.mock import patch
from sboxmgr.cli.utils import is_ai_lang


class TestIsAiLang:
    """Test is_ai_lang function."""
    
    def test_is_ai_lang_with_ai_marker(self, tmp_path):
        """Test is_ai_lang returns True for AI-generated language files."""
        # Create mock i18n directory
        i18n_dir = tmp_path / "i18n"
        i18n_dir.mkdir()
        
        # Create language file with AI marker
        lang_file = i18n_dir / "de.json"
        lang_data = {
            "__note__": "AI-generated translations, may need review",
            "cli.help": "Hilfe für CLI",
            "error.config_load_failed": "Konfiguration laden fehlgeschlagen"
        }
        lang_file.write_text(json.dumps(lang_data, indent=2))
        
        # Mock the i18n directory path
        with patch('sboxmgr.cli.utils.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            result = is_ai_lang("de")
            
        assert result is True
    
    def test_is_ai_lang_without_ai_marker(self, tmp_path):
        """Test is_ai_lang returns False for human-reviewed language files."""
        # Create mock i18n directory
        i18n_dir = tmp_path / "i18n"
        i18n_dir.mkdir()
        
        # Create language file without AI marker
        lang_file = i18n_dir / "en.json"
        lang_data = {
            "cli.help": "Help for CLI",
            "error.config_load_failed": "Configuration load failed"
        }
        lang_file.write_text(json.dumps(lang_data, indent=2))
        
        # Mock the i18n directory path
        with patch('sboxmgr.cli.utils.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            result = is_ai_lang("en")
            
        assert result is False
    
    def test_is_ai_lang_with_different_note(self, tmp_path):
        """Test is_ai_lang returns False for files with different note."""
        # Create mock i18n directory
        i18n_dir = tmp_path / "i18n"
        i18n_dir.mkdir()
        
        # Create language file with different note
        lang_file = i18n_dir / "ru.json"
        lang_data = {
            "__note__": "Human-reviewed translations",
            "cli.help": "Помощь по CLI",
            "error.config_load_failed": "Ошибка загрузки конфигурации"
        }
        lang_file.write_text(json.dumps(lang_data, indent=2))
        
        # Mock the i18n directory path
        with patch('sboxmgr.cli.utils.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            result = is_ai_lang("ru")
            
        assert result is False
    
    def test_is_ai_lang_file_not_exists(self, tmp_path):
        """Test is_ai_lang returns False for non-existent language files."""
        # Create empty i18n directory
        i18n_dir = tmp_path / "i18n"
        i18n_dir.mkdir()
        
        # Mock the i18n directory path
        with patch('sboxmgr.cli.utils.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            result = is_ai_lang("nonexistent")
            
        assert result is False
    
    def test_is_ai_lang_invalid_json(self, tmp_path):
        """Test is_ai_lang returns False for invalid JSON files."""
        # Create mock i18n directory
        i18n_dir = tmp_path / "i18n"
        i18n_dir.mkdir()
        
        # Create invalid JSON file
        lang_file = i18n_dir / "invalid.json"
        lang_file.write_text("invalid json content")
        
        # Mock the i18n directory path
        with patch('sboxmgr.cli.utils.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            result = is_ai_lang("invalid")
            
        assert result is False
    
    def test_is_ai_lang_partial_ai_marker(self, tmp_path):
        """Test is_ai_lang with partial AI marker."""
        # Create mock i18n directory
        i18n_dir = tmp_path / "i18n"
        i18n_dir.mkdir()
        
        # Create language file with partial AI marker
        lang_file = i18n_dir / "partial.json"
        lang_data = {
            "__note__": "Some AI-generated content mixed with human review",
            "cli.help": "Mixed content"
        }
        lang_file.write_text(json.dumps(lang_data, indent=2))
        
        # Mock the i18n directory path
        with patch('sboxmgr.cli.utils.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            result = is_ai_lang("partial")
            
        assert result is True
    
    def test_is_ai_lang_file_read_permission_error(self, tmp_path):
        """Test is_ai_lang handles file read permission errors."""
        # Create mock i18n directory
        i18n_dir = tmp_path / "i18n"
        i18n_dir.mkdir()
        
        # Create language file
        lang_file = i18n_dir / "protected.json"
        lang_data = {"__note__": "AI-generated"}
        lang_file.write_text(json.dumps(lang_data))
        
        # Mock file reading to raise exception
        with patch('sboxmgr.cli.utils.Path') as mock_path, \
             patch('builtins.open', side_effect=PermissionError("Access denied")):
            mock_path.return_value.parent.parent = tmp_path
            result = is_ai_lang("protected")
            
        assert result is False


class TestDetectLangSource:
    """Test detect_lang_source function."""
    
    def test_detect_lang_source_env_variable(self):
        """Test detect_lang_source with SBOXMGR_LANG environment variable."""
        with patch.dict(os.environ, {'SBOXMGR_LANG': 'ru'}):
            from sboxmgr.cli.utils import detect_lang_source
            lang_code, source = detect_lang_source()
            
        assert lang_code == 'ru'
        assert source == "env (SBOXMGR_LANG)"
    
    def test_detect_lang_source_config_file(self, tmp_path):
        """Test detect_lang_source with config file."""
        # Create mock config directory and file
        config_dir = tmp_path / ".sboxmgr"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text('default_lang = "de"\n')
        
        with patch.dict(os.environ, {}, clear=True), \
             patch('sboxmgr.cli.utils.Path.home') as mock_home:
            
            mock_home.return_value = tmp_path
            
            from sboxmgr.cli.utils import detect_lang_source
            lang_code, source = detect_lang_source()
            
        assert lang_code == "de"
        assert str(config_file) in source
    
    def test_detect_lang_source_system_lang(self):
        """Test detect_lang_source with system locale."""
        with patch.dict(os.environ, {}, clear=True), \
             patch('sboxmgr.cli.utils.Path.home') as mock_home, \
             patch('locale.getdefaultlocale') as mock_locale:
            
            # Mock config file doesn't exist
            mock_home.return_value = Path("/nonexistent")
            mock_locale.return_value = ("en_US", "UTF-8")
            
            from sboxmgr.cli.utils import detect_lang_source
            lang_code, source = detect_lang_source()
            
        assert lang_code == "en"
        assert source == "system LANG"
    
    def test_detect_lang_source_default_fallback(self):
        """Test detect_lang_source falls back to default."""
        with patch.dict(os.environ, {}, clear=True), \
             patch('sboxmgr.cli.utils.Path.home') as mock_home, \
             patch('locale.getdefaultlocale') as mock_locale:
            
            # Mock config file doesn't exist and no system locale
            mock_home.return_value = Path("/nonexistent")
            mock_locale.return_value = (None, None)
            
            from sboxmgr.cli.utils import detect_lang_source
            lang_code, source = detect_lang_source()
            
        assert lang_code == "en"
        assert source == "default"
    
    def test_detect_lang_source_config_file_error(self, tmp_path):
        """Test detect_lang_source handles config file read errors."""
        # Create mock config file
        config_file = tmp_path / ".sboxmgr" / "config.toml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("invalid toml content [")
        
        with patch.dict(os.environ, {}, clear=True), \
             patch('sboxmgr.cli.utils.Path.home') as mock_home, \
             patch('locale.getdefaultlocale') as mock_locale:
            
            mock_home.return_value = tmp_path
            mock_locale.return_value = ("fr_FR", "UTF-8")
            
            from sboxmgr.cli.utils import detect_lang_source
            lang_code, source = detect_lang_source()
            
        assert lang_code == "fr"
        assert source == "system LANG"
    
    def test_detect_lang_source_complex_locale(self):
        """Test detect_lang_source with complex locale format."""
        with patch.dict(os.environ, {}, clear=True), \
             patch('sboxmgr.cli.utils.Path.home') as mock_home, \
             patch('locale.getdefaultlocale') as mock_locale:
            
            mock_home.return_value = Path("/nonexistent")
            mock_locale.return_value = ("zh_CN.UTF-8", "UTF-8")
            
            from sboxmgr.cli.utils import detect_lang_source
            lang_code, source = detect_lang_source()
            
        assert lang_code == "zh"
        assert source == "system LANG"
    
    def test_detect_lang_source_config_without_lang(self, tmp_path):
        """Test detect_lang_source with config file without default_lang."""
        config_file = tmp_path / ".sboxmgr" / "config.toml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text('some_other_setting = "value"\n')
        
        with patch.dict(os.environ, {}, clear=True), \
             patch('sboxmgr.cli.utils.Path.home') as mock_home, \
             patch('locale.getdefaultlocale') as mock_locale, \
             patch('toml.load') as mock_toml_load:
            
            mock_home.return_value = tmp_path
            mock_locale.return_value = ("es_ES", "UTF-8")
            mock_toml_load.return_value = {"some_other_setting": "value"}
            
            from sboxmgr.cli.utils import detect_lang_source
            lang_code, source = detect_lang_source()
            
        assert lang_code == "es"
        assert source == "system LANG" 