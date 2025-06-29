from sboxmgr.utils.cli_common import load_outbounds


class TestLoadOutbounds:
    """Test load_outbounds function."""
    
    def test_load_outbounds_dict_format(self):
        """Test loading outbounds from dict format."""
        json_data = {
            "outbounds": [
                {"type": "vless", "server": "example.com", "tag": "vless-1"},
                {"type": "direct", "tag": "direct"},
                {"type": "vmess", "server": "test.com", "tag": "vmess-1"},
                {"type": "unsupported", "server": "bad.com", "tag": "bad-1"}
            ]
        }
        supported_protocols = {"vless", "vmess", "trojan"}
        
        result = load_outbounds(json_data, supported_protocols)
        
        assert len(result) == 2
        assert result[0]["type"] == "vless"
        assert result[1]["type"] == "vmess"
        assert all(o["type"] in supported_protocols for o in result)
    
    def test_load_outbounds_list_format(self):
        """Test loading outbounds from list format."""
        json_data = [
            {"type": "vless", "server": "example.com", "tag": "vless-1"},
            {"type": "trojan", "server": "test.com", "tag": "trojan-1"},
            {"type": "unsupported", "server": "bad.com", "tag": "bad-1"}
        ]
        supported_protocols = {"vless", "trojan"}
        
        result = load_outbounds(json_data, supported_protocols)
        
        assert len(result) == 2
        assert result[0]["type"] == "vless"
        assert result[1]["type"] == "trojan"
    
    def test_load_outbounds_empty_data(self):
        """Test loading outbounds from empty data."""
        assert load_outbounds({}, {"vless"}) == []
        assert load_outbounds([], {"vless"}) == []
        assert load_outbounds({"outbounds": []}, {"vless"}) == []
    
    def test_load_outbounds_no_matching_protocols(self):
        """Test loading outbounds with no matching protocols."""
        json_data = {
            "outbounds": [
                {"type": "unsupported1", "tag": "bad-1"},
                {"type": "unsupported2", "tag": "bad-2"}
            ]
        }
        supported_protocols = {"vless", "vmess"}
        
        result = load_outbounds(json_data, supported_protocols)
        assert result == [] 