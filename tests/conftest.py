# Инициализируем логирование для тестов ПЕРЕД всеми импортами
import sys
import subprocess
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем src в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Импорты sboxmgr
from sboxmgr.logging.core import initialize_logging
from sboxmgr.config.models import LoggingConfig
import sboxmgr.logging.core

# Мокаем get_logger до инициализации логирования
sboxmgr.logging.core.get_logger = MagicMock(return_value=MagicMock())

# Инициализируем логирование сразу
logging_config = LoggingConfig(
    level="DEBUG",
    sinks=["stdout"],
    format="text"
)
initialize_logging(logging_config)

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

def run_cli(args, env=None, cwd=None):
    """Вспомогательная функция для вызова CLI с capture_output.
    exclusions.json и selected_config.json будут создаваться в cwd (tmp_path) через env.
    """
    if env is None:
        env = os.environ.copy()
    # Указать файлы в tmp_path
    cwd = cwd or os.getcwd()
    env["SBOXMGR_EXCLUSION_FILE"] = str(Path(cwd) / "exclusions.json")
    env["SBOXMGR_SELECTED_CONFIG_FILE"] = str(Path(cwd) / "selected_config.json")
    # Использовать временный лог файл для тестов
    env["SBOXMGR_LOG_FILE"] = str(Path(cwd) / "test.log")
    result = subprocess.run(
        [sys.executable, "src/sboxmgr/cli/main.py"] + args,
        capture_output=True, text=True, env=env, cwd=PROJECT_ROOT
    )
    return result

@pytest.fixture(autouse=True)
def cleanup_files(tmp_path, monkeypatch):
    """Фикстура: каждый тест работает в своём tmp_path, файлы очищаются автоматически."""
    monkeypatch.chdir(tmp_path)
    for fname in ["exclusions.json", "selected_config.json"]:
        if os.path.exists(fname):
            os.remove(fname)
    yield
    # После теста — ещё раз чистим
    for fname in ["exclusions.json", "selected_config.json"]:
        if os.path.exists(fname):
            os.remove(fname)

@pytest.fixture(autouse=True)
def mock_logging_setup():
    """Mock sboxmgr logging setup to prevent initialization errors during test collection."""
    with patch('sboxmgr.logging.core.initialize_logging') as mock_init, \
         patch('sboxmgr.logging.core.get_logger') as mock_get_logger:
        mock_init.return_value = None
        mock_get_logger.return_value = MagicMock()
        yield 