from sboxmgr.subscription.postprocessor_base import DedupPostProcessor, PostProcessorChain
from sboxmgr.subscription.models import ParsedServer, PipelineContext


def _server(tag: str):
    return ParsedServer(type="vmess", address="example.com", port=443, meta={"tag": tag})


class CustomThreeParamPostProcessor:
    """Custom postprocessor with 3 parameters but no context parameter."""
    
    def process(self, servers, extra_param=None, another_param=None):
        """Process with custom parameters, not context."""
        return servers


def test_postprocessor_chain_dedup():
    servers = [_server("a"), _server("a"), _server("b")]
    chain = PostProcessorChain([DedupPostProcessor()])

    ctx = PipelineContext()

    # Call with context
    processed_with_ctx = chain.process(list(servers), ctx)
    assert len(processed_with_ctx) == 2
    # Order preserved first occurrence
    assert processed_with_ctx[0].meta["tag"] == "a"

    # Call without context (backward-compat)
    processed_no_ctx = chain.process(list(servers))
    assert len(processed_no_ctx) == 2


def test_postprocessor_chain_custom_three_param():
    """Test that custom postprocessors with 3 params but no context work correctly."""
    servers = [_server("a"), _server("b")]
    custom_processor = CustomThreeParamPostProcessor()
    chain = PostProcessorChain([custom_processor])
    
    # Should not raise TypeError - context should be ignored
    result = chain.process(list(servers), PipelineContext())
    assert len(result) == 2 