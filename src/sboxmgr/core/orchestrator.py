"""Orchestrator facade for coordinating all sboxmgr operations.

This module provides the central coordination layer that acts as a facade
for all sboxmgr operations. It implements the dependency injection pattern
to enable proper testing and architectural separation while providing a
unified interface for CLI and other consumers.
"""

from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass

from .interfaces import (
    SubscriptionManagerInterface, 
    ExportManagerInterface, 
    ExclusionManagerInterface
)
from sboxmgr.subscription.models import SubscriptionSource, PipelineContext, PipelineResult


@dataclass
class OrchestratorConfig:
    """Configuration for Orchestrator operations.
    
    Centralizes configuration management for consistent behavior
    across all coordinated operations.
    
    Attributes:
        default_mode: Default pipeline execution mode.
        debug_level: Default debug verbosity level.
        cache_enabled: Whether to enable result caching.
        timeout_seconds: Default timeout for operations.
        fail_safe: Whether to use fail-safe error handling.
    """
    default_mode: str = "tolerant"
    debug_level: int = 0
    cache_enabled: bool = True
    timeout_seconds: int = 30
    fail_safe: bool = True


class OrchestratorError(Exception):
    """Base exception for Orchestrator operations.
    
    Provides a consistent exception hierarchy for all orchestrator-level
    errors with context preservation and error chaining support.
    """
    
    def __init__(self, message: str, operation: str = None, cause: Exception = None):
        """Initialize orchestrator error.
        
        Args:
            message: Human-readable error description.
            operation: Name of operation that failed.
            cause: Original exception that caused this error.
        """
        super().__init__(message)
        self.operation = operation
        self.cause = cause


class Orchestrator:
    """Central facade for coordinating all sboxmgr operations.
    
    The Orchestrator provides a unified interface for subscription management,
    configuration export, and exclusion management. It implements dependency
    injection pattern for testability and uses consistent error handling
    and logging across all operations.
    
    This class serves as the single point of coordination between CLI commands
    and the various manager components, eliminating direct dependencies and
    enabling proper architectural separation.
    
    Attributes:
        config: Configuration settings for orchestrator operations.
        logger: Logger instance for operation tracking.
        subscription_manager: Injected subscription management service.
        export_manager: Injected configuration export service.
        exclusion_manager: Injected server exclusion service.
    """
    
    def __init__(self, 
                 subscription_manager: Optional[SubscriptionManagerInterface] = None,
                 export_manager: Optional[ExportManagerInterface] = None,
                 exclusion_manager: Optional[ExclusionManagerInterface] = None,
                 config: Optional[OrchestratorConfig] = None,
                 logger: Optional[logging.Logger] = None):
        """Initialize Orchestrator with dependency injection.
        
        Args:
            subscription_manager: Service for subscription operations.
            export_manager: Service for configuration export.
            exclusion_manager: Service for exclusion management.
            config: Configuration settings for operations.
            logger: Custom logger instance.
        """
        self.config = config or OrchestratorConfig()
        self.logger = logger or logging.getLogger(__name__)
        
        # Dependency injection - will be resolved by factory if None
        self._subscription_manager = subscription_manager
        self._export_manager = export_manager
        self._exclusion_manager = exclusion_manager
    
    @property
    def subscription_manager(self) -> SubscriptionManagerInterface:
        """Get subscription manager instance with lazy loading.
        
        Returns:
            Subscription manager instance.
            
        Raises:
            OrchestratorError: If subscription manager cannot be resolved.
        """
        if self._subscription_manager is None:
            from .factory import create_default_subscription_manager
            self._subscription_manager = create_default_subscription_manager()
        return self._subscription_manager
    
    @property
    def export_manager(self) -> ExportManagerInterface:
        """Get export manager instance with lazy loading.
        
        Returns:
            Export manager instance.
            
        Raises:
            OrchestratorError: If export manager cannot be resolved.
        """
        if self._export_manager is None:
            from .factory import create_default_export_manager
            self._export_manager = create_default_export_manager()
        return self._export_manager
    
    @property
    def exclusion_manager(self) -> ExclusionManagerInterface:
        """Get exclusion manager instance with lazy loading.
        
        Returns:
            Exclusion manager instance.
            
        Raises:
            OrchestratorError: If exclusion manager cannot be resolved.
        """
        if self._exclusion_manager is None:
            from .factory import create_default_exclusion_manager
            self._exclusion_manager = create_default_exclusion_manager()
        return self._exclusion_manager
    
    def get_subscription_servers(self, url: str, 
                                source_type: str = "url_base64",
                                user_routes: Optional[List[str]] = None,
                                exclusions: Optional[List[str]] = None,
                                mode: Optional[str] = None,
                                force_reload: bool = False,
                                **kwargs) -> PipelineResult:
        """Retrieve and process servers from subscription source.
        
        Provides a unified interface for subscription processing that coordinates
        between subscription management and exclusion filtering. Handles error
        reporting and logging consistently across the operation.
        
        Args:
            url: Subscription URL to fetch from.
            source_type: Type of subscription source (url_base64, url_json, etc.).
            user_routes: Optional list of route tags to include in selection.
            exclusions: Optional list of route tags to exclude from selection.
            mode: Pipeline execution mode (strict, tolerant).
            force_reload: Whether to bypass cache and force fresh data retrieval.
            **kwargs: Additional arguments passed to subscription manager.
            
        Returns:
            PipelineResult containing processed servers and execution metadata.
            
        Raises:
            OrchestratorError: If subscription processing fails critically.
        """
        try:
            self.logger.info(f"Processing subscription from {url}")
            
            # Create subscription source
            source = SubscriptionSource(url=url, source_type=source_type)
            
            # Create pipeline context
            context = PipelineContext(
                mode=mode or self.config.default_mode,
                debug_level=self.config.debug_level
            )
            # Always create subscription manager for the specific source URL
            # SubscriptionManager is tied to a specific source, so we can't reuse 
            # it for different URLs as it would fetch from the wrong source
            from sboxmgr.subscription.manager import SubscriptionManager
            sub_manager = SubscriptionManager(source)
            
            # Get servers through pipeline
            result = sub_manager.get_servers(
                user_routes=user_routes,
                exclusions=exclusions,
                mode=context.mode,
                context=context,
                force_reload=force_reload
            )
            
            # Apply exclusion filtering if exclusion manager is available
            if result.success and result.config:
                try:
                    filtered_servers = self.exclusion_manager.filter_servers(result.config)
                    # Update result with filtered servers
                    result.config = filtered_servers
                    self.logger.info(f"Filtered to {len(filtered_servers)} servers after exclusions")
                except Exception as e:
                    self.logger.warning(f"Exclusion filtering failed: {e}")
                    if not self.config.fail_safe:
                        raise
            
            self.logger.info(f"Subscription processing completed: {result.success}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to process subscription from {url}: {str(e)}"
            self.logger.error(error_msg)
            if self.config.fail_safe:
                # Return failed result instead of raising
                context = PipelineContext(mode=mode or self.config.default_mode)
                context.metadata['errors'] = [str(e)]
                return PipelineResult(config=None, context=context, errors=[str(e)], success=False)
            else:
                raise OrchestratorError(error_msg, operation="get_subscription_servers", cause=e)
    
    def manage_exclusions(self, action: str, **kwargs) -> Dict[str, Any]:
        """Unified interface for exclusion management operations.
        
        Provides a single entry point for all exclusion-related operations
        including add, remove, list, and clear with consistent error handling
        and result formatting.
        
        Args:
            action: The exclusion action to perform (add, remove, list, clear).
            **kwargs: Action-specific arguments.
            
        Returns:
            Dictionary containing operation result and metadata.
            
        Raises:
            OrchestratorError: If exclusion operation fails.
        """
        try:
            self.logger.info(f"Managing exclusions: {action}")
            
            result = {"action": action, "success": False, "message": "", "data": None}
            
            if action == "add":
                server_id = kwargs.get("server_id")
                name = kwargs.get("name")
                reason = kwargs.get("reason")
                
                if not server_id:
                    raise ValueError("server_id is required for add action")
                
                success = self.exclusion_manager.add(server_id, name, reason)
                result.update({
                    "success": success,
                    "message": f"Server {server_id} {'added to' if success else 'already in'} exclusions",
                    "data": {"server_id": server_id, "added": success}
                })
                
            elif action == "remove":
                server_id = kwargs.get("server_id")
                
                if not server_id:
                    raise ValueError("server_id is required for remove action")
                
                success = self.exclusion_manager.remove(server_id)
                result.update({
                    "success": success,
                    "message": f"Server {server_id} {'removed from' if success else 'not found in'} exclusions",
                    "data": {"server_id": server_id, "removed": success}
                })
                
            elif action == "list":
                exclusions = self.exclusion_manager.list_all()
                result.update({
                    "success": True,
                    "message": f"Found {len(exclusions)} exclusions",
                    "data": {"exclusions": exclusions, "count": len(exclusions)}
                })
                
            elif action == "clear":
                count = self.exclusion_manager.clear()
                result.update({
                    "success": True,
                    "message": f"Cleared {count} exclusions",
                    "data": {"cleared_count": count}
                })
                
            else:
                raise ValueError(f"Unknown exclusion action: {action}")
            
            self.logger.info(f"Exclusion operation completed: {result['message']}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to manage exclusions (action={action}): {str(e)}"
            self.logger.error(error_msg)
            if self.config.fail_safe:
                return {
                    "action": action,
                    "success": False,
                    "message": error_msg,
                    "data": None,
                    "error": str(e)
                }
            else:
                raise OrchestratorError(error_msg, operation="manage_exclusions", cause=e)
    
    def export_configuration(self, source_url: str,
                           source_type: str = "url_base64", 
                           export_format: str = "singbox",
                           exclusions: Optional[List[str]] = None,
                           user_routes: Optional[List[str]] = None,
                           skip_version_check: bool = False,
                           **kwargs) -> Dict[str, Any]:
        """Export subscription to client configuration format.
        
        Coordinates the complete process from subscription fetching through
        final configuration export with unified error handling and logging.
        
        Args:
            source_url: Subscription URL to process.
            source_type: Type of subscription source.
            export_format: Target export format (singbox, clash, etc.).
            exclusions: Optional list of server addresses to exclude.
            user_routes: Optional list of custom routing rules.
            skip_version_check: Whether to skip version compatibility checks.
            **kwargs: Additional arguments for export customization.
            
        Returns:
            Dictionary containing the exported configuration and metadata.
            
        Raises:
            OrchestratorError: If export process fails.
        """
        try:
            self.logger.info(f"Exporting configuration from {source_url} to {export_format}")
            
            # First get servers from subscription
            servers_result = self.get_subscription_servers(
                url=source_url,
                source_type=source_type,
                user_routes=user_routes,
                exclusions=exclusions,
                **kwargs
            )
            
            if not servers_result.success:
                raise OrchestratorError(
                    f"Failed to retrieve servers: {servers_result.errors}",
                    operation="get_servers"
                )
            
            # Export configuration using export manager
            # Convert user_routes from List[str] to List[Dict] for compatibility
            user_routes_dicts = [{"tag": route} for route in (user_routes or [])]
            
            config = self.export_manager.export(
                servers=servers_result.config,
                exclusions=exclusions,
                user_routes=user_routes_dicts,
                skip_version_check=skip_version_check
            )
            
            result = {
                "success": True,
                "format": export_format,
                "server_count": len(servers_result.config) if servers_result.config else 0,
                "config": config,
                "metadata": {
                    "source_url": source_url,
                    "exclusions_applied": len(exclusions) if exclusions else 0,
                    "pipeline_errors": len(servers_result.errors)
                }
            }
            
            self.logger.info(f"Configuration export completed: {result['server_count']} servers")
            return result
            
        except Exception as e:
            error_msg = f"Failed to export configuration: {str(e)}"
            self.logger.error(error_msg)
            if self.config.fail_safe:
                return {
                    "success": False,
                    "format": export_format,
                    "error": error_msg,
                    "config": None
                }
            else:
                raise OrchestratorError(error_msg, operation="export_configuration", cause=e)
    
    @classmethod
    def create_default(cls, **config_overrides) -> 'Orchestrator':
        """Factory method to create Orchestrator with default dependencies.
        
        Provides a convenient way to create a fully configured Orchestrator
        instance with default implementations for all dependencies.
        
        Args:
            **config_overrides: Configuration values to override defaults.
            
        Returns:
            Fully configured Orchestrator instance.
        """
        config = OrchestratorConfig(**config_overrides)
        return cls(config=config)
    
    def with_custom_managers(self, **managers) -> 'Orchestrator':
        """Builder pattern for creating Orchestrator with custom managers.
        
        Enables flexible customization of dependencies while preserving
        existing configuration and other dependencies.
        
        Args:
            **managers: Custom manager instances to inject.
            
        Returns:
            New Orchestrator instance with custom managers.
        """
        return Orchestrator(
            subscription_manager=managers.get('subscription_manager', self._subscription_manager),
            export_manager=managers.get('export_manager', self._export_manager),
            exclusion_manager=managers.get('exclusion_manager', self._exclusion_manager),
            config=self.config,
            logger=self.logger
        ) 