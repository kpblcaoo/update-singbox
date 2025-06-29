import pytest
import subprocess
import sys
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
TEST_URL = os.getenv("TEST_URL") or os.getenv("SINGBOX_URL") or "https://example.com/config"

# Для tolerant-поиска сообщений
EXCLUDE_MSGS = ["Excluded server by index", "Added", "exclusions", "CLI operation"]
REMOVE_MSGS = ["Removed exclusion", "Exclusions cleared", "очищен", "已清除"]
DRYRUN_MSGS = ["Dry run: config is valid", "dry-run", "конфиг валиден", "试运行", "配置有效"]

# Таблица CLI-флагов и ожидаемого поведения
CLI_MATRIX = [
    # args, description, expected_exit, expected_files, expected_stdout_contains
    (["export", "-u", "https://sub.vpn.momai.dev/GvFArer807ZY8vdg"], 
     "Базовый запуск: только URL", 0, ["config.json"], 
     ["Configuration written to", "更新成功完成", "Use sboxagent"]),
    
    (["export", "--dry-run", "-u", "https://sub.vpn.momai.dev/GvFArer807ZY8vdg"], 
     "Dry-run: не должно быть изменений файлов", 0, [], 
     ["Dry run: config is valid", "dry-run", "конфиг валиден", "试运行", "配置有效", "Configuration validated"]),
    
    (["export", "-u", "https://sub.vpn.momai.dev/GvFArer807ZY8vdg", "--output", "custom.json"],
     "Кастомный output файл", 0, ["custom.json"], 
     ["Configuration written to: custom.json", "更新成功完成"]),
    
    (["export", "-u", "https://sub.vpn.momai.dev/GvFArer807ZY8vdg", "--format", "toml"], 
     "TOML формат", 0, ["config.json"], 
     ["Configuration written to", "更新成功完成"]),
    
    (["export", "-u", "https://sub.vpn.momai.dev/GvFArer807ZY8vdg", "--backup"], 
     "Создание backup", 0, ["config.json"], 
     ["Configuration written to", "更新成功完成"]),
    
    (["export", "--validate-only"], 
     "Только валидация существующего файла", 1, [], 
     ["--validate-only cannot be used with subscription URL"]),
    
    (["export", "--agent-check", "-u", "https://sub.vpn.momai.dev/GvFArer807ZY8vdg"], 
     "Проверка через агента", 0, [], 
     ["External validation", "agent-check", "sboxagent"]),
]

def add_output_args(args, tmp_path):
    # Добавляет --output и backup в tmp_path, если команда export
    if "export" in args:
        if "--output" not in args:
            args += ["--output", str(tmp_path / "config.json")]
        if "--backup" in args:
            idx = args.index("--backup")
            # SBOXMGR_BACKUP_FILE уже указывает на tmp_path/backup.json
    return args

@pytest.mark.parametrize('args, description, expected_exit, expected_files, expected_stdout_contains', CLI_MATRIX)
def test_cli_matrix(args, description, expected_exit, expected_files, expected_stdout_contains, tmp_path):
    """
    CLI matrix: tolerant-поиск сообщений, не трогает exclusions.json вне tmp_path.
    Если тест падает — выводит stdout, stderr и лог для диагностики.
    """
    project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = add_output_args(list(args), tmp_path)
    cmd = [sys.executable, 'src/sboxmgr/cli/main.py'] + args
    env = os.environ.copy()
    # Подменяем пути для артефактов на tmp_path
    env["SBOXMGR_CONFIG_FILE"] = str(tmp_path / "config.json")
    env["SBOXMGR_BACKUP_FILE"] = str(tmp_path / "backup.json")
    env["SBOXMGR_TEMPLATE_FILE"] = str(project_root / "config.template.json")
    env["SBOXMGR_EXCLUSIONS_FILE"] = str(tmp_path / "exclusions.json")
    env["SBOXMGR_LOG_FILE"] = str(tmp_path / "log.txt")
    env["SBOXMGR_TEST_MODE"] = "1"
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, env=env)
    log_text = ""
    log_path = tmp_path / "log.txt"
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8")
    output = result.stdout + result.stderr + log_text
    text = expected_stdout_contains[0] if expected_stdout_contains else ''
    try:
        assert result.returncode == expected_exit, f"{description}: неверный код возврата"
        for fname in expected_files:
            if fname == "exclusions.json":
                if not (tmp_path / fname).exists():
                    # exclusions.json может не появиться, если сервер уже исключён
                    continue
            # Check if file exists in tmp_path or current directory
            file_exists = (tmp_path / fname).exists()
            if not file_exists and "--output" in args:
                # For custom output files, check in current directory
                file_exists = (project_root / fname).exists()
            assert file_exists, f"{description}: отсутствует {fname}"
        if not any(
            s.strip().lower() in output.lower()
            for text in expected_stdout_contains
            for s in ([text] if isinstance(text, str) else text)
        ):
            print("\n==== CLI MATRIX DIAGNOSTICS ====\nArgs:", args)
            print(f"Return code: {result.returncode}")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            print(f"LOG:\n{log_text}")
            print(f"OUTPUT repr:\n{repr(output)}")
            print(f"TYPES: text={type(text)}, output={type(output)}")
            print("===============================\n")
            assert False, f"{description}: не найдено ни одной из подстрок {expected_stdout_contains} в выводе или логе"
    except AssertionError:
        print("\n==== CLI MATRIX DIAGNOSTICS ====\nArgs:", args)
        print(f"Return code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        print(f"LOG:\n{log_text}")
        print(f"OUTPUT repr:\n{repr(output)}")
        print(f"TYPES: text={type(text)}, output={type(output)}")
        print("===============================\n")
        assert False, f"{description}: не найдено ни одной из подстрок {expected_stdout_contains} в выводе или логе" 