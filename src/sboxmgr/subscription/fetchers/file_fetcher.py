"""Local file system subscription fetcher implementation.

This module provides the FileFetcher class for reading subscription data
from local files. It supports various file formats and provides caching
mechanisms for improved performance when processing multiple subscriptions
from the same file sources.
"""
from pathlib import Path
import threading
from typing import Dict, Tuple
from ..models import SubscriptionSource
from ..base_fetcher import BaseFetcher
from ..registry import register

@register("file")
class FileFetcher(BaseFetcher):
    """Fetcher for reading subscription data from local files.
    
    This fetcher handles local file system access with proper error handling,
    caching, and security validation. It supports reading from various file
    formats and provides thread-safe caching for improved performance.
    
    Attributes:
        SUPPORTED_SCHEMES: Tuple of supported URL schemes ("file",).
        _cache_lock: Thread lock for cache synchronization.
        _fetch_cache: Cache dictionary for storing fetched file contents.
    """
    SUPPORTED_SCHEMES: Tuple[str, ...] = ("file",)
    _cache_lock = threading.Lock()
    _fetch_cache: Dict[Tuple[str], bytes] = {}

    def __init__(self, source: SubscriptionSource):
        super().__init__(source)

    def fetch(self, force_reload: bool = False) -> bytes:
        """Загружает данные из локального файла с кешированием и проверкой размера.

        Args:
            force_reload (bool, optional): Принудительно сбросить кеш и заново получить результат.

        Returns:
            bytes: Содержимое файла.

        Raises:
            ValueError: Если размер файла превышает лимит.
            FileNotFoundError: Если файл не найден.
        """
        key = (self.source.url,)
        if force_reload:
            with self._cache_lock:
                self._fetch_cache.pop(key, None)
        with self._cache_lock:
            if key in self._fetch_cache:
                return self._fetch_cache[key]
        
        # Убираем схему file:// из URL
        path_str = self.source.url.replace("file://", "", 1)
        path = Path(path_str)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        # Проверяем размер файла перед чтением
        file_size = path.stat().st_size
        size_limit = self._get_size_limit()
        
        if file_size > size_limit:
            raise ValueError(f"File size ({file_size} bytes) exceeds limit ({size_limit} bytes)")
        
        with open(path, "rb") as f:
            data = f.read()
            
        with self._cache_lock:
            self._fetch_cache[key] = data
        return data

    @classmethod
    def validate_url_scheme(cls, url: str):
        """Валидирует схему URL для FileFetcher."""
        if not url.startswith("file://"):
            raise ValueError(f"FileFetcher supports only file:// URLs, got: {url}")

 