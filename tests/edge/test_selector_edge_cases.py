from sboxmgr.subscription.base_selector import DefaultSelector
from sboxmgr.subscription.models import ParsedServer

def test_empty_servers():
    selector = DefaultSelector()
    result = selector.select([])
    assert isinstance(result, list)
    assert result == []

def test_unsupported_mode():
    selector = DefaultSelector()
    servers = [ParsedServer(type="vmess", address="1.2.3.4", port=443)]
    # DefaultSelector не выбрасывает ошибку на unsupported mode, просто игнорирует
    result = selector.select(servers, mode="unsupported")
    assert isinstance(result, list)
    assert len(result) == 1

def test_wildcard_and_exclusions():
    selector = DefaultSelector()
    servers = [
        ParsedServer(type="vmess", address="1.2.3.4", port=443, meta={"tag": "A"}),
        ParsedServer(type="vmess", address="2.2.2.2", port=443, meta={"tag": "B"}),
    ]
    # user_routes = ["*"] (все), exclusions = ["A"] (исключить A)
    result = selector.select(servers, user_routes=["*"], exclusions=["A"])
    tags = [s.meta.get("tag") for s in result]
    assert "A" not in tags
    assert "B" in tags

def test_intersecting_user_routes_exclusions():
    selector = DefaultSelector()
    servers = [
        ParsedServer(type="vmess", address="1.2.3.4", port=443, meta={"tag": "A"}),
        ParsedServer(type="vmess", address="2.2.2.2", port=443, meta={"tag": "B"}),
    ]
    # user_routes = ["A"], exclusions = ["A"] (пересечение)
    result = selector.select(servers, user_routes=["A"], exclusions=["A"])
    tags = [s.meta.get("tag") for s in result]
    assert "A" not in tags
    assert "B" not in tags

def test_custom_selector_in_subscription_manager():
    from sboxmgr.subscription.manager import SubscriptionManager
    from sboxmgr.subscription.models import SubscriptionSource, ParsedServer
    from sboxmgr.subscription.base_selector import BaseSelector
    class OnlyTagBSelector(BaseSelector):
        def select(self, servers, user_routes=None, exclusions=None, mode=None):
            return [s for s in servers if getattr(s, 'meta', {}).get('tag') == 'B']
    # Подготовим SubscriptionManager с кастомным selector
    source = SubscriptionSource(url="file://dummy_selector_test", source_type="url_base64")  # уникальный URL
    mgr = SubscriptionManager(source)
    mgr.selector = OnlyTagBSelector()
    # Очищаем кеш
    mgr._get_servers_cache.clear()
    # Мокаем fetcher и parser
    class DummyFetcher:
        def __init__(self, source):
            self.source = source
        def fetch(self):
            return b'test_selector_data'
    mgr.fetcher = DummyFetcher(source)
    mgr.detect_parser = lambda raw, t: type('P', (), { 'parse': lambda self, raw: [
        ParsedServer(type="ss", address="1.2.3.4", port=443, meta={"tag": "A"}),
        ParsedServer(type="ss", address="2.2.2.2", port=1234, meta={"tag": "B"}),
        ParsedServer(type="ss", address="3.3.3.3", port=2000, meta={"tag": "C"}),
    ] })()
    result = mgr.get_servers(force_reload=True)  # принудительно обновляем кеш
    tags = [s.meta.get("tag") for s in result.config]
    assert tags == ["B"] 