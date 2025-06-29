"""Interfaces for dependency injection in Orchestrator pattern.

This module defines the abstract interfaces that the Orchestrator uses
to interact with different manager components. This enables proper
dependency injection, testing, and architectural separation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from sboxmgr.subscription.models import PipelineContext, PipelineResult


class SubscriptionManagerInterface(ABC):
    """Abstract interface for subscription management operations.
    
    Defines the contract for subscription processing including
    server retrieval, configuration export, and pipeline management.
    """
    
    @abstractmethod
    def get_servers(self, user_routes: Optional[List[str]] = None, 
                   exclusions: Optional[List[str]] = None, 
                   mode: Optional[str] = None,
                   context: Optional[PipelineContext] = None,
                   force_reload: bool = False) -> PipelineResult:
        """Retrieve and process servers from subscription.
        
        Args:
            user_routes: Optional list of route tags to include.
            exclusions: Optional list of route tags to exclude.
            mode: Pipeline execution mode.
            context: Optional pipeline execution context.
            force_reload: Whether to bypass cache.
            
        Returns:
            PipelineResult containing servers and execution metadata.
        """
        pass
    
    @abstractmethod
    def export_config(self, exclusions: Optional[List[str]] = None,
                     user_routes: Optional[List[str]] = None,
                     context: Optional[PipelineContext] = None,
                     routing_plugin: Optional[Any] = None,
                     export_manager: Optional[Any] = None,
                     skip_version_check: bool = False) -> PipelineResult:
        """Export subscription to configuration format.
        
        Args:
            exclusions: Optional list of route tags to exclude.
            user_routes: Optional list of route tags to include.
            context: Optional pipeline execution context.
            routing_plugin: Optional custom routing plugin.
            export_manager: Optional custom export manager.
            skip_version_check: Whether to skip version compatibility checks.
            
        Returns:
            PipelineResult containing exported configuration.
        """
        pass


class ExportManagerInterface(ABC):
    """Abstract interface for configuration export operations.
    
    Defines the contract for exporting processed server configurations
    to various client formats with routing and profile customization.
    """
    
    @abstractmethod
    def export(self, servers: List[Any], 
              exclusions: Optional[List[str]] = None,
              user_routes: Optional[List[Dict]] = None,
              context: Optional[Dict[str, Any]] = None,
              client_profile: Optional[Any] = None,
              skip_version_check: bool = False) -> Dict:
        """Export servers to client configuration format.
        
        Args:
            servers: List of parsed server configurations.
            exclusions: Optional list of server addresses to exclude.
            user_routes: Optional list of custom routing rules.
            context: Optional context dictionary for export customization.
            client_profile: Optional client profile override.
            skip_version_check: Whether to skip version compatibility checks.
            
        Returns:
            Dictionary containing the final client configuration.
        """
        pass


class ExclusionManagerInterface(ABC):
    """Abstract interface for server exclusion management.
    
    Defines the contract for managing server exclusions including
    adding, removing, and querying exclusion entries.
    """
    
    @abstractmethod
    def add(self, server_id: str, name: Optional[str] = None, 
           reason: Optional[str] = None) -> bool:
        """Add server to exclusions.
        
        Args:
            server_id: Unique identifier for the server.
            name: Optional human-readable name.
            reason: Optional reason for exclusion.
            
        Returns:
            True if added, False if already existed.
        """
        pass
    
    @abstractmethod
    def remove(self, server_id: str) -> bool:
        """Remove server from exclusions.
        
        Args:
            server_id: Unique identifier for the server.
            
        Returns:
            True if removed, False if not found.
        """
        pass
    
    @abstractmethod
    def contains(self, server_id: str) -> bool:
        """Check if server is excluded.
        
        Args:
            server_id: Unique identifier for the server.
            
        Returns:
            True if server is excluded, False otherwise.
        """
        pass
    
    @abstractmethod
    def list_all(self) -> List[Dict]:
        """List all exclusions.
        
        Returns:
            List of exclusion dictionaries with metadata.
        """
        pass
    
    @abstractmethod
    def clear(self) -> int:
        """Clear all exclusions.
        
        Returns:
            Number of exclusions that were cleared.
        """
        pass
    
    @abstractmethod
    def filter_servers(self, servers: List[Any]) -> List[Any]:
        """Filter servers by removing excluded ones.
        
        Args:
            servers: List of server objects to filter.
            
        Returns:
            Filtered list without excluded servers.
        """
        pass 