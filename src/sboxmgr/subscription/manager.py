"""Subscription management and orchestration.

This module provides the main SubscriptionManager class that orchestrates
the entire subscription processing pipeline from fetching to export. It
coordinates fetchers, parsers, validators, postprocessors, and exporters
to provide a unified subscription processing interface.
"""

from .models import SubscriptionSource, PipelineContext, PipelineResult
from .registry import get_plugin, load_entry_points
from .fetchers import *  # noqa: F401, импортируем fetcher-плагины для регистрации

from typing import Optional, Any, Dict, Tuple, List, Literal, Protocol
from sboxmgr.export.export_manager import ExportManager
from .base_selector import DefaultSelector
from .postprocessor_base import DedupPostProcessor, PostProcessorChain
from .errors import PipelineError, ErrorType
from datetime import datetime, timezone
from .middleware_base import MiddlewareChain

import threading

class ParserProtocol(Protocol):
    """Protocol for parser objects that can parse subscription data."""
    
    def parse(self, raw: bytes) -> List[Any]:
        """Parse raw subscription data into server configurations."""
        ...

def detect_parser(raw: bytes, source_type: str) -> Optional[ParserProtocol]:
    """Auto-detect appropriate parser based on data content.
    
    Args:
        raw: Raw subscription data bytes.
        source_type: Subscription source type hint.
        
    Returns:
        Parser instance or None if detection fails.
    """
    # Декодируем данные
    text = raw.decode('utf-8', errors='ignore')
    # 1. Пробуем JSON (SingBox)
    try:
        from .parsers.singbox_parser import SingBoxParser
        parser = SingBoxParser()
        data = parser._strip_comments_and_validate(text)[0]
        import json
        json.loads(data)
        return parser
    except Exception as e:
        import logging
        logging.debug(f"JSON parser detection failed: {e}")
    # 2. Пробуем Clash YAML
    if text.startswith(("mixed-port:", "proxies:", "proxy-groups:", "proxy-providers:")) or 'proxies:' in text:
        from .parsers.clash_parser import ClashParser
        return ClashParser()
    # 3. Пробуем base64 (если строка похожа на base64)
    import base64
    import re
    b64_re = re.compile(r'^[A-Za-z0-9+/=\s]+$')
    if b64_re.match(text) and len(text.strip()) > 100:
        try:
            decoded = base64.b64decode(text.strip() + '=' * (-len(text.strip()) % 4))
            decoded_text = decoded.decode('utf-8', errors='ignore')
            if any(proto in decoded_text for proto in ("vless://", "vmess://", "trojan://", "ss://")):
                from .parsers.base64_parser import Base64Parser
                return Base64Parser()
        except Exception as e:
            import logging
            logging.debug(f"Base64 parser detection failed: {e}")
    # 4. Пробуем plain URI list
    lines = text.splitlines()
    if any(line.strip().startswith(("vless://", "vmess://", "trojan://", "ss://")) for line in lines):
        from .parsers.uri_list_parser import URIListParser
        return URIListParser()
    # fallback
    from .parsers.base64_parser import Base64Parser
    return Base64Parser()

class SubscriptionManager:
    """Manages subscription data processing pipeline.
    
    This class orchestrates the complete subscription processing workflow
    including fetching, validation, parsing, middleware processing, and
    server selection. It provides a unified interface for handling various
    subscription formats and sources with comprehensive error handling
    and caching support.
    
    The pipeline stages are:
    1. Fetch raw data from source
    2. Validate raw data
    3. Parse into server configurations  
    4. Apply middleware transformations
    5. Post-process and deduplicate
    6. Select servers based on criteria
    
    Attributes:
        fetcher: Plugin for fetching subscription data.
        postprocessor: Chain of post-processing plugins.
        middleware_chain: Chain of middleware plugins.
        selector: Server selection strategy.
        detect_parser: Function for auto-detecting parsers.
    """
    
    _cache_lock = threading.Lock()
    _get_servers_cache: Dict[Tuple, Any] = {}

    def __init__(self, source: SubscriptionSource, detect_parser=None, postprocessor_chain=None, middleware_chain=None):
        """Initialize subscription manager with configuration.

        Args:
            source: Subscription source configuration.
            detect_parser: Optional custom parser detection function.
            postprocessor_chain: Optional custom post-processor chain.
            middleware_chain: Optional custom middleware chain.
            
        Raises:
            ValueError: If source_type is unknown or unsupported.
        """
        load_entry_points()  # Подгружаем entry points, если есть
        fetcher_cls = get_plugin(source.source_type)
        if not fetcher_cls:
            # Fallback: попытка автоопределения типа (по расширению, mime и т.д.)
            # Пока просто ошибка
            raise ValueError(f"Unknown source_type: {source.source_type}")
        self.fetcher = fetcher_cls(source)
        if postprocessor_chain is not None:
            self.postprocessor = postprocessor_chain
        else:
            self.postprocessor = PostProcessorChain([DedupPostProcessor()])
        if middleware_chain is not None:
            self.middleware_chain = middleware_chain
        else:
            self.middleware_chain = MiddlewareChain([])
        self.selector = DefaultSelector()
        if detect_parser is None:
            from .manager import detect_parser as default_detect_parser
            self.detect_parser = default_detect_parser
        else:
            self.detect_parser = detect_parser

    def _create_cache_key(self, mode: str, context: PipelineContext) -> tuple:
        """Create cache key for get_servers results.
        
        Generates a unique cache key based on subscription source parameters
        and execution context to ensure proper cache differentiation.
        
        Args:
            mode: Pipeline execution mode.
            context: Pipeline execution context.
            
        Returns:
            Tuple representing the unique cache key.
        """
        return (
            str(self.fetcher.source.url),
            getattr(self.fetcher.source, 'user_agent', None),
            str(getattr(self.fetcher.source, 'headers', None)),
            str(getattr(context, 'tag_filters', None)),
            str(mode),
        )
    
    def _create_pipeline_error(self, error_type: ErrorType, stage: str, message: str, context_data: dict = None) -> PipelineError:
        """Create standardized pipeline error.
        
        Centralizes pipeline error creation with consistent structure
        and timestamp handling.
        
        Args:
            error_type: Type of error that occurred.
            stage: Pipeline stage where error occurred.
            message: Human-readable error description.
            context_data: Optional additional context information.
            
        Returns:
            Formatted PipelineError object.
        """
        return PipelineError(
            type=error_type,
            stage=stage,
            message=message,
            context=context_data or {},
            timestamp=datetime.now(timezone.utc)
        )
    
    def _fetch_and_validate_raw(self, context: PipelineContext) -> tuple[bytes, bool]:
        """Fetch and validate raw subscription data.
        
        Handles the initial data fetching and raw validation stages
        of the subscription processing pipeline.
        
        Args:
            context: Pipeline execution context for logging and error tracking.
            
        Returns:
            Tuple of (raw_data, success_flag). If success_flag is False,
            appropriate errors will be added to context.metadata['errors'].
        """
        try:
            # Логируем User-Agent на уровне 1
            debug_level = getattr(context, 'debug_level', 0)
            if debug_level >= 1:
                ua = getattr(self.fetcher.source, 'user_agent', None)
                if ua:
                    print(f"[fetcher] Using User-Agent: {ua}")
                else:
                    print("[fetcher] Using User-Agent: [default]")
            
            raw = self.fetcher.fetch()
            
            # Отладочные print в зависимости от debug_level
            if debug_level >= 2:
                print(f"[debug] Fetched {len(raw)} bytes. First 200 bytes: {raw[:200]!r}")
            
            # Raw validation
            from .validators.base import RAW_VALIDATOR_REGISTRY
            validator_cls = RAW_VALIDATOR_REGISTRY.get("noop")
            validator = validator_cls()
            result = validator.validate(raw, context)
            
            if not result.valid:
                err = self._create_pipeline_error(
                    ErrorType.VALIDATION,
                    "raw_validate",
                    "; ".join(result.errors),
                    {"source_type": self.fetcher.source.source_type}
                )
                context.metadata['errors'].append(err)
                return raw, False
            
            return raw, True
            
        except Exception as e:
            err = self._create_pipeline_error(
                ErrorType.INTERNAL,
                "fetch_and_validate",
                str(e)
            )
            context.metadata['errors'].append(err)
            return b"", False
    
    def _parse_servers(self, raw_data: bytes, context: PipelineContext) -> tuple[list, bool]:
        """Parse raw data into server configurations.
        
        Handles parser detection and server parsing with comprehensive
        error handling and debug logging.
        
        Args:
            raw_data: Raw subscription data to parse.
            context: Pipeline execution context.
            
        Returns:
            Tuple of (servers_list, success_flag). If success_flag is False,
            appropriate errors will be added to context.metadata['errors'].
        """
        try:
            debug_level = getattr(context, 'debug_level', 0)
            
            # Parser detection
            parser = self.detect_parser(raw_data, self.fetcher.source.source_type)
            if debug_level >= 2:
                print(f"[debug] Selected parser: {getattr(parser, '__class__', type(parser)).__name__}")
            
            if not parser:
                err = self._create_pipeline_error(
                    ErrorType.PARSE,
                    "detect_parser",
                    "Could not detect parser for subscription data",
                    {"source_type": self.fetcher.source.source_type}
                )
                context.metadata['errors'].append(err)
                return [], False
            
            # Parse servers
            servers = parser.parse(raw_data)
            if debug_level >= 1:
                print(f"[info] Parsed {len(servers)} servers from subscription")
            
            return servers, True
            
        except Exception as e:
            err = self._create_pipeline_error(
                ErrorType.PARSE,
                "parse_servers",
                str(e),
                {"source_type": self.fetcher.source.source_type}
            )
            context.metadata['errors'].append(err)
            return [], False
    
    def _validate_parsed_servers(self, servers: list, context: PipelineContext) -> tuple[list, bool]:
        """Validate parsed server configurations.
        
        Applies parsed validation rules to ensure server configurations
        meet minimum requirements for further processing.
        
        Args:
            servers: List of parsed server objects to validate.
            context: Pipeline execution context.
            
        Returns:
            Tuple of (validated_servers, success_flag). If success_flag is False,
            appropriate errors will be added to context.metadata['errors'].
        """
        try:
            debug_level = getattr(context, 'debug_level', 0)
            
            # Parsed validation
            from .validators.base import PARSED_VALIDATOR_REGISTRY
            parsed_validator_cls = PARSED_VALIDATOR_REGISTRY.get("required_fields")
            if not parsed_validator_cls:
                return servers, True  # No validator available
            
            parsed_validator = parsed_validator_cls()
            parsed_result = parsed_validator.validate(servers, context)
            
            if debug_level >= 2:
                print(f"[DEBUG] ParsedValidator valid_servers: {getattr(parsed_result, 'valid_servers', None)} errors: {parsed_result.errors}")
            
            # В strict режиме возвращаем все сервера (включая невалидные) с ошибками
            # В tolerant режиме возвращаем только валидные сервера
            if context.mode == 'strict':
                validated_servers = servers  # Возвращаем все сервера
                # В strict режиме при наличии серверов всегда success=True
                if servers:
                    success = True
                else:
                    success = False
            else:
                validated_servers = getattr(parsed_result, 'valid_servers', servers)
                success = bool(validated_servers)
            
            if debug_level >= 2:
                print(f"[DEBUG] servers after validation: {validated_servers}")
            
            if not validated_servers:
                err = self._create_pipeline_error(
                    ErrorType.VALIDATION,
                    "parsed_validate",
                    "; ".join(parsed_result.errors),
                    {"source_type": self.fetcher.source.source_type}
                )
                context.metadata['errors'].append(err)
                return [], False
            
            if parsed_result.errors:
                err = self._create_pipeline_error(
                    ErrorType.VALIDATION,
                    "parsed_validate",
                    "; ".join(parsed_result.errors),
                    {"source_type": self.fetcher.source.source_type}
                )
                context.metadata['errors'].append(err)
            
            return validated_servers, success
            
        except Exception as e:
            err = self._create_pipeline_error(
                ErrorType.VALIDATION,
                "validate_parsed_servers",
                str(e),
                {"source_type": self.fetcher.source.source_type}
            )
            context.metadata['errors'].append(err)
            return servers, False
    
    def _process_middleware(self, servers: list, context: PipelineContext) -> tuple[list, bool]:
        """Process servers through middleware chain.
        
        Applies middleware transformations to server configurations
        with comprehensive error handling.
        
        Args:
            servers: List of server objects to process.
            context: Pipeline execution context.
            
        Returns:
            Tuple of (processed_servers, success_flag). If success_flag is False,
            appropriate errors will be added to context.metadata['errors'].
        """
        try:
            debug_level = getattr(context, 'debug_level', 0)
            
            processed_servers = self.middleware_chain.process(servers, context=context)
            
            if debug_level >= 2:
                print(f"[debug] servers after middleware: {processed_servers[:2]}{' ...' if len(processed_servers) > 3 else ''}")
            
            return processed_servers, True
            
        except Exception as e:
            err = self._create_pipeline_error(
                ErrorType.INTERNAL,
                "process_middleware",
                str(e)
            )
            context.metadata['errors'].append(err)
            return servers, False
    
    def _postprocess_and_select(self, servers: list, user_routes: list, exclusions: list, mode: str) -> tuple[list, bool]:
        """Apply post-processing and server selection.
        
        Handles the final stages of server processing including
        post-processing filters and server selection logic.
        
        Args:
            servers: List of processed server objects.
            user_routes: Optional list of route tags to include.
            exclusions: Optional list of route tags to exclude.
            mode: Selection mode for server filtering.
            
        Returns:
            Tuple of (selected_servers, success_flag). Selection failures
            are not considered critical errors.
        """
        try:
            # Post-processing
            processed_servers = self.postprocessor.process(servers)
            
            # Server selection
            selected_servers = self.selector.select(
                processed_servers, 
                user_routes=user_routes, 
                exclusions=exclusions, 
                mode=mode
            )
            
            return selected_servers, True
            
        except Exception:
            # Post-processing errors are not critical - return original servers
            return servers, True

    def get_servers(self, user_routes=None, exclusions=None, mode=None, context: PipelineContext = None, force_reload: bool = False) -> PipelineResult:
        """Retrieve and process servers from subscription with comprehensive pipeline.

        Executes the complete subscription processing pipeline including fetching,
        validation, parsing, middleware processing, and server selection. Supports
        caching, error tolerance, and detailed debugging information.

        Args:
            user_routes: Optional list of route tags to include in selection.
            exclusions: Optional list of route tags to exclude from selection.
            mode: Pipeline execution mode ('strict' for fail-fast, 'tolerant' for partial success).
            context: Optional pipeline execution context for tracing and debugging.
            force_reload: Whether to bypass cache and force fresh data retrieval.

        Returns:
            PipelineResult containing:
            - config: List of ParsedServer objects or None on critical failure
            - context: Execution context with trace information
            - errors: List of PipelineError objects for any issues encountered
            - success: Boolean indicating overall pipeline success
            
        Note:
            In 'tolerant' mode, partial failures may still return success=True with
            warnings in the errors list. In 'strict' mode, any error causes failure.
            
            Results are cached based on source URL, headers, filters, and mode to
            improve performance for repeated requests.
        """
        # Initialize context and parameters
        context = context or PipelineContext()
        if mode is not None:
            context.mode = mode
        if 'errors' not in context.metadata:
            context.metadata['errors'] = []
        
        # Handle caching
        key = self._create_cache_key(mode, context)
        if force_reload:
            with self._cache_lock:
                self._get_servers_cache.pop(key, None)
        
        with self._cache_lock:
            if key in self._get_servers_cache:
                result = self._get_servers_cache[key]
                if result.success:
                    return result
        
        # Execute pipeline stages
        try:
            # Stage 1: Fetch and validate raw data
            raw_data, success = self._fetch_and_validate_raw(context)
            if not success:
                if context.mode == 'strict':
                    return PipelineResult(config=None, context=context, errors=context.metadata['errors'], success=False)
                else:
                    return PipelineResult(config=[], context=context, errors=context.metadata['errors'], success=False)
            
            # Stage 2: Parse servers
            servers, success = self._parse_servers(raw_data, context)
            if not success:
                if context.mode == 'strict':
                    return PipelineResult(config=None, context=context, errors=context.metadata['errors'], success=False)
                else:
                    return PipelineResult(config=[], context=context, errors=context.metadata['errors'], success=False)
            
            # Stage 3: Validate parsed servers
            servers, success = self._validate_parsed_servers(servers, context)
            if not success:
                return PipelineResult(config=[], context=context, errors=context.metadata['errors'], success=False)
            
            # Stage 4: Process middleware
            servers, success = self._process_middleware(servers, context)
            if not success:
                # Middleware errors are not critical in tolerant mode
                if context.mode == 'strict':
                    return PipelineResult(config=None, context=context, errors=context.metadata['errors'], success=False)
            
            # Stage 5: Post-process and select
            servers, success = self._postprocess_and_select(servers, user_routes, exclusions, mode)
            
            # Create successful result
            result = PipelineResult(config=servers, context=context, errors=context.metadata['errors'], success=True)
            
            # Cache successful result
            with self._cache_lock:
                self._get_servers_cache[key] = result
            
            return result
            
        except Exception as e:
            # Handle unexpected errors
            err = self._create_pipeline_error(
                ErrorType.INTERNAL,
                "get_servers",
                str(e)
            )
            context.metadata['errors'].append(err)
            return PipelineResult(config=None, context=context, errors=context.metadata['errors'], success=False)

    def export_config(self, exclusions=None, user_routes=None, context: PipelineContext = None, routing_plugin=None, export_manager: Optional[ExportManager] = None, skip_version_check: bool = False) -> PipelineResult:
        """Export subscription to final configuration format.

        Processes the subscription through the complete pipeline and exports
        the result to a target configuration format (e.g., sing-box JSON)
        with routing rules, filtering, and format-specific optimizations.

        Args:
            exclusions: Optional list of route tags to exclude.
            user_routes: Optional list of route tags to include.
            context: Optional pipeline execution context.
            routing_plugin: Optional custom routing plugin for rule generation.
            export_manager: Optional export manager with target format configuration.
            skip_version_check: Whether to skip version compatibility checks.

        Returns:
            PipelineResult containing:
            - config: Final configuration in target format or None on failure
            - context: Execution context with processing details
            - errors: List of any errors encountered during export
            - success: Boolean indicating export success
            
        Raises:
            None: All errors are captured in the PipelineResult.errors list.
            
        Note:
            This method combines get_servers() with format-specific export logic.
            The export format is determined by the export_manager configuration.
        """
        exclusions = exclusions or []
        user_routes = user_routes or []
        context = context or PipelineContext()
        if 'errors' not in context.metadata:
            context.metadata['errors'] = []
        servers_result = self.get_servers(user_routes=user_routes, exclusions=exclusions, mode=context.mode, context=context)
        if not servers_result.success:
            return PipelineResult(config=None, context=servers_result.context, errors=servers_result.errors, success=False)
        
        # Используем переданный ExportManager или создаём дефолтный
        mgr = export_manager or ExportManager(routing_plugin=routing_plugin)
        try:
            config = mgr.export(servers_result.config, exclusions, user_routes, context, skip_version_check=skip_version_check)
            return PipelineResult(config=config, context=context, errors=context.metadata['errors'], success=True)
        except Exception as e:
            err = PipelineError(
                type=ErrorType.INTERNAL,
                stage="export_config",
                message=str(e),
                context={},
                timestamp=datetime.now(timezone.utc)
            )
            context.metadata['errors'].append(err)
            return PipelineResult(config=None, context=context, errors=context.metadata['errors'], success=False) 