"""Translation utilities and convenience functions.

This module provides convenient functions for accessing translations without
directly instantiating LanguageLoader. It includes caching mechanisms to
avoid repeated language file loading.
"""
from functools import lru_cache
from .loader import LanguageLoader

def current_lang() -> LanguageLoader:
    """Get cached instance of the current language loader.
    
    Returns:
        LanguageLoader: Cached language loader instance for current language.
    """
    return LanguageLoader()

def t(key: str) -> str:
    """Get translated string for the given key.
    
    Convenience function that uses the cached language loader to retrieve
    translated strings. This is the primary function used throughout the
    codebase for internationalization.
    
    Args:
        key: Translation key to look up (e.g., 'cli.help.url').
        
    Returns:
        Translated string or the key itself if no translation found.
    """
    return current_lang().get(key) 