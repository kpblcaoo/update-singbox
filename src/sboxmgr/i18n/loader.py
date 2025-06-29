"""Internationalization (i18n) language loader for sboxmgr.

This module provides the LanguageLoader class for loading and managing
localized strings from JSON files. It supports automatic language detection
from environment variables and system locale, with fallback to English.
"""
import json
import os
from pathlib import Path
import locale
import re
from typing import Dict, List, Optional, Tuple

class LanguageLoader:
    """Language loader for internationalization support.
    
    Loads translation strings from JSON files based on language preference.
    Supports automatic language detection, fallback to English, and sanitization
    of translation values for security.
    
    Attributes:
        lang (str): Current language code (e.g., 'en', 'ru', 'zh').
        base_dir (Path): Directory containing translation JSON files.
        translations (dict): Loaded translations for current language.
        en_translations (dict): English translations for fallback.
    """
    
    def __init__(self, lang: str = None, base_dir: Path = None):
        """Initialize the language loader.
        
        Args:
            lang: Language code to load (e.g., 'en', 'ru'). If None, 
                  auto-detects from environment and system locale.
            base_dir: Directory containing translation files. If None,
                     uses the directory containing this module.
        """
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        
        if lang is None:
            lang, _ = self.get_preferred_lang_with_source()
        
        self.lang = lang or "en"
        self.translations: Dict[str, str] = {}
        self.en_translations: Dict[str, str] = {}
        
        self.load()

    def load(self):
        """Load translation files for current language and English fallback.
        
        Loads the JSON translation file for the current language, with English
        as fallback. If the current language file doesn't exist, falls back to
        English only. All loaded translations are sanitized for security.
        """
        file = self.base_dir / f"{self.lang}.json"
        en_file = self.base_dir / "en.json"
        
        # Load current language
        if file.exists():
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    raw_translations = json.load(f)
                    self.translations = self.sanitize(raw_translations)
            except (json.JSONDecodeError, OSError):
                self.translations = {}
        else:
            self.translations = {}
        
        # Load English fallback
        if en_file.exists():
            try:
                with open(en_file, 'r', encoding='utf-8') as f:
                    raw_en = json.load(f)
                    self.en_translations = self.sanitize(raw_en)
            except (json.JSONDecodeError, OSError):
                self.en_translations = {}
        else:
            self.en_translations = {}

    def sanitize(self, mapping: dict) -> dict:
        """Sanitize translation values for security.
        
        Removes ANSI escape sequences, limits string length, and filters out
        potentially dangerous content from translation values.
        
        Args:
            mapping: Dictionary of translation key-value pairs.
            
        Returns:
            Sanitized dictionary with cleaned translation values.
        """
        # Remove ANSI escape sequences completely
        def clean_value(v):
            if isinstance(v, str):
                # Remove all ANSI escape sequences: \x1b[ followed by any characters until a letter
                # This covers: \x1b[31m, \x1b[1;33m, \x1b(B, \x1b)P, etc.
                cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', v)
                # Also remove other ANSI sequences like \x1b(, \x1b), \x1bP, etc.
                cleaned = re.sub(r'\x1b[()P]', '', cleaned)
                # Remove incomplete ANSI sequences (like \x1b[31 without ending letter)
                cleaned = re.sub(r'\x1b\[[0-9;]*$', '', cleaned)
                # Remove any remaining \x1b characters
                cleaned = re.sub(r'\x1b', '', cleaned)
                # Limit length to 500 characters
                return cleaned[:500]
            return str(v)[:500]
        
        return {
            k: clean_value(v)
            for k, v in mapping.items()
            if isinstance(k, str) and len(k) < 100
        }

    def get(self, key: str) -> str:
        """Get translated string for the given key.
        
        Looks up the translation key in the current language first, then falls
        back to English if not found. If the key doesn't exist in either
        language, returns the key itself.
        
        Args:
            key: Translation key to look up.
            
        Returns:
            Translated string or the key itself if no translation found.
        """
        # Сначала ищем в локальном языке, затем в en, иначе возвращаем ключ
        return self.translations.get(key) or self.en_translations.get(key, key)

    def get_with_source(self, key: str) -> tuple:
        """Get translated string with source language information.
        
        Args:
            key: Translation key to look up.
            
        Returns:
            Tuple of (translated_string, source_language) where source_language
            is the language code that provided the translation ('local', 'en', 
            or 'fallback').
        """
        local = self.translations.get(key)
        en = self.en_translations.get(key)
        
        if local:
            return local, "local"
        if en:
            return en, "en"
        return key, "fallback"

    def get_with_fallback(self, key: str) -> str:
        """Get translated string with fallback behavior (compatibility method).
        
        This method provides compatibility with existing code that expects
        fallback behavior. It simply delegates to the get() method.
        
        Args:
            key: Translation key to look up.
            
        Returns:
            Translated string or the key itself if no translation found.
        """
        return self.get(key)

    def exists(self, lang_code: str) -> bool:
        """Check if translation file exists for given language code.
        
        Args:
            lang_code: Language code to check (e.g., 'en', 'ru').
            
        Returns:
            True if translation file exists, False otherwise.
        """
        return (self.base_dir / f"{lang_code}.json").exists()

    def list_languages(self) -> list:
        """List all available language codes.
        
        Scans the translation directory for JSON files and returns their
        base names as language codes.
        
        Returns:
            Sorted list of available language codes.
        """
        return sorted([p.stem for p in self.base_dir.glob("*.json")])

    @staticmethod
    def get_preferred_lang_with_source() -> tuple:
        """Detect preferred language from environment and system locale.
        
        Checks environment variables (SBOXMGR_LANG, LANG, LC_ALL) and system
        locale to determine the preferred language.
        
        Returns:
            Tuple of (language_code, source) where source indicates where the
            language preference was detected from ('env', 'locale', or 'default').
        """
        # 1. env
        lang = os.environ.get("SBOXMGR_LANG")
        if lang:
            return lang, "env"
        
        # 2. config file
        config_path = Path.home() / ".sboxmgr" / "config.toml"
        if config_path.exists():
            try:
                import toml
                cfg = toml.load(config_path)
                if "default_lang" in cfg:
                    return cfg["default_lang"], "config"
            except Exception:
                pass
        
        # 3. LANG/LC_ALL
        for env_var in ["LANG", "LC_ALL"]:
            lang = os.environ.get(env_var)
            if lang:
                # Извлекаем код языка из локали (например, "ru_RU.UTF-8" -> "ru")
                lang_code = lang.split('.')[0].split('_')[0]
                if lang_code:
                    return lang_code, "env"
        
        # 4. system locale
        try:
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang:
                lang_code = sys_lang.split('_')[0]
                return lang_code, "locale"
        except (TypeError, AttributeError):
            pass
        
        return "en", "default" 