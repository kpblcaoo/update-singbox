"""
Тесты для проверки что версия sing-box проверяется только для singbox формата.
"""
import pytest
from unittest.mock import patch
from sboxmgr.export.export_manager import ExportManager
from sboxmgr.subscription.models import ParsedServer


class TestFormatVersionCheck:
    """Тесты проверки версии в зависимости от формата экспорта."""
    
    def test_singbox_format_checks_version(self):
        """Для singbox формата версия должна проверяться."""
        with patch('sboxmgr.utils.version.check_version_compatibility') as mock_check, \
             patch('typer.echo') as mock_echo:
            
            # check_version_compatibility возвращает (is_compatible, current_version, message)
            mock_check.return_value = (False, "1.10.5", "Outdated version")
            
            mgr = ExportManager(export_format="singbox")
            servers = [ParsedServer(type="vmess", address="test.com", port=443)]
            
            # Вызываем экспорт - версия должна проверяться
            mgr.export(servers, skip_version_check=False)
            
            # Проверяем что версия была запрошена
            mock_check.assert_called_once()
            
            # Проверяем что было показано предупреждение
            assert mock_echo.call_count >= 1
            warning_calls = [call for call in mock_echo.call_args_list if "⚠️" in str(call)]
            assert len(warning_calls) > 0
    
    def test_clash_format_skips_version_check(self):
        """Для clash формата версия НЕ должна проверяться."""
        with patch('sboxmgr.utils.version.get_singbox_version') as mock_get_version, \
             patch('sboxmgr.utils.version.check_version_compatibility') as mock_check:
            
            mgr = ExportManager(export_format="clash")
            servers = [ParsedServer(type="vmess", address="test.com", port=443)]
            
            # Вызываем экспорт - версия НЕ должна проверяться
            try:
                mgr.export(servers, skip_version_check=False)
            except Exception:
                pass  # Ожидаем ошибку т.к. clash экспортер не реализован
            
            # Проверяем что версия НЕ была запрошена
            mock_get_version.assert_not_called()
            mock_check.assert_not_called()
    
    def test_singbox_format_with_skip_version_check(self):
        """Для singbox формата с skip_version_check=True версия НЕ должна проверяться."""
        with patch('sboxmgr.utils.version.get_singbox_version') as mock_get_version, \
             patch('sboxmgr.utils.version.check_version_compatibility') as mock_check:
            
            mgr = ExportManager(export_format="singbox")
            servers = [ParsedServer(type="vmess", address="test.com", port=443)]
            
            # Вызываем экспорт с пропуском проверки версии
            mgr.export(servers, skip_version_check=True)
            
            # Проверяем что версия НЕ была запрошена
            mock_get_version.assert_not_called()
            mock_check.assert_not_called()
    
    def test_unknown_format_error(self):
        """Неизвестный формат должен вызывать ошибку."""
        mgr = ExportManager(export_format="unknown_format")
        servers = [ParsedServer(type="vmess", address="test.com", port=443)]
        
        with pytest.raises(ValueError, match="Unknown export format: unknown_format"):
            mgr.export(servers) 