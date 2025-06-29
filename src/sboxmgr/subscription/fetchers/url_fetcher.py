"""HTTP/HTTPS URL fetcher with caching and compression support.

This module provides the URLFetcher class for retrieving subscription data
from HTTP/HTTPS URLs and local file:// URLs. It includes support for gzip
decompression, response caching, custom headers, user agents, and size limits
for secure and efficient subscription data fetching.
"""
import requests
import gzip
from ..models import SubscriptionSource
from ..base_fetcher import BaseFetcher
from ..registry import register
import threading
from sboxmgr.utils.env import get_fetch_timeout
from typing import Dict, Tuple, Optional

@register("url")
@register("url_base64")
@register("uri_list")
class URLFetcher(BaseFetcher):
    """HTTP/HTTPS URL fetcher with caching and compression support.
    
    This fetcher handles HTTP/HTTPS URLs and local file:// URLs with support
    for gzip decompression, response caching, custom headers, and user agents.
    It provides thread-safe caching and respects size limits for security.
    
    Attributes:
        _cache_lock: Thread lock for cache synchronization.
        _fetch_cache: Cache dictionary for storing fetched data.
    """
    _cache_lock = threading.Lock()
    _fetch_cache: Dict[Tuple[str, Optional[str], str], bytes] = {}

    def __init__(self, source: SubscriptionSource):
        super().__init__(source)  # SEC: centralized scheme validation

    def fetch(self, force_reload: bool = False) -> bytes:
        """Загружает данные по URL или из файла с поддержкой лимита размера, кеша и user-agent.

        Args:
            force_reload (bool, optional): Принудительно сбросить кеш и заново получить результат.

        Returns:
            bytes: Сырые данные источника.

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
                # Check if data is gzipped and decompress if needed
                data = self._decompress_if_gzipped(data)
                with self._cache_lock:
                    self._fetch_cache[key] = data
                return data
        else:
            headers = dict(self.source.headers) if self.source.headers else {}
            ua = self.source.user_agent
            if ua is None:
                ua = "ClashMeta/1.0"  # дефолтный UA
            if ua != "":
                headers["User-Agent"] = ua
            # Убираем безусловный print - будет логироваться в manager.py
            timeout = get_fetch_timeout()
            resp = requests.get(self.source.url, headers=headers, stream=True, timeout=timeout)
            resp.raise_for_status()
            data = resp.raw.read(size_limit + 1)
            if len(data) > size_limit:
                print(f"[fetcher][WARN] Downloaded data exceeds limit ({size_limit} bytes), skipping.")
                raise ValueError("Downloaded data exceeds limit")
            # Check if data is gzipped and decompress if needed
            data = self._decompress_if_gzipped(data)
            with self._cache_lock:
                self._fetch_cache[key] = data
            return data

    def _decompress_if_gzipped(self, data: bytes) -> bytes:
        """Check if data is gzipped and decompress if needed."""
        if data.startswith(b'\x1f\x8b'):  # gzip magic number
            try:
                decompressed = gzip.decompress(data)
                print(f"[fetcher] Decompressed gzip data: {len(data)} -> {len(decompressed)} bytes")
                return decompressed
            except Exception as e:
                print(f"[fetcher][WARN] Failed to decompress gzip data: {e}")
                return data
        return data 