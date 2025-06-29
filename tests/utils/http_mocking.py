"""HTTP mocking utilities for SBOXMGR tests.

This module provides standard mocking patterns for CLI tests that need to
simulate HTTP requests to subscription services.
"""

def setup_subscription_mock(monkeypatch, subscription_data=None):
    """Setup HTTP mock for subscription fetching in CLI tests.
    
    Args:
        monkeypatch: pytest monkeypatch fixture
        subscription_data (str, optional): Custom base64 subscription data.
            If None, uses default mock data with 2 servers.
    """
    if subscription_data is None:
        # Default mock data: 2 vmess servers for testing exclusions/selection
        subscription_data = """
dm1lc3M6Ly9leUpoWkdRaU9pSmpiMjUwY205c0xtTnZiU0lzSW1GcFpDSTZNQ3dpYUc5emRDSTZJbU52Ym5SeWIyeGZhRzl6ZENJc0ltbGtJam9pTVRJek5EVTJOemc1TFRGaFltTXRNVEZsWVMxaU1UUTBMVEZoTW1KaU1UUTBNVEZoWWlJc0ltNWxkQ0k2SW5keklpd2lhV1JzWlhCc1lYbGxjaUk2SWlJc0luQnZjblFpT2pRME15d2ljSE1pT2lKYlRrd3RNbDBnZG0xbGMzTXRjbVZoYkdsMGVTSXNJblI1Y0dVaU9pSmhkWFJ2SWl3aWRpSTZNaXdpYzJONUlqb2lZWFYwYnlJc0luUnNjeUk2SWlKOQp2bWVzczovL2V5SmhaR1FpT2lKamIyNTBjbTlzTWk1amIyMGlMQ0poYVdRaU9qQXNJbWhoYzNRaU9pSmpiMjUwY205c01pNWpiMjBpTENKcFpDSTZJakV5TXpRMU5qYzRPUzB4WVdKakxURXhaV0V0WWpFME5DMHhZVEppWWpFME5ERXhZV0lpTENKdVpYUWlPaUozY3lJc0ltbGtiR1Z3YkdGNVpYSWlPaUlpTENKd2IzSjBJam8wTkRNc0luQnpJam9pVzA1TUxUTmRJSFp0WlhOekxYSmxZV3hwZEhreUlpd2lkSGx3WlNJNkltRjFkRzhpTENKMklqb3lMQ0p6WTNraU9pSmhkWFJ2SWl3aWRHeHpJam9pSWlKOQ==
""".strip()
    
    class DummyRequests:
        def get(self, url, headers=None, stream=None, **kwargs):
            """Mock requests.get for subscription fetching."""
            class Resp:
                def raise_for_status(self): 
                    pass
                    
                def json(self): 
                    return {}
                    
                @property
                def raw(self):
                    class Raw:
                        def read(self, n):
                            return subscription_data.encode()
                    return Raw()
            return Resp()
    
    monkeypatch.setattr("requests.get", DummyRequests().get)


def setup_legacy_json_mock(monkeypatch, json_data=None):
    """Setup HTTP mock for legacy fetch_json() used by exclusions command.
    
    Args:
        monkeypatch: pytest monkeypatch fixture
        json_data (dict, optional): Custom JSON data to return.
            If None, uses default mock data with 2 servers.
    """
    if json_data is None:
        # Default mock JSON: 2 servers for testing exclusions
        json_data = {
            "outbounds": [
                {
                    "type": "vmess",
                    "tag": "[NL-1] vmess-reality",
                    "server": "control.com",
                    "server_port": 443,
                    "uuid": "12345678-1abc-11ea-b140-1a2bb1411ab",
                    "security": "auto",
                    "transport": {"type": "ws"}
                },
                {
                    "type": "vmess", 
                    "tag": "[NL-2] vmess-reality2",
                    "server": "control2.com",
                    "server_port": 443,
                    "uuid": "12345678-1abc-11ea-b140-1a2bb1411ab",
                    "security": "auto",
                    "transport": {"type": "ws"}
                }
            ]
        }
    
    class DummyRequests:
        def get(self, url, headers=None, stream=None, **kwargs):
            """Mock requests.get for legacy JSON fetching."""
            class Resp:
                def raise_for_status(self): 
                    pass
                    
                def json(self): 
                    return json_data
                    
                @property
                def raw(self):
                    class Raw:
                        def read(self, n):
                            return b""
                    return Raw()
            return Resp()
    
    monkeypatch.setattr("requests.get", DummyRequests().get)


def setup_version_mock(monkeypatch, version="1.11.5"):
    """Setup sing-box version detection mock.
    
    Args:
        monkeypatch: pytest monkeypatch fixture  
        version (str): Version to return from sing-box --version
    """
    
    def mock_run(*args, **kwargs):
        """Mock subprocess.run for sing-box version detection."""
        class MockResult:
            def __init__(self):
                self.stdout = f"sing-box version {version}\n"
                self.returncode = 0
        return MockResult()
    
    monkeypatch.setattr("subprocess.run", mock_run)


def setup_full_cli_mock(monkeypatch, subscription_data=None, version="1.11.5"):
    """Setup complete mocking for CLI tests.
    
    Combines HTTP mocking and version mocking for full CLI test isolation.
    
    Args:
        monkeypatch: pytest monkeypatch fixture
        subscription_data (str, optional): Custom subscription data
        version (str): sing-box version to mock
    """
    setup_subscription_mock(monkeypatch, subscription_data)
    setup_version_mock(monkeypatch, version)


def setup_legacy_cli_mock(monkeypatch, json_data=None, version="1.11.5"):
    """Setup complete mocking for legacy CLI tests (exclusions command).
    
    Uses JSON mocking instead of subscription mocking for old architecture.
    
    Args:
        monkeypatch: pytest monkeypatch fixture
        json_data (dict, optional): Custom JSON data
        version (str): sing-box version to mock
    """
    setup_legacy_json_mock(monkeypatch, json_data)
    setup_version_mock(monkeypatch, version)


def setup_universal_cli_mock(monkeypatch, json_data=None, subscription_data=None, version="1.11.5"):
    """Setup universal mocking for tests that use both legacy and new CLI commands.
    
    This mock supports both:
    - Legacy commands (exclusions) that use fetch_json() 
    - New commands (run, dry-run, list-servers) that use SubscriptionManager
    
    Args:
        monkeypatch: pytest monkeypatch fixture
        json_data (dict, optional): Custom JSON data for legacy commands
        subscription_data (str, optional): Custom subscription data for new commands  
        version (str): sing-box version to mock
    """
    if json_data is None:
        # Default mock JSON: 2 servers for testing exclusions
        json_data = {
            "outbounds": [
                {
                    "type": "vmess",
                    "tag": "[NL-1] vmess-reality",
                    "server": "control.com",
                    "server_port": 443,
                    "uuid": "12345678-1abc-11ea-b140-1a2bb1411ab",
                    "security": "auto",
                    "transport": {"type": "ws"}
                },
                {
                    "type": "vmess", 
                    "tag": "[NL-2] vmess-reality2",
                    "server": "control2.com",
                    "server_port": 443,
                    "uuid": "12345678-1abc-11ea-b140-1a2bb1411ab",
                    "security": "auto",
                    "transport": {"type": "ws"}
                }
            ]
        }
    
    if subscription_data is None:
        # Default mock data: 2 vmess servers for testing exclusions/selection
        subscription_data = """
dm1lc3M6Ly9leUpoWkdRaU9pSmpiMjUwY205c0xtTnZiU0lzSW1GcFpDSTZNQ3dpYUc5emRDSTZJbU52Ym5SeWIyeGZhRzl6ZENJc0ltbGtJam9pTVRJek5EVTJOemc1TFRGaFltTXRNVEZsWVMxaU1UUTBMVEZoTW1KaU1UUTBNVEZoWWlJc0ltNWxkQ0k2SW5keklpd2lhV1JzWlhCc1lYbGxjaUk2SWlJc0luQnZjblFpT2pRME15d2ljSE1pT2lKYlRrd3RNbDBnZG0xbGMzTXRjbVZoYkdsMGVTSXNJblI1Y0dVaU9pSmhkWFJ2SWl3aWRpSTZNaXdpYzJONUlqb2lZWFYwYnlJc0luUnNjeUk2SWlKOQp2bWVzczovL2V5SmhaR1FpT2lKamIyNTBjbTlzTWk1amIyMGlMQ0poYVdRaU9qQXNJbWhoYzNRaU9pSmpiMjUwY205c01pNWpiMjBpTENKcFpDSTZJakV5TXpRMU5qYzRPUzB4WVdKakxURXhaV0V0WWpFME5DMHhZVEppWWpFME5ERXhZV0lpTENKdVpYUWlPaUozY3lJc0ltbGtiR1Z3YkdGNVpYSWlPaUlpTENKd2IzSjBJam8wTkRNc0luQnpJam9pVzA1TUxUTmRJSFp0WlhOekxYSmxZV3hwZEhreUlpd2lkSGx3WlNJNkltRjFkRzhpTENKMklqb3lMQ0p6WTNraU9pSmhkWFJ2SWl3aWRHeHpJam9pSWlKOQ==
""".strip()
    
    class UniversalDummyRequests:
        def get(self, url, headers=None, stream=None, **kwargs):
            """Mock requests.get that supports both JSON and raw subscription data."""
            class Resp:
                def raise_for_status(self): 
                    pass
                    
                def json(self): 
                    # Return JSON data for legacy commands
                    return json_data
                    
                @property
                def raw(self):
                    class Raw:
                        def read(self, n):
                            # Return subscription data for new commands
                            return subscription_data.encode()
                    return Raw()
            return Resp()
    
    monkeypatch.setattr("requests.get", UniversalDummyRequests().get)
    setup_version_mock(monkeypatch, version) 