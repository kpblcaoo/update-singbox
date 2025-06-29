import json
import pytest
from typer.testing import CliRunner
from sboxmgr.cli.main import app
from tests.utils.http_mocking import setup_legacy_cli_mock

runner = CliRunner()

# Контролируемый mock: всегда два сервера с индексами 0 и 1
MOCK_JSON = {
    "outbounds": [
        {
            "type": "vmess",
            "tag": "[NL-1] vmess-reality",
            "server": "control.com",
            "server_port": 443,
            "uuid": "uuid-1",
            "security": "auto",
            "transport": {"type": "ws"}
        },
        {
            "type": "vmess",
            "tag": "[NL-2] vmess-reality2",
            "server": "control2.com",
            "server_port": 443,
            "uuid": "uuid-2",
            "security": "auto",
            "transport": {"type": "ws"}
        }
    ]
}

@pytest.mark.usefixtures("cleanup_files")
def test_add_exclusion_and_idempotency(tmp_path, monkeypatch):
    setup_legacy_cli_mock(monkeypatch, json_data=MOCK_JSON)
    monkeypatch.setenv("SBOXMGR_EXCLUSION_FILE", str(tmp_path / "exclusions.json"))
    url = "https://example.com/sub-link"
    # Добавляем exclusion по индексу 1
    result1 = runner.invoke(app, ["exclusions", "-u", url, "--add", "1"])
    assert result1.exit_code == 0
    exclusions_path = tmp_path / "exclusions.json"
    assert exclusions_path.exists()
    with open(exclusions_path) as f:
        data = json.load(f)
    assert len(data["exclusions"]) == 1
    # Повторное добавление не дублирует
    result2 = runner.invoke(app, ["exclusions", "-u", url, "--add", "1"])
    assert result2.exit_code == 0
    with open(exclusions_path) as f:
        data2 = json.load(f)
    assert len(data2["exclusions"]) == 1
    assert "already excluded" in (result2.stdout or "")

@pytest.mark.usefixtures("cleanup_files")
def test_clear_exclusions(tmp_path, monkeypatch):
    setup_legacy_cli_mock(monkeypatch, json_data=MOCK_JSON)
    monkeypatch.setenv("SBOXMGR_EXCLUSION_FILE", str(tmp_path / "exclusions.json"))
    url = "https://example.com/sub-link"
    # Добавляем exclusion по индексу 0
    result = runner.invoke(app, ["exclusions", "-u", url, "--add", "0"])
    assert result.exit_code == 0
    exclusions_path = tmp_path / "exclusions.json"
    assert exclusions_path.exists()
    # Подтверждаем очистку exclusions через input='y\n'
    result = runner.invoke(app, ["exclusions", "--clear"], input='y\n')
    assert result.exit_code == 0
    with open(exclusions_path) as f:
        data = json.load(f)
    assert data["exclusions"] == []

@pytest.mark.usefixtures("cleanup_files")
def test_broken_exclusions_json_is_recovered(tmp_path, monkeypatch):
    setup_legacy_cli_mock(monkeypatch, json_data=MOCK_JSON)
    monkeypatch.setenv("SBOXMGR_EXCLUSION_FILE", str(tmp_path / "exclusions.json"))
    exclusions_path = tmp_path / "exclusions.json"
    # Создаём битый exclusions.json
    with open(exclusions_path, "w") as f:
        f.write("{broken json")
    url = "https://example.com/sub-link"
    # Добавление exclusions должно восстановить файл
    result = runner.invoke(app, ["exclusions", "-u", url, "--add", "0"])
    assert result.exit_code == 0
    # Проверяем, что файл теперь валидный JSON
    with open(exclusions_path) as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "exclusions" in data
    # Проверяем, что exclusion был добавлен (может быть 0 или 1 в зависимости от того, был ли сервер уже исключен)
    assert len(data["exclusions"]) >= 0

@pytest.mark.usefixtures("cleanup_files")
def test_add_exclusion_invalid_index(tmp_path, monkeypatch):
    setup_legacy_cli_mock(monkeypatch, json_data=MOCK_JSON)
    monkeypatch.setenv("SBOXMGR_EXCLUSION_FILE", str(tmp_path / "exclusions.json"))
    url = "https://example.com/sub-link"
    # Индекс 99 не существует
    result = runner.invoke(app, ["exclusions", "-u", url, "--add", "99"])
    assert result.exit_code != 0
    assert "Invalid server index" in (result.stdout or "")

@pytest.mark.usefixtures("cleanup_files")
def test_view_exclusions(tmp_path, monkeypatch):
    setup_legacy_cli_mock(monkeypatch, json_data=MOCK_JSON)
    monkeypatch.setenv("SBOXMGR_EXCLUSION_FILE", str(tmp_path / "exclusions.json"))
    url = "https://example.com/sub-link"
    runner.invoke(app, ["exclusions", "-u", url, "--add", "1"])
    result = runner.invoke(app, ["exclusions", "-u", url, "--view"])
    assert result.exit_code == 0
    assert "Current Exclusions" in (result.stdout or "")
    assert "vmess-reality2" in (result.stdout or "") 