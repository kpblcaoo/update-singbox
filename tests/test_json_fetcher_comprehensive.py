"""Comprehensive tests for JSONFetcher class to kill mutations."""

import pytest
import requests
from unittest.mock import patch, mock_open, Mock
from sboxmgr.subscription.fetchers.json_fetcher import JSONFetcher
from sboxmgr.subscription.models import SubscriptionSource


class TestJSONFetcherComprehensive:
    """Comprehensive tests for JSONFetcher to kill all mutations."""

    def setup_method(self):
        """Setup for each test method."""
        # Clear cache before each test
        JSONFetcher._fetch_cache.clear()

    def test_init_and_registration(self):
        """Test JSONFetcher initialization and registry."""
        source = SubscriptionSource(url="https://example.com/config.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        assert fetcher.source == source
        assert hasattr(fetcher, '_cache_lock')
        assert hasattr(fetcher, '_fetch_cache')
        assert isinstance(fetcher._fetch_cache, dict)
        # Test that _cache_lock has lock methods
        assert hasattr(fetcher._cache_lock, '__enter__')
        assert hasattr(fetcher._cache_lock, '__exit__')

    def test_cache_key_generation(self):
        """Test cache key generation with different parameters."""
        source1 = SubscriptionSource(url="https://example.com", source_type="url_json")
        source2 = SubscriptionSource(url="https://example.com", source_type="url_json")
        source2.user_agent = "Custom-Agent"
        source3 = SubscriptionSource(url="https://example.com", source_type="url_json")
        source3.headers = {"Custom": "Header"}
        
        fetcher1 = JSONFetcher(source1)
        fetcher2 = JSONFetcher(source2)
        fetcher3 = JSONFetcher(source3)
        
        # Test key generation (accessing internal method through fetch logic)
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # Different sources should generate different cache keys
            fetcher1.fetch()
            fetcher2.fetch()
            fetcher3.fetch()
            
            # Cache should have 3 different entries
            assert len(JSONFetcher._fetch_cache) == 3

    def test_force_reload_true_clears_cache(self):
        """Test that force_reload=True clears cache for specific key."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test data"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # First fetch
            result1 = fetcher.fetch()
            assert result1 == b"test data"
            assert len(JSONFetcher._fetch_cache) == 1
            
            # Force reload should clear cache and make new request
            mock_response.iter_content.return_value = [b"new data"]
            result3 = fetcher.fetch(force_reload=True)
            assert result3 == b"new data"
            assert mock_get.call_count == 2  # Now two HTTP calls

    def test_force_reload_false_uses_cache(self):
        """Test that force_reload=False uses cache when available."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"cached data"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # First fetch
            result1 = fetcher.fetch(force_reload=False)
            assert result1 == b"cached data"
            
            # Second fetch with force_reload=False should use cache
            result2 = fetcher.fetch(force_reload=False)
            assert result2 == b"cached data"
            assert mock_get.call_count == 1  # Only one HTTP call

    def test_cache_hit_returns_cached_data(self):
        """Test that cache hit returns cached data without HTTP request."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        # Pre-populate cache
        key = (source.url, None, "None")
        JSONFetcher._fetch_cache[key] = b"cached content"
        
        with patch('requests.get') as mock_get:
            result = fetcher.fetch()
            assert result == b"cached content"
            mock_get.assert_not_called()  # No HTTP request should be made

    def test_file_url_startswith_true(self):
        """Test file:// URL handling - startswith returns True."""
        source = SubscriptionSource(url="file:///tmp/test.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        test_data = b'{"test": "file data"}'
        
        with patch("builtins.open", mock_open(read_data=test_data)) as mock_file:
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                result = fetcher.fetch()
                
                assert result == test_data
                mock_file.assert_called_once_with("/tmp/test.json", "rb")

    def test_file_url_replace_logic(self):
        """Test file:// URL replacement logic."""
        source = SubscriptionSource(url="file://relative/path/test.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch("builtins.open", mock_open(read_data=b"test")) as mock_file:
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                fetcher.fetch()
                
                # Should replace "file://" with empty string once
                mock_file.assert_called_once_with("relative/path/test.json", "rb")

    def test_file_size_limit_exceeded(self):
        """Test file size limit exceeded error."""
        source = SubscriptionSource(url="file:///tmp/large.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        large_data = b"x" * 1001  # 1001 bytes
        
        with patch("builtins.open", mock_open(read_data=large_data)):
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                with pytest.raises(ValueError, match="File size exceeds limit"):
                    fetcher.fetch()

    def test_file_size_limit_boundary_at_limit(self):
        """Test file size exactly at limit passes."""
        source = SubscriptionSource(url="file:///tmp/test.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        # Test exactly at limit
        exact_data = b"x" * 1000  # Exactly 1000 bytes
        with patch("builtins.open", mock_open(read_data=exact_data)):
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                result = fetcher.fetch()
                assert result == exact_data

    def test_file_size_limit_boundary_over_limit(self):
        """Test file size one byte over limit fails."""
        source = SubscriptionSource(url="file:///tmp/test.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        # Test one byte over limit
        over_data = b"x" * 1001  # 1001 bytes
        with patch("builtins.open", mock_open(read_data=over_data)):
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                with pytest.raises(ValueError, match="File size exceeds limit"):
                    fetcher.fetch()

    def test_http_url_startswith_false(self):
        """Test HTTP URL handling - startswith file:// returns False."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        # This tests the else condition
        assert source.url.startswith("file://") is False
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetcher.fetch()
            assert result == b"test"

    def test_http_headers_none(self):
        """Test HTTP request with None headers."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        source.headers = None
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            fetcher.fetch()
            
            # Should create empty dict when headers is None
            call_args = mock_get.call_args
            assert call_args[1]['headers'] == {"User-Agent": "ClashMeta/1.0"}

    def test_http_headers_empty_dict(self):
        """Test HTTP request with empty headers dict."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        source.headers = {}
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            fetcher.fetch()
            
            call_args = mock_get.call_args
            assert call_args[1]['headers'] == {"User-Agent": "ClashMeta/1.0"}

    def test_user_agent_none_uses_default(self):
        """Test user agent when None uses default."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        source.user_agent = None
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            fetcher.fetch()
            
            call_args = mock_get.call_args
            assert call_args[1]['headers']['User-Agent'] == "ClashMeta/1.0"

    def test_user_agent_empty_string_no_header(self):
        """Test user agent when empty string doesn't add header."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        source.user_agent = ""
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            fetcher.fetch()
            
            call_args = mock_get.call_args
            # Empty string should not add User-Agent header
            assert "User-Agent" not in call_args[1]['headers']

    def test_user_agent_not_empty_adds_header(self):
        """Test non-empty user agent adds header."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        source.user_agent = "Custom-Agent/1.0"
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            fetcher.fetch()
            
            call_args = mock_get.call_args
            assert call_args[1]['headers']['User-Agent'] == "Custom-Agent/1.0"

    def test_http_request_parameters(self):
        """Test HTTP request parameters are correct."""
        source = SubscriptionSource(url="https://example.com/data.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            fetcher.fetch()
            
            mock_get.assert_called_once_with(
                "https://example.com/data.json",
                headers={"User-Agent": "ClashMeta/1.0"},
                stream=True,
                timeout=30
            )

    def test_raise_for_status_called(self):
        """Test that raise_for_status is called."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            fetcher.fetch()
            
            mock_response.raise_for_status.assert_called_once()

    def test_raise_for_status_exception_propagates(self):
        """Test that raise_for_status exceptions propagate."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
            mock_get.return_value = mock_response
            
            with pytest.raises(requests.HTTPError):
                fetcher.fetch()

    def test_iter_content_chunk_size_8192(self):
        """Test iter_content called with chunk_size=8192."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetcher.fetch()
            
            assert result == b"chunk1chunk2"
            mock_response.iter_content.assert_called_once_with(chunk_size=8192)

    def test_chunk_size_accumulation(self):
        """Test chunk size accumulation logic."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            # First chunk 500 bytes, second chunk 600 bytes = 1100 total
            mock_response.iter_content.return_value = [b"x" * 500, b"x" * 600]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                with pytest.raises(ValueError, match="Downloaded data exceeds limit"):
                    fetcher.fetch()

    def test_download_size_at_limit_passes(self):
        """Test download size exactly at limit passes."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"x" * 1000]  # Exactly 1000 bytes
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                result = fetcher.fetch()
                assert result == b"x" * 1000

    def test_download_size_over_limit_fails(self):
        """Test download size over limit fails."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"x" * 1001]  # 1001 bytes
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                with pytest.raises(ValueError, match="Downloaded data exceeds limit"):
                    fetcher.fetch()

    def test_data_accumulation_multiple_chunks(self):
        """Test data accumulation with multiple chunks."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"part1", b"part2", b"part3"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetcher.fetch()
            
            assert result == b"part1part2part3"

    def test_cache_storage_after_http_success(self):
        """Test cache storage after successful HTTP fetch."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"cached_data"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetcher.fetch()
            
            assert result == b"cached_data"
            assert len(JSONFetcher._fetch_cache) == 1
            
            # Second call should use cache
            result2 = fetcher.fetch()
            assert result2 == b"cached_data"
            assert mock_get.call_count == 1  # Still only one HTTP call

    def test_cache_storage_after_file_success(self):
        """Test cache storage after successful file fetch."""
        source = SubscriptionSource(url="file:///tmp/test.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        test_data = b"file_cached_data"
        
        with patch("builtins.open", mock_open(read_data=test_data)):
            with patch.object(fetcher, '_get_size_limit', return_value=1000):
                result = fetcher.fetch()
                
                assert result == test_data
                assert len(JSONFetcher._fetch_cache) == 1
                
                # Second call should use cache
                result2 = fetcher.fetch()
                assert result2 == test_data

    def test_print_user_agent_with_value(self):
        """Test print statement with actual User-Agent value."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        source.user_agent = "Test-Agent"
        fetcher = JSONFetcher(source)
        
        with patch('builtins.print') as mock_print:
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.iter_content.return_value = [b"test"]
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                
                fetcher.fetch()
                
                mock_print.assert_called_with("[fetcher] Using User-Agent: Test-Agent")

    def test_print_user_agent_none_display(self):
        """Test print statement with [none] when User-Agent missing."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        source.user_agent = ""  # Empty string, so no User-Agent header
        fetcher = JSONFetcher(source)
        
        with patch('builtins.print') as mock_print:
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.iter_content.return_value = [b"test"]
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                
                fetcher.fetch()
                
                mock_print.assert_called_with("[fetcher] Using User-Agent: [none]")

    def test_file_size_warning_print(self):
        """Test file size warning print statement."""
        source = SubscriptionSource(url="file:///tmp/large.json", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        large_data = b"x" * 1001
        
        with patch('builtins.print') as mock_print:
            with patch("builtins.open", mock_open(read_data=large_data)):
                with patch.object(fetcher, '_get_size_limit', return_value=1000):
                    with pytest.raises(ValueError):
                        fetcher.fetch()
                    
                    mock_print.assert_called_with("[fetcher][WARN] File size exceeds limit (1000 bytes), skipping.")

    def test_download_size_warning_print(self):
        """Test download size warning print statement."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('builtins.print') as mock_print:
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.iter_content.return_value = [b"x" * 1001]
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                
                with patch.object(fetcher, '_get_size_limit', return_value=1000):
                    with pytest.raises(ValueError):
                        fetcher.fetch()
                    
                    mock_print.assert_called_with("[fetcher][WARN] Downloaded data exceeds limit (1000 bytes), skipping.")

    def test_getattr_default_values(self):
        """Test getattr with default None values."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        # Test getattr behavior with missing attributes
        assert getattr(source, 'user_agent', None) is None
        assert getattr(source, 'headers', None) is None
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            fetcher.fetch()
            
            call_args = mock_get.call_args
            assert call_args[1]['headers'] == {"User-Agent": "ClashMeta/1.0"}

    def test_cache_key_str_conversion(self):
        """Test str() conversion in cache key generation."""
        source1 = SubscriptionSource(url="https://example.com", source_type="url_json")
        source1.headers = {"key": "value"}
        
        source2 = SubscriptionSource(url="https://example.com", source_type="url_json")
        source2.headers = None
        
        fetcher1 = JSONFetcher(source1)
        fetcher2 = JSONFetcher(source2)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # Both should create different cache entries
            fetcher1.fetch()
            fetcher2.fetch()
            
            assert len(JSONFetcher._fetch_cache) == 2

    def test_empty_chunk_handling(self):
        """Test handling of empty chunks in iteration."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"", b"data", b"", b"more"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = fetcher.fetch()
            
            assert result == b"datamore"

    def test_cache_thread_lock_usage(self):
        """Test that cache operations use thread lock."""
        source = SubscriptionSource(url="https://example.com", source_type="url_json")
        fetcher = JSONFetcher(source)
        
        # Test that the lock is used by checking cache behavior
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test"]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # First fetch should populate cache
            result1 = fetcher.fetch()
            assert result1 == b"test"
            assert len(JSONFetcher._fetch_cache) == 1
            
            # Second fetch should use cache (no additional HTTP call)
            result2 = fetcher.fetch()
            assert result2 == b"test"
            assert mock_get.call_count == 1  # Only one HTTP call
            
            # Test that lock attributes exist (indicating thread safety implementation)
            assert hasattr(JSONFetcher._cache_lock, '__enter__')
            assert hasattr(JSONFetcher._cache_lock, '__exit__') 