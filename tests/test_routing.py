from sboxmgr.export.export_manager import ExportManager
from sboxmgr.export.routing.default_router import DefaultRouter
from sboxmgr.export.routing.base_router import BaseRoutingPlugin
from sboxmgr.subscription.models import ParsedServer

class TestRouter(BaseRoutingPlugin):
    def __init__(self):
        self.last_call = None
    def generate_routes(self, servers, exclusions, user_routes, context=None):
        self.last_call = {
            'servers': servers,
            'exclusions': exclusions,
            'user_routes': user_routes,
            'context': context,
        }
        return [{"test": True}]

def test_default_router_returns_list():
    router = DefaultRouter()
    servers = []
    routes = router.generate_routes(servers, [], [], context={"mode": "default"})
    assert isinstance(routes, list)

def test_export_manager_with_test_router():
    router = TestRouter()
    servers = [ParsedServer(type="ss", address="1.2.3.4", port=1234, security=None, meta={"tag": "test"})]
    exclusions = ["5.6.7.8"]
    user_routes = [{"domain": ["example.com"], "outbound": "ss"}]
    context = {"mode": "geo", "custom": 42}
    mgr = ExportManager(routing_plugin=router)
    config = mgr.export(servers, exclusions, user_routes, context)
    assert config["route"]["rules"] == [{"test": True}]
    assert router.last_call["context"]["mode"] == "geo"
    assert router.last_call["user_routes"] == user_routes
    assert router.last_call["servers"] == servers

def test_default_router_with_servers_uses_server_tag():
    """Test that DefaultRouter creates fallback rule using server tag."""
    router = DefaultRouter()
    
    # Server with explicit tag
    servers = [ParsedServer(type="ss", address="1.2.3.4", port=1234, security=None, meta={"tag": "proxy-server"})]
    routes = router.generate_routes(servers, [], [], context={"debug_level": 0})
    
    # Should have DNS, private IPs, and fallback rules
    assert len(routes) >= 3
    
    # Check that fallback rule uses the server tag
    fallback_rule = routes[-1]  # Last rule should be the fallback
    assert fallback_rule["outbound"] == "proxy-server"

def test_default_router_with_servers_generates_tag():
    """Test that DefaultRouter generates tag when server has no explicit tag."""
    router = DefaultRouter()
    
    # Server without explicit tag
    servers = [ParsedServer(type="vmess", address="5.6.7.8", port=443, security=None, meta={})]
    routes = router.generate_routes(servers, [], [], context={"debug_level": 0})
    
    # Should have DNS, private IPs, and fallback rules
    assert len(routes) >= 3
    
    # Check that fallback rule uses generated tag
    fallback_rule = routes[-1]  # Last rule should be the fallback
    assert fallback_rule["outbound"] == "vmess-5.6.7.8"

def test_default_router_without_servers_uses_direct():
    """Test that DefaultRouter routes to direct when no servers available."""
    router = DefaultRouter()
    
    # No servers
    routes = router.generate_routes([], [], [], context={"debug_level": 0})
    
    # Should have DNS, private IPs, and direct fallback
    assert len(routes) >= 3
    
    # Check that fallback rule routes to direct
    fallback_rule = routes[-1]  # Last rule should be the fallback
    assert fallback_rule["outbound"] == "direct"

def test_default_router_complete_rule_set():
    """Test complete rule set generation with all components."""
    router = DefaultRouter()
    
    servers = [ParsedServer(type="ss", address="1.2.3.4", port=1234, security=None, meta={"tag": "proxy"})]
    exclusions = ["192.168.1.1", "example.com"]
    user_routes = [{"domain": ["google.com"], "outbound": "direct"}]
    
    routes = router.generate_routes(servers, exclusions, user_routes, context={"debug_level": 0})
    
    # Should have: DNS + Private IPs + Exclusions + User routes + Fallback
    assert len(routes) >= 5
    
    # Check DNS rule
    assert routes[0]["protocol"] == "dns"
    assert routes[0]["action"] == "hijack-dns"
    
    # Check private IPs rule
    assert routes[1]["ip_is_private"] == True
    assert routes[1]["outbound"] == "direct"
    
    # Check exclusions (IP)
    assert any("ip_cidr" in rule and "192.168.1.1/32" in rule["ip_cidr"] for rule in routes)
    
    # Check exclusions (domain)
    assert any("domain" in rule and "example.com" in rule["domain"] for rule in routes)
    
    # Check user route
    assert any("domain" in rule and "google.com" in rule["domain"] and rule["outbound"] == "direct" for rule in routes)
    
    # Check fallback
    fallback_rule = routes[-1]
    assert fallback_rule["outbound"] == "proxy" 