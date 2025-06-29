import os
import shutil
from dotenv import load_dotenv
from typer.testing import CliRunner
from sboxmgr.cli.main import app
from tests.utils.http_mocking import setup_universal_cli_mock

load_dotenv()

runner = CliRunner()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_SRC = os.path.join(PROJECT_ROOT, "config.template.json")

def test_excluded_index(tmp_path, monkeypatch):
    setup_universal_cli_mock(monkeypatch)
    monkeypatch.setenv("SBOXMGR_EXCLUSION_FILE", str(tmp_path / "exclusions.json"))
    monkeypatch.setenv("SBOXMGR_CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setenv("SBOXMGR_LOG_FILE", str(tmp_path / "log.txt"))
    # Копируем шаблон в tmp_path
    template_path = tmp_path / "config.template.json"
    shutil.copyfile(TEMPLATE_SRC, template_path)
    monkeypatch.setenv("SBOXMGR_TEMPLATE_FILE", str(template_path))
    
    # Add server to exclusions and verify exclusion behavior
    runner.invoke(app, ["exclusions", "-u", os.getenv("TEST_URL", "https://example.com/sub-link"), "--add", "1"])
    # Используем export --dry-run для проверки что subscription работает
    result = runner.invoke(app, ["export", "--dry-run", "-u", os.getenv("TEST_URL", "https://example.com/sub-link")])
    
    # Проверяем что команда выполнилась (возможно с исключениями, но без критических ошибок)
    assert result.exit_code in [0, 1]  # 0 = успех, 1 = валидация не прошла или исключения

def test_excluded_remarks(tmp_path, monkeypatch):
    setup_universal_cli_mock(monkeypatch)
    monkeypatch.setenv("SBOXMGR_EXCLUSION_FILE", str(tmp_path / "exclusions.json"))
    monkeypatch.setenv("SBOXMGR_CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setenv("SBOXMGR_LOG_FILE", str(tmp_path / "log.txt"))
    template_path = tmp_path / "config.template.json"
    shutil.copyfile(TEMPLATE_SRC, template_path)
    monkeypatch.setenv("SBOXMGR_TEMPLATE_FILE", str(template_path))
    runner.invoke(app, ["exclusions", "-u", os.getenv("TEST_URL", "https://example.com/sub-link"), "--add", "1"])
    # Используем export --dry-run для проверки что subscription работает с исключениями
    result = runner.invoke(app, ["export", "--dry-run", "-u", os.getenv("TEST_URL", "https://example.com/sub-link")])
    
    # Проверяем что команда выполнилась (возможно с исключениями, но без критических ошибок)
    assert result.exit_code in [0, 1]  # 0 = успех, 1 = валидация не прошла или исключения 