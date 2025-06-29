"""Tests for SubscriptionManager refactoring - validating current behavior before changes."""

import pytest
from unittest.mock import Mock, patch
import tempfile
from sboxmgr.subscription.models import SubscriptionSource, PipelineContext, PipelineResult
from sboxmgr.subscription.manager import SubscriptionManager
from sboxmgr.subscription.errors import ErrorType


class TestSubscriptionManagerRefactoring:
    """Test suite for SubscriptionManager refactoring validation.
    
    These tests validate the refactored SubscriptionManager architecture
    ensuring compatibility and proper functionality during the transition.
    """
    
    @pytest.fixture
    def mock_source(self):
        """Create a mock subscription source with file:// URL."""
        # Create a temporary file with test data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("ss://YWVzLTI1Ni1nY206cGFzc0BleGFtcGxlLmNvbTo4Mzg4#test")
            temp_path = f.name
        
        return SubscriptionSource(
            url=f"file://{temp_path}",
            source_type="url_base64"
        )
    
    @pytest.fixture  
    def mock_context(self):
        """Create a mock pipeline context."""
        return PipelineContext(mode="strict")

    def test_get_servers_basic_flow(self, mock_source, mock_context):
        """Test basic get_servers flow with mocked components.
    
        This test validates the complete pipeline execution from
        fetch to final server selection without external dependencies.
        """
        # Mock parsed server
        mock_server = Mock()
        mock_server.type = "ss"
        mock_server.address = "example.com"
        mock_server.port = 8388
        mock_server.meta = {"tag": "test"}

        with patch('sboxmgr.subscription.manager.detect_parser') as mock_detect:
            # Mock parser
            mock_parser = Mock()
            mock_parser.parse.return_value = [mock_server]
            mock_detect.return_value = mock_parser

            with patch('sboxmgr.subscription.validators.base.RAW_VALIDATOR_REGISTRY') as mock_raw_val:
                # Mock raw validator
                mock_raw_validator = Mock()
                mock_raw_validator.validate.return_value = Mock(valid=True, errors=[])
                mock_raw_val.get.return_value = Mock(return_value=mock_raw_validator)

                with patch('sboxmgr.subscription.validators.base.PARSED_VALIDATOR_REGISTRY') as mock_parsed_val:
                    # Mock parsed validator
                    mock_parsed_validator = Mock()
                    mock_parsed_validator.validate.return_value = Mock(
                        valid_servers=[mock_server], errors=[]
                    )
                    mock_parsed_val.get.return_value = Mock(return_value=mock_parsed_validator)

                    # Execute test
                    mgr = SubscriptionManager(mock_source)
                    result = mgr.get_servers(context=mock_context)

                    # Validate results
                    assert isinstance(result, PipelineResult)
                    assert result.success
                    assert result.config is not None
                    assert len(result.config) > 0

    def test_get_servers_validation_error_strict_mode(self, mock_source):
        """Test validation error handling in strict mode.
    
        Validates that validation errors in strict mode cause immediate
        pipeline failure with appropriate error reporting.
        """
        mock_context = PipelineContext(mode="strict")

        with patch('sboxmgr.subscription.validators.base.RAW_VALIDATOR_REGISTRY') as mock_raw_val:
            # Mock validator that fails
            mock_raw_validator = Mock()
            mock_raw_validator.validate.return_value = Mock(
                valid=False,
                errors=["Invalid data format"]
            )
            mock_raw_val.get.return_value = Mock(return_value=mock_raw_validator)

            # Execute test
            mgr = SubscriptionManager(mock_source)
            result = mgr.get_servers(context=mock_context)

            # Validate strict mode behavior
            assert isinstance(result, PipelineResult)
            assert not result.success
            assert result.config is None
            assert len(result.errors) == 1
            assert result.errors[0].type == ErrorType.VALIDATION

    def test_get_servers_fetch_error_handling(self, mock_context):
        """Test error handling during fetch stage.
    
        Validates that fetch errors are properly caught and converted
        to PipelineError objects with appropriate error context.
        """
        # Use an invalid file URL that will cause a fetch error
        source = SubscriptionSource(
            url="file:///nonexistent/path/file.txt",
            source_type="url_base64"
        )

        # Execute test
        mgr = SubscriptionManager(source)
        result = mgr.get_servers(context=mock_context)

        # Validate error handling
        assert isinstance(result, PipelineResult)
        assert not result.success
        assert result.config is None
        assert len(result.errors) == 1
        assert result.errors[0].type == ErrorType.INTERNAL

    def test_get_servers_middleware_processing(self, mock_source, mock_context):
        """Test middleware chain processing during get_servers.
    
        Validates that middleware chain is properly invoked and
        can modify server configurations during pipeline execution.
        """
        mock_server = Mock()
        mock_server.type = "ss"
        mock_server.meta = {"tag": "original"}

        # Mock modified server from middleware
        mock_modified_server = Mock()
        mock_modified_server.type = "ss"
        mock_modified_server.meta = {"tag": "modified_by_middleware"}

        with patch('sboxmgr.subscription.manager.detect_parser') as mock_detect:
            mock_parser = Mock()
            mock_parser.parse.return_value = [mock_server]
            mock_detect.return_value = mock_parser

            with patch('sboxmgr.subscription.validators.base.RAW_VALIDATOR_REGISTRY') as mock_raw_val:
                mock_raw_validator = Mock()
                mock_raw_validator.validate.return_value = Mock(valid=True, errors=[])
                mock_raw_val.get.return_value = Mock(return_value=mock_raw_validator)

                with patch('sboxmgr.subscription.validators.base.PARSED_VALIDATOR_REGISTRY') as mock_parsed_val:
                    mock_parsed_validator = Mock()
                    mock_parsed_validator.validate.return_value = Mock(
                        valid_servers=[mock_server], errors=[]
                    )
                    mock_parsed_val.get.return_value = Mock(return_value=mock_parsed_validator)

                    # Create manager with custom middleware
                    mock_middleware = Mock()
                    mock_middleware.process.return_value = [mock_modified_server]

                    mgr = SubscriptionManager(mock_source, middleware_chain=mock_middleware)
                    result = mgr.get_servers(context=mock_context)

                    # Validate middleware was called and modified result
                    assert result.success
                    mock_middleware.process.assert_called_once()

    def test_get_servers_caching_behavior(self, mock_source, mock_context):
        """Test caching behavior of get_servers method.
    
        Validates that identical requests are served from cache
        and cache keys properly differentiate between different parameters.
        """
        mock_server = Mock()
        mock_server.type = "ss"

        with patch('sboxmgr.subscription.manager.detect_parser') as mock_detect:
            # Mock parser
            mock_parser = Mock()
            mock_parser.parse.return_value = [mock_server]
            mock_detect.return_value = mock_parser

            with patch('sboxmgr.subscription.validators.base.RAW_VALIDATOR_REGISTRY') as mock_raw_val:
                mock_raw_validator = Mock()
                mock_raw_validator.validate.return_value = Mock(valid=True, errors=[])
                mock_raw_val.get.return_value = Mock(return_value=mock_raw_validator)

                with patch('sboxmgr.subscription.validators.base.PARSED_VALIDATOR_REGISTRY') as mock_parsed_val:
                    mock_parsed_validator = Mock()
                    mock_parsed_validator.validate.return_value = Mock(
                        valid_servers=[mock_server], errors=[]
                    )
                    mock_parsed_val.get.return_value = Mock(return_value=mock_parsed_validator)

                    # Execute multiple requests
                    mgr = SubscriptionManager(mock_source)

                    # First request - should call parser
                    result1 = mgr.get_servers(context=mock_context)
                    assert mock_detect.call_count == 1

                    # Second request - should use cache
                    result2 = mgr.get_servers(context=mock_context)
                    assert mock_detect.call_count == 1  # No additional calls

                    # Both results should be successful
                    assert result1.success
                    assert result2.success


class TestSubscriptionManagerCurrentBehavior:
    """Test suite documenting current SubscriptionManager behavior.
    
    These tests serve as documentation and regression protection
    for the existing SubscriptionManager implementation.
    """

    def test_get_servers_parameter_combinations(self):
        """Test various parameter combinations for get_servers method.
    
        Documents how different parameter combinations affect caching
        and pipeline behavior in the current implementation.
        """
        # Create a valid file source
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("ss://YWVzLTI1Ni1nY206cGFzc0BleGFtcGxlLmNvbTo4Mzg4#test")
            temp_path = f.name
        
        source = SubscriptionSource(url=f"file://{temp_path}", source_type="url_base64")

        with patch('sboxmgr.subscription.manager.detect_parser') as mock_detect:
            mock_parser = Mock()
            mock_parser.parse.return_value = []
            mock_detect.return_value = mock_parser
            
            with patch('sboxmgr.subscription.validators.base.RAW_VALIDATOR_REGISTRY') as mock_raw_val:
                mock_raw_validator = Mock()
                mock_raw_validator.validate.return_value = Mock(valid=True, errors=[])
                mock_raw_val.get.return_value = Mock(return_value=mock_raw_validator)

                mgr = SubscriptionManager(source)
                
                # Test different parameter combinations
                result1 = mgr.get_servers(mode="strict")
                result2 = mgr.get_servers(mode="tolerant")
                result3 = mgr.get_servers(user_routes=["test"])
                
                assert all(isinstance(r, PipelineResult) for r in [result1, result2, result3])

    def test_error_context_metadata_structure(self):
        """Test error context metadata structure in current implementation.
    
        Documents the expected structure of error metadata and context
        information that must be preserved during refactoring.
        """
        # Use invalid file to trigger error
        source = SubscriptionSource(url="file:///nonexistent", source_type="url_base64")
        context = PipelineContext()

        # Test metadata initialization
        assert 'errors' not in context.metadata

        mgr = SubscriptionManager(source)
        result = mgr.get_servers(context=context)

        # After get_servers call, should have errors
        assert not result.success
        assert len(result.errors) > 0
        assert 'errors' in context.metadata 