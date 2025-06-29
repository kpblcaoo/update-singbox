"""JSON-based subscription fetcher implementation.

This module provides the JSONFetcher class for retrieving subscription data
from JSON API endpoints. It handles JSON parsing, validation, and provides
caching mechanisms for improved performance and reduced API load.
"""
import requests
from ..base_fetcher import BaseFetcher
from ..registry import register
import threading
from typing import Dict, Tuple, Optional

@register("url_json")
class JSONFetcher(BaseFetcher):
    """Fetcher for JSON-based subscription APIs.
    
    This fetcher specializes in handling JSON API endpoints with proper
    content-type validation, JSON parsing, and error handling. It provides
    thread-safe caching and supports various JSON subscription formats.
    
    Attributes:
        _cache_lock: Thread lock for cache synchronization.
        _fetch_cache: Cache dictionary for storing fetched JSON data.
    """
    _cache_lock = threading.Lock()
    _fetch_cache: Dict[Tuple[str, Optional[str], str], bytes] = {}

    def fetch(self, force_reload: bool = False) -> bytes:
        """Загружает подписку в формате JSON с поддержкой лимита размера и in-memory кешированием.

        Args:
            force_reload (bool, optional): Принудительно сбросить кеш и заново получить результат.

        Returns:
            bytes: Сырые данные подписки.

        Raises:
            ValueError: Если размер файла превышает лимит.
            requests.RequestException: Если не удалось скачать файл.
        """
        key = (self.source.url, getattr(self.source, 'user_agent', None), str(getattr(self.source, 'headers', None)))
        if force_reload:
            with self._cache_lock:
                self._fetch_cache.pop(key, None)
        with self._cache_lock:
            if key in self._fetch_cache:
                return self._fetch_cache[key]
        size_limit = self._get_size_limit()
        if self.source.url.startswith("file://"):
            path = self.source.url.replace("file://", "", 1)
            with open(path, "rb") as f:
                data = f.read(size_limit + 1)
                if len(data) > size_limit:
                    print(f"[fetcher][WARN] File size exceeds limit ({size_limit} bytes), skipping.")
                    raise ValueError("File size exceeds limit")
                with self._cache_lock:
                    self._fetch_cache[key] = data
                return data
        else:
            headers = dict(self.source.headers) if self.source.headers else {}
            ua = self.source.user_agent
            if ua is None:
                ua = "ClashMeta/1.0"  # дефолтный UA
                headers["User-Agent"] = ua
            elif ua != "":  # Добавляем только если UA не пустой
                headers["User-Agent"] = ua
            print(f"[fetcher] Using User-Agent: {headers.get('User-Agent', '[none]')}")
            resp = requests.get(self.source.url, headers=headers, stream=True, timeout=30)
            resp.raise_for_status()
            
            # Используем iter_content для правильной обработки сжатых данных
            data = b""
            for chunk in resp.iter_content(chunk_size=8192):
                if len(data) + len(chunk) > size_limit:
                    print(f"[fetcher][WARN] Downloaded data exceeds limit ({size_limit} bytes), skipping.")
                    raise ValueError("Downloaded data exceeds limit")
                data += chunk
            
            with self._cache_lock:
                self._fetch_cache[key] = data
            return data

 