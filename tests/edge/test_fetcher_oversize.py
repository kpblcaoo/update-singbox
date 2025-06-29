import pytest

def test_fetcher_unsupported_protocols():
    """Edge-case: Fetcher должен явно запрещать или безопасно fallback для нестандартных схем."""
    from sboxmgr.subscription.models import SubscriptionSource
    from sboxmgr.subscription.manager import SubscriptionManager
    unsupported = [
        "ftp://example.com/file.txt",
        "data:text/plain;base64,SGVsbG8sIFdvcmxkIQ==",
        "chrome-extension://abcdefg/data.json"
    ]
    for url in unsupported:
        source = SubscriptionSource(url=url, source_type="url_base64")
        try:
            mgr = SubscriptionManager(source)
            mgr.get_servers()
            assert False, f"Fetcher must not support scheme: {url}"
        except Exception as e:
            assert "unsupported" in str(e).lower() or "not allowed" in str(e).lower() or "invalid" in str(e).lower()

def test_fetcher_unsupported_scheme_ftp():
    """Test that unsupported schemes raise ValueError."""
    from sboxmgr.subscription.fetchers.url_fetcher import URLFetcher
    from sboxmgr.subscription.models import SubscriptionSource
    src = SubscriptionSource(url="ftp://example.com/file.txt", source_type="url")
    with pytest.raises(ValueError, match="unsupported scheme: ftp"):
        URLFetcher(src)

def test_fetcher_unsupported_scheme_data():
    """Test that data URLs are not supported."""
    from sboxmgr.subscription.fetchers.url_fetcher import URLFetcher
    from sboxmgr.subscription.models import SubscriptionSource
    src = SubscriptionSource(url="data:text/plain;base64,SGVsbG8=", source_type="url")
    with pytest.raises(ValueError, match="unsupported scheme: data"):
        URLFetcher(src)

def test_fetcher_unsupported_scheme_chrome_extension():
    """Test that chrome-extension URLs are not supported."""
    from sboxmgr.subscription.fetchers.url_fetcher import URLFetcher
    from sboxmgr.subscription.models import SubscriptionSource
    src = SubscriptionSource(url="chrome-extension://id/file.txt", source_type="url")
    with pytest.raises(ValueError, match="unsupported scheme: chrome-extension"):
        URLFetcher(src) 