import pytest
from sboxmgr.subscription.exporters.singbox_exporter import singbox_export
from sboxmgr.subscription.models import ParsedServer, InboundProfile, ClientProfile
from sboxmgr.subscription.postprocessor_base import PostProcessorChain, DedupPostProcessor, BasePostProcessor
from sboxmgr.export.export_manager import ExportManager

def test_empty_servers():
    config = singbox_export([], routes=[])
    assert isinstance(config, dict)
    assert "outbounds" in config
    tags = [o["tag"] for o in config["outbounds"]]
    # Проверяем, что только стандартные outbounds (legacy special outbounds удалены в sing-box 1.11.0+)
    assert set(tags) >= {"direct"}
    # Не должно быть пользовательских (только стандартные)
    assert len(tags) == 1

def test_invalid_server_fields():
    servers = [
        ParsedServer(type=None, address=123, port="not_a_port"),
        ParsedServer(type="vmess", address="", port=-1),
    ]
    config = singbox_export(servers, routes=[])
    assert isinstance(config, dict)
    assert "outbounds" in config
    assert isinstance(config["outbounds"], list)

def test_duplicate_servers():
    server = ParsedServer(type="vmess", address="1.2.3.4", port=443, meta={"tag": "dup"})
    servers = [server, ParsedServer(**server.__dict__)]
    config = singbox_export(servers, routes=[])
    assert isinstance(config, dict)
    assert "outbounds" in config
    assert len(config["outbounds"]) >= 1

def test_too_long_values():
    long_str = "A" * 1000
    servers = [ParsedServer(type="vmess", address=long_str, port=443, meta={"tag": long_str})]
    config = singbox_export(servers, routes=[])
    assert isinstance(config, dict)
    assert "outbounds" in config
    for outbound in config["outbounds"]:
        assert len(str(outbound.get("server", ""))) <= 1000
        assert len(str(outbound.get("tag", ""))) <= 1000

def test_failtolerance_skip_unsupported_type(caplog):
    """Если среди ParsedServer есть unsupported type или неполные поля, он скипается, partial config генерируется, warning выводится."""
    servers = [
        ParsedServer(type="vmess", address="ok.com", port=443, meta={}),
        ParsedServer(type="wireguard", address="wg.com", port=51820, meta={}),
        ParsedServer(type="ss", address="ok2.com", port=8388, meta={"method": "aes-256-gcm", "password": "p"}),
    ]
    config = singbox_export(servers, routes=[])
    tags = [o["tag"] for o in config["outbounds"]]
    assert "ok.com" in tags
    assert "ok2.com" in tags
    # wireguard не должен попасть
    for outbound in config["outbounds"]:
        assert outbound["type"] != "wireguard"
    # Проверяем warning
    assert "Incomplete wireguard fields" in caplog.text

def test_export_wireguard_success(caplog):
    servers = [ParsedServer(type="wireguard", address="1.2.3.4", port=51820, private_key="priv", peer_public_key="pub", local_address=["10.0.0.2/32"], tag="wg1")]
    config = singbox_export(servers, routes=[])
    assert "wireguard" in str(config)
    assert "wg1" in str(config)
    assert "priv" in str(config)
    assert "pub" in str(config)
    assert "10.0.0.2" in str(config)
    assert "WARN" not in caplog.text

def test_export_wireguard_missing_fields(caplog):
    servers = [ParsedServer(type="wireguard", address="1.2.3.4", port=51820)]
    config = singbox_export(servers, routes=[])
    assert "wireguard" not in str(config)
    assert "Incomplete wireguard fields" in caplog.text

def test_export_hysteria2_success(caplog):
    servers = [ParsedServer(type="hysteria2", address="h.com", port=443, password="pw", tag="hyst2")]
    config = singbox_export(servers, routes=[])
    assert "hysteria2" in str(config)
    assert "h.com" in str(config)
    assert "pw" in str(config)
    assert "WARN" not in caplog.text

def test_export_tuic_success(caplog):
    servers = [ParsedServer(type="tuic", address="t.com", port=443, uuid="uuid", password="pw", tag="tuic1")]
    config = singbox_export(servers, routes=[])
    assert "tuic" in str(config)
    assert "t.com" in str(config)
    assert "uuid" in str(config)
    assert "pw" in str(config)
    assert "WARN" not in caplog.text

def test_export_shadowtls_success(caplog):
    servers = [ParsedServer(type="shadowtls", address="s.com", port=443, password="pw", version=3, tag="stls")]
    config = singbox_export(servers, routes=[])
    assert "shadowtls" in str(config)
    assert "s.com" in str(config)
    assert "pw" in str(config)
    assert "3" in str(config)
    assert "WARN" not in caplog.text

def test_export_anytls_success(caplog):
    servers = [ParsedServer(type="anytls", address="a.com", port=443, uuid="uuid", tag="anytls")]
    config = singbox_export(servers, routes=[])
    assert "anytls" in str(config)
    assert "a.com" in str(config)
    assert "uuid" in str(config)
    assert "WARN" not in caplog.text

def test_export_tor_success(caplog):
    servers = [ParsedServer(type="tor", address="127.0.0.1", port=9050, tag="tor1")]
    config = singbox_export(servers, routes=[])
    assert "tor" in str(config)
    assert "127.0.0.1" in str(config)
    assert "WARN" not in caplog.text

def test_export_ssh_success(caplog):
    servers = [ParsedServer(type="ssh", address="ssh.com", port=22, username="user", password="pw", tag="ssh1")]
    config = singbox_export(servers, routes=[])
    assert "ssh" in str(config)
    assert "ssh.com" in str(config)
    assert "user" in str(config)
    assert "pw" in str(config)
    assert "WARN" not in caplog.text

def test_postprocessor_chain_dedup_and_filter():
    # Дубликаты и порты
    servers = [
        ParsedServer(type="ss", address="1.2.3.4", port=443, meta={"tag": "A"}),
        ParsedServer(type="ss", address="1.2.3.4", port=443, meta={"tag": "A"}),
        ParsedServer(type="ss", address="2.2.2.2", port=1234, meta={"tag": "B"}),
        ParsedServer(type="ss", address="3.3.3.3", port=999, meta={"tag": "C"}),
        ParsedServer(type="ss", address="4.4.4.4", port=2000, meta={"tag": "D"}),
    ]
    chain = PostProcessorChain([DedupPostProcessor(), FilterPortPostProcessor()])
    result = chain.process(servers)
    # После dedup останется 4 сервера, после фильтра — только порты >= 1000
    ports = [s.port for s in result]
    assert 443 not in ports
    assert 999 not in ports
    assert 1234 in ports
    assert 2000 in ports
    tags = [s.meta.get("tag") for s in result]
    assert set(tags) == {"B", "D"}

class FilterPortPostProcessor(BasePostProcessor):
    def process(self, servers):
        # Удаляет все серверы с портом < 1000
        return [s for s in servers if getattr(s, 'port', 0) >= 1000]

def test_inbounds_valid_profile():
    """Тест: генерация inbounds с валидным профилем (localhost, безопасные порты)."""
    profile = ClientProfile(inbounds=[
        InboundProfile(type="socks", listen="127.0.0.1", port=10808),
        InboundProfile(type="tun", listen="127.0.0.1", port=12345, options={"stack": "system"})
    ])
    mgr = ExportManager(client_profile=profile)
    config = mgr.export([], [])
    assert "inbounds" in config
    assert config["inbounds"][0]["listen"] == "127.0.0.1"
    assert config["inbounds"][0]["port"] == 10808


def test_inbounds_invalid_bind():
    """Тест: SEC — bind-to-all (0.0.0.0) должен вызывать ошибку валидации."""
    with pytest.raises(ValueError):
        InboundProfile(type="socks", listen="0.0.0.0", port=10808)


def test_inbounds_port_conflict():
    """Тест: конфликт портов (два inbounds на одном порту) — edge-case, должен быть обработан на уровне профиля/экспортера."""
    profile = ClientProfile(inbounds=[
        InboundProfile(type="socks", listen="127.0.0.1", port=10808),
        InboundProfile(type="http", listen="127.0.0.1", port=10808)
    ])
    mgr = ExportManager(client_profile=profile)
    config = mgr.export([], [])
    ports = [inb["port"] for inb in config["inbounds"]]
    assert ports.count(10808) == 2  # Пока допускается, но edge-case зафиксирован


def test_inbounds_sec_validation():
    """Тест: SEC — порт вне диапазона должен вызывать ошибку валидации."""
    with pytest.raises(ValueError):
        InboundProfile(type="socks", listen="127.0.0.1", port=80)

def test_exporter_wireguard_missing_fields():
    """Exporter: WireGuard outbound без обязательных полей должен скипаться с warning."""
    from sboxmgr.export.export_manager import ExportManager
    from sboxmgr.subscription.models import ParsedServer
    servers = [ParsedServer(type="wireguard", address="", port=0, meta={})]
    mgr = ExportManager()
    config = mgr.export(servers, exclusions=[], user_routes=[], context=None)
    assert "outbounds" in config
    assert all(o.get("type") != "wireguard" or o.get("address") for o in config["outbounds"])

def test_exporter_tuic_invalid():
    """Exporter: tuic outbound с невалидными значениями должен скипаться с warning."""
    from sboxmgr.export.export_manager import ExportManager
    from sboxmgr.subscription.models import ParsedServer
    servers = [ParsedServer(type="tuic", address="bad", port=-1, meta={})]
    mgr = ExportManager()
    config = mgr.export(servers, exclusions=[], user_routes=[], context=None)
    assert "outbounds" in config
    assert all(o.get("type") != "tuic" or o.get("port", 0) > 0 for o in config["outbounds"])

def test_exporter_hysteria_missing_fields():
    """Exporter: hysteria outbound без обязательных полей должен скипаться с warning."""
    from sboxmgr.export.export_manager import ExportManager
    from sboxmgr.subscription.models import ParsedServer
    servers = [ParsedServer(type="hysteria", address="", port=0, meta={})]
    mgr = ExportManager()
    config = mgr.export(servers, exclusions=[], user_routes=[], context=None)
    assert "outbounds" in config
    assert all(o.get("type") != "hysteria" or o.get("address") for o in config["outbounds"])

def test_exporter_shadowtls_anytls_tor_ssh():
    """Exporter: shadowtls, anytls, tor, ssh — отсутствие обязательных полей, невалидные значения — должны скипаться с warning."""
    from sboxmgr.export.export_manager import ExportManager
    from sboxmgr.subscription.models import ParsedServer
    types = ["shadowtls", "anytls", "tor", "ssh"]
    for t in types:
        servers = [ParsedServer(type=t, address="", port=0, meta={})]
        mgr = ExportManager()
        config = mgr.export(servers, exclusions=[], user_routes=[], context=None)
        assert "outbounds" in config
        assert all(o.get("type") != t or o.get("address") for o in config["outbounds"]) 