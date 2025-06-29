"""Main CLI entry point for sboxctl command-line interface.

This module defines the root Typer application and registers all CLI command
groups (subscription, exclusions, lang, etc.). It serves as the primary entry
point for the `sboxctl` console script defined in pyproject.toml.
"""
import typer
import os
from dotenv import load_dotenv
from sboxmgr.logging import initialize_logging
from sboxmgr.config.models import LoggingConfig
from sboxmgr.i18n.loader import LanguageLoader
from pathlib import Path
import locale
from sboxmgr.i18n.t import t
from sboxmgr.cli import plugin_template
from sboxmgr.cli.commands.config import config_app

# Import commands for registration  
from sboxmgr.cli.commands.subscription import list_servers as subscription_list_servers
from sboxmgr.cli.commands.exclusions import exclusions
from sboxmgr.cli.commands.export import export

load_dotenv()

# Initialize logging for CLI
logging_config = LoggingConfig(
    level="INFO",
    format="text",
    sinks=["stdout"]
)
initialize_logging(logging_config)

lang = LanguageLoader(os.getenv('SBOXMGR_LANG', 'en'))

app = typer.Typer(help=lang.get("cli.help"))

SUPPORTED_PROTOCOLS = {"vless", "shadowsocks", "vmess", "trojan", "tuic", "hysteria2"}

def is_ai_lang(code):
    """Check if language is AI-generated based on metadata.
    
    Examines the language file's metadata to determine if it contains
    AI-generated translations that may need human review.
    
    Args:
        code: Language code to check (e.g., 'en', 'ru', 'de').
        
    Returns:
        True if language is marked as AI-generated, False otherwise.
    """
    import json
    from pathlib import Path
    i18n_dir = Path(__file__).parent.parent / "i18n"
    lang_file = i18n_dir / f"{code}.json"
    if lang_file.exists():
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return "__note__" in data and "AI-generated" in data["__note__"]
        except Exception:
            return False
    return False

@app.command("lang")
def lang_cmd(
    set_lang: str = typer.Option(None, "--set", "-s", help=lang.get("cli.lang.set.help")),
):
    """Manage CLI internationalization language settings.
    
    Provides language management functionality including displaying current
    language, listing available languages, and persistently setting the
    preferred language for CLI output.
    
    The language priority is:
    1. SBOXMGR_LANG environment variable
    2. Configuration file setting (~/.sboxmgr/config.toml)
    3. System locale (LANG)
    4. Default (English)
    
    Args:
        set_lang: Language code to set as default (e.g., 'en', 'ru', 'de').
        
    Raises:
        typer.Exit: If specified language is not available or config write fails.
    """
    config_path = Path.home() / ".sboxmgr" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    def detect_lang_source():
        if os.environ.get("SBOXMGR_LANG"):
            return os.environ["SBOXMGR_LANG"], "env (SBOXMGR_LANG)"
        if config_path.exists():
            try:
                import toml
                cfg = toml.load(config_path)
                if "default_lang" in cfg:
                    return cfg["default_lang"], f"config ({config_path})"
            except Exception as e:
                typer.echo(f"[Warning] Failed to read {config_path}: {e}. Falling back to system LANG.", err=True)
        sys_lang = locale.getdefaultlocale()[0]
        if sys_lang:
            return sys_lang.split("_")[0], "system LANG"
        return "en", "default"

    if set_lang:
        loader = LanguageLoader()
        if not loader.exists(set_lang):
            typer.echo(f"Language '{set_lang}' not found in i18n folder.")
            typer.echo(f"Available: {', '.join(loader.list_languages())}")
            raise typer.Exit(1)
        try:
            import toml
            with open(config_path, "w") as f:
                toml.dump({"default_lang": set_lang}, f)
            typer.echo(f"Language set to '{set_lang}' and persisted in {config_path}.")
        except Exception as e:
            typer.echo(f"[Error] Failed to write config: {e}", err=True)
            raise typer.Exit(1)
    else:
        lang_code, source = detect_lang_source()
        loader = LanguageLoader(lang_code)
        typer.echo(f"Current language: {lang_code} (source: {source})")
        if source in ("system LANG", "default"):
            # Двуязычный вывод help и notice
            en_loader = LanguageLoader("en")
            local_loader = loader if lang_code != "en" else None
            typer.echo("--- English ---")
            typer.echo(en_loader.get("cli.lang.help"))
            typer.echo(en_loader.get("cli.lang.bilingual_notice"))
            if local_loader:
                typer.echo("--- Русский ---" if lang_code == "ru" else f"--- {lang_code.upper()} ---")
                typer.echo(local_loader.get("cli.lang.help"))
                typer.echo(local_loader.get("cli.lang.bilingual_notice"))
        else:
            typer.echo(loader.get("cli.lang.help"))
        # --- Вывод языков с самоназванием и пометками ---
        LANG_NAMES = {
            "en": "English",
            "ru": "Русский",
            "de": "Deutsch",
            "zh": "中文",
            "fa": "فارسی",
            "tr": "Türkçe",
            "uk": "Українська",
            "es": "Español",
            "fr": "Français",
            "ar": "العربية",
            "pl": "Polski",
        }
        langs = loader.list_languages()
        langs_out = []
        for code in langs:
            name = LANG_NAMES.get(code, code)
            ai = " [AI]" if is_ai_lang(code) else ""
            langs_out.append(f"  {code} - {name}{ai}")
        typer.echo("Available languages:")
        for lang_line in langs_out:
            typer.echo(lang_line)
        if any(is_ai_lang(code) for code in langs):
            typer.echo("Note: [AI] = machine-translated, not reviewed. Contributions welcome!")
        typer.echo("To set language persistently: sboxctl lang --set ru")
        typer.echo("Or for one-time use: SBOXMGR_LANG=ru sboxctl ...")

app.command("plugin-template")(plugin_template.plugin_template)

# Регистрируем команды из commands/subscription.py
app.command("list-servers", help=t("cli.list_servers.help"))(subscription_list_servers)

# Регистрируем exclusions (импортированную из commands/exclusions.py)
app.command("exclusions")(exclusions)

# Регистрируем config команды
app.add_typer(config_app)

# Регистрируем команду экспорта
app.command("export", help="Export configurations in standardized formats")(export)

if __name__ == "__main__":
    app() 