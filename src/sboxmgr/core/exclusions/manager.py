"""File-based ExclusionManager implementation with caching and DI support."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Union
import threading
import fnmatch

from ..interfaces import ExclusionManagerInterface
from .models import ExclusionEntry, ExclusionList
from sboxmgr.utils.file import atomic_write_json, file_exists, read_json
from sboxmgr.utils.env import get_exclusion_file
from sboxmgr.utils.id import generate_server_id


class ExclusionLoadError(Exception):
    """Exception raised when exclusion file cannot be loaded."""
    pass


class ExclusionManager(ExclusionManagerInterface):
    """File-based exclusion manager with caching and atomic operations.
    
    Features:
    - Stateful caching (loads once, updates in memory)
    - Thread-safe operations
    - Atomic file writes
    - Backward compatibility with old format
    - Dependency injection ready
    """
    
    _default_instance: Optional['ExclusionManager'] = None
    _default_lock = threading.Lock()
    
    def __init__(self, file_path: Optional[Path] = None, auto_load: bool = True, logger: Optional[logging.Logger] = None):
        """Initialize ExclusionManager.
        
        Args:
            file_path: Path to exclusions file (defaults to env setting)
            auto_load: Whether to load exclusions on init
            logger: Custom logger instance (defaults to module logger)
        """
        self.file_path = Path(file_path) if file_path else Path(get_exclusion_file())
        self._exclusions: Optional[ExclusionList] = None
        self._lock = threading.RLock()
        self.logger = logger or logging.getLogger(__name__)
        self._servers_cache: Dict[str, Any] = {}  # Cache for server data
        
        if auto_load:
            self._load()
    
    @classmethod
    def default(cls) -> 'ExclusionManager':
        """Get or create the default ExclusionManager, respecting env changes."""
        from sboxmgr.utils.env import get_exclusion_file
        file_path = get_exclusion_file()
        with cls._default_lock:
            # Если singleton не создан или путь изменился — пересоздать
            if (
                cls._default_instance is None or
                str(cls._default_instance.file_path) != str(file_path)
            ):
                cls._default_instance = cls(file_path=file_path)
            return cls._default_instance
    
    def _load(self) -> ExclusionList:
        """Load exclusions from file (with caching and fail-safe)."""
        with self._lock:
            if self._exclusions is not None:
                return self._exclusions
            
            if file_exists(str(self.file_path)):
                try:
                    data = read_json(str(self.file_path))
                    self._exclusions = ExclusionList.from_dict(data)
                    self.logger.debug(f"Loaded {len(self._exclusions.exclusions)} exclusions from {self.file_path}")
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    # Fail-safe: corrupted file -> empty list + restore file
                    self.logger.warning(f"Exclusion file {self.file_path} is corrupted: {e}. Restoring to empty state.")
                    self._exclusions = ExclusionList()
                    # Restore the file with empty exclusions
                    try:
                        self._save()
                        self.logger.info(f"Restored corrupted exclusion file {self.file_path} to empty state")
                    except Exception as save_error:
                        self.logger.error(f"Failed to restore exclusion file {self.file_path}: {save_error}")
                    # Don't raise exception on init - fail-safe mode
                except Exception as e:
                    # Unexpected error -> fail-safe
                    self.logger.error(f"Unexpected error loading exclusions from {self.file_path}: {e}. Using empty list.")
                    self._exclusions = ExclusionList()
                    # Don't raise exception on init - fail-safe mode
            else:
                self._exclusions = ExclusionList()
                self.logger.debug(f"No exclusion file found at {self.file_path}, starting with empty list")
            
            return self._exclusions
    
    def _save(self) -> None:
        """Save exclusions to file (atomic)."""
        if self._exclusions is None:
            return
        
        try:
            data = self._exclusions.to_dict()
            atomic_write_json(data, str(self.file_path))
        except Exception as e:
            logging.error(f"Failed to save exclusions to {self.file_path}: {e}")
            raise
    
    def add(self, server_id: str, name: str = None, reason: str = None) -> bool:
        """Add server to exclusions with audit logging."""
        exclusions = self._load()  # _load() now handles errors internally
        
        entry = ExclusionEntry(
            id=server_id,
            name=name,
            reason=reason
        )
        
        with self._lock:
            if exclusions.add(entry):
                self._save()
                # Audit logging
                display_name = name or server_id
                display_reason = f" (reason: {reason})" if reason else ""
                self.logger.info(f"Excluded server: {display_name} [ID: {server_id}]{display_reason}")
                return True
            else:
                self.logger.debug(f"Server {server_id} already excluded")
                return False
    
    def add_from_server_data(self, server_data: Dict, reason: str = None) -> bool:
        """Add server to exclusions from server configuration data.
        
        Args:
            server_data: Server configuration dictionary
            reason: Reason for exclusion
            
        Returns:
            True if added, False if already existed
        """
        server_id = generate_server_id(server_data)
        name = f"{server_data.get('tag', 'N/A')} ({server_data.get('type', 'N/A')}:{server_data.get('server_port', 'N/A')})"
        
        return self.add(server_id, name, reason)
    
    def remove(self, server_id: str) -> bool:
        """Remove server from exclusions with audit logging."""
        try:
            exclusions = self._load()
        except ExclusionLoadError:
            self.logger.warning(f"Cannot remove {server_id}: exclusion file corrupted")
            return False
        
        # Get name before removal for logging
        old_entry = next((ex for ex in exclusions.exclusions if ex.id == server_id), None)
        
        with self._lock:
            if exclusions.remove(server_id):
                self._save()
                # Audit logging
                display_name = old_entry.name if old_entry else server_id
                self.logger.info(f"Removed exclusion: {display_name} [ID: {server_id}]")
                return True
            else:
                self.logger.warning(f"Attempted to remove non-existent exclusion: {server_id}")
                return False
    
    def contains(self, server_id: str) -> bool:
        """Check if server is excluded."""
        exclusions = self._load()
        return exclusions.contains(server_id)
    
    def list_all(self) -> List[Dict]:
        """List all exclusions."""
        exclusions = self._load()
        return [ex.to_dict() for ex in exclusions.exclusions]
    
    def clear(self) -> int:
        """Clear all exclusions."""
        exclusions = self._load()
        
        with self._lock:
            count = exclusions.clear()
            if count > 0:
                self._save()
            return count
    
    def filter_servers(self, servers: List[Any]) -> List[Any]:
        """Filter servers by removing excluded ones.
        
        Args:
            servers: List of server objects (ParsedServer or dict)
            
        Returns:
            Filtered list without excluded servers
        """
        if not servers:
            return servers
        
        excluded_ids = self.get_excluded_ids()
        if not excluded_ids:
            return servers
        
        filtered = []
        for server in servers:
            # Handle both ParsedServer objects and dicts
            if hasattr(server, '__dict__'):
                # ParsedServer object - generate ID from its attributes
                server_dict = server.__dict__ if hasattr(server, '__dict__') else {}
                server_id = generate_server_id(server_dict)
            else:
                # Dictionary - use directly
                server_id = generate_server_id(server)
            
            if server_id not in excluded_ids:
                filtered.append(server)
        
        return filtered
    
    def get_excluded_ids(self) -> set:
        """Get set of excluded server IDs for fast lookup."""
        exclusions = self._load()
        return exclusions.get_ids()
    
    def reload(self) -> None:
        """Force reload from file (clears cache)."""
        with self._lock:
            self._exclusions = None
        self._load()
    
    def is_loaded(self) -> bool:
        """Check if exclusions are loaded in memory."""
        return self._exclusions is not None
    
    def get_stats(self) -> Dict:
        """Get exclusion statistics."""
        exclusions = self._load()
        return {
            "total_exclusions": len(exclusions.exclusions),
            "last_modified": exclusions.last_modified.isoformat(),
            "file_path": str(self.file_path),
            "file_exists": file_exists(str(self.file_path)),
            "loaded_in_memory": self.is_loaded()
        }

    # NEW: Server listing and parsing functions
    def set_servers_cache(self, json_data: Union[Dict[str, Any], List[Dict[str, Any]]], supported_protocols: List[str]) -> None:
        """Cache server data for index-based operations."""
        # Handle both dict with "outbounds" key and direct list of servers
        if isinstance(json_data, dict):
            servers = json_data.get("outbounds", json_data)
        elif isinstance(json_data, list):
            servers = json_data
        else:
            raise ValueError(f"Expected dict or list, got {type(json_data)}")
            
        self._servers_cache = {
            'servers': servers,
            'supported_servers': [
                (idx, server) for idx, server in enumerate(servers)
                if server.get("type") in supported_protocols
            ],
            'supported_protocols': supported_protocols
        }
        self.logger.debug(f"Cached {len(self._servers_cache['supported_servers'])} supported servers")

    def list_servers(self, json_data: Optional[Dict[str, Any]] = None, 
                    supported_protocols: Optional[List[str]] = None,
                    show_excluded: bool = True) -> List[Tuple[int, Dict[str, Any], bool]]:
        """List available servers with indices and exclusion status.
        
        Returns:
            List of (index, server_data, is_excluded) tuples
        """
        if json_data and supported_protocols:
            self.set_servers_cache(json_data, supported_protocols)
        
        if not self._servers_cache:
            return []
        
        self._load()
        result = []
        
        # Use sequential numbering for display, not original indices
        for display_idx, (original_idx, server) in enumerate(self._servers_cache['supported_servers']):
            server_id = generate_server_id(server)
            is_excluded = self.contains(server_id)
            
            if show_excluded or not is_excluded:
                result.append((display_idx, server, is_excluded))
        
        return result

    def format_server_info(self, server: Dict[str, Any], index: int, is_excluded: bool = False) -> str:
        """Format server information for display."""
        tag = server.get('tag', 'N/A')
        server_type = server.get('type', 'N/A')
        port = server.get('server_port', 'N/A')
        
        status = "🚫 EXCLUDED" if is_excluded else "✅ Available"
        return f"[{index:2d}] {tag} ({server_type}:{port}) - {status}"

    # NEW: Enhanced add methods with wildcard and index support
    def _ensure_file_valid(self) -> None:
        """Ensure exclusion file is valid, restore if corrupted."""
        if not file_exists(str(self.file_path)):
            return
        
        try:
            # Try to read the file to check if it's valid
            read_json(str(self.file_path))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # File is corrupted, restore it
            self.logger.warning(f"Exclusion file {self.file_path} is corrupted: {e}. Restoring to empty state.")
            self._exclusions = ExclusionList()
            try:
                self._save()
                self.logger.info(f"Restored corrupted exclusion file {self.file_path} to empty state")
            except Exception as save_error:
                self.logger.error(f"Failed to restore exclusion file {self.file_path}: {save_error}")

    def add_by_index(self, json_data: Union[Dict[str, Any], List[Dict[str, Any]]], indices: List[int], 
                    supported_protocols: List[str], reason: str = "Added by index") -> List[str]:
        """Add exclusions by server indices.
        
        Args:
            json_data: Server data (will not re-cache if it's the same as cached)
            indices: Display indices from list_servers output
            
        Returns:
            List of added server IDs
        """
        # Only re-cache if data is different or cache is empty
        if not self._servers_cache or json_data != self._servers_cache.get('servers'):
            self.set_servers_cache(json_data, supported_protocols)
        
        # Ensure file is valid before loading
        self._ensure_file_valid()
        self._load()
        
        added_ids = []
        supported_servers = self._servers_cache['supported_servers']
        
        with self._lock:
            for display_index in indices:
                if 0 <= display_index < len(supported_servers):
                    _, server = supported_servers[display_index]
                    server_id = generate_server_id(server)
                    name = f"{server.get('tag', 'N/A')} ({server.get('type', 'N/A')}:{server.get('server_port', 'N/A')})"
                    
                    if not self.contains(server_id):
                        entry = ExclusionEntry(id=server_id, name=name, reason=reason)
                        self._exclusions.exclusions.append(entry)
                        added_ids.append(server_id)
                        self.logger.info(f"Excluded server by index {display_index}: {name} [ID: {server_id}] (reason: {reason})")
                    else:
                        self.logger.info(f"Server already excluded: {name} [ID: {server_id}]")
                else:
                    self.logger.warning(f"Invalid server index: {display_index} (max: {len(supported_servers)-1})")
            
            if added_ids:
                self._save()
        
        return added_ids

    def add_by_wildcard(self, json_data: Union[Dict[str, Any], List[Dict[str, Any]]], patterns: List[str], 
                       supported_protocols: List[str], reason: str = "Added by wildcard") -> List[str]:
        """Add exclusions by wildcard patterns matching server tags.
        
        Returns:
            List of added server IDs
        """
        # Only re-cache if data is different or cache is empty
        if not self._servers_cache or json_data != self._servers_cache.get('servers'):
            self.set_servers_cache(json_data, supported_protocols)
        
        # Ensure file is valid before loading
        self._ensure_file_valid()
        self._load()
        
        added_ids = []
        supported_servers = self._servers_cache['supported_servers']
        
        with self._lock:
            for pattern in patterns:
                for _, server in supported_servers:
                    server_tag = server.get("tag", "")
                    if fnmatch.fnmatch(server_tag, pattern):
                        server_id = generate_server_id(server)
                        name = f"{server.get('tag', 'N/A')} ({server.get('type', 'N/A')}:{server.get('server_port', 'N/A')})"
                        
                        if not self.contains(server_id):
                            entry = ExclusionEntry(id=server_id, name=name, reason=reason)
                            self._exclusions.exclusions.append(entry)
                            added_ids.append(server_id)
                            self.logger.info(f"Excluded server by pattern '{pattern}': {name} [ID: {server_id}] (reason: {reason})")
                        else:
                            self.logger.info(f"Server already excluded: {name} [ID: {server_id}]")
            
            if added_ids:
                self._save()
        
        return added_ids

    # NEW: Enhanced remove methods with index support
    def remove_by_index(self, json_data: Union[Dict[str, Any], List[Dict[str, Any]]], indices: List[int], 
                       supported_protocols: List[str]) -> List[str]:
        """Remove exclusions by server indices.
        
        Args:
            json_data: Server data (will not re-cache if it's the same as cached)
            indices: Display indices from list_servers output
            
        Returns:
            List of removed server IDs
        """
        # Only re-cache if data is different or cache is empty
        if not self._servers_cache or json_data != self._servers_cache.get('servers'):
            self.set_servers_cache(json_data, supported_protocols)
        
        self._load()
        
        removed_ids = []
        supported_servers = self._servers_cache['supported_servers']
        
        with self._lock:
            for display_index in indices:
                if 0 <= display_index < len(supported_servers):
                    _, server = supported_servers[display_index]
                    server_id = generate_server_id(server)
                    
                    if self.remove(server_id):
                        removed_ids.append(server_id)
                        self.logger.info(f"Removed exclusion for server at index {display_index}: {server.get('tag', 'N/A')} [ID: {server_id}]")
                    else:
                        self.logger.warning(f"Server at index {display_index} was not excluded: {server.get('tag', 'N/A')} [ID: {server_id}]")
                else:
                    self.logger.warning(f"Invalid server index: {display_index} (max: {len(supported_servers)-1})")
        
        return removed_ids

    # NEW: Bulk operations
    def add_multiple(self, entries: List[Tuple[str, str, str]]) -> List[str]:
        """Add multiple exclusions at once.
        
        Args:
            entries: List of (server_id, name, reason) tuples
            
        Returns:
            List of added server IDs
        """
        self._load()
        added_ids = []
        
        with self._lock:
            for server_id, name, reason in entries:
                if not self.contains(server_id):
                    entry = ExclusionEntry(id=server_id, name=name, reason=reason)
                    self._exclusions.exclusions.append(entry)
                    added_ids.append(server_id)
                    self.logger.info(f"Excluded server: {name} [ID: {server_id}] (reason: {reason})")
            
            if added_ids:
                self._save()
        
        return added_ids

    def remove_multiple(self, server_ids: List[str]) -> List[str]:
        """Remove multiple exclusions at once.
        
        Returns:
            List of removed server IDs
        """
        self._load()
        removed_ids = []
        
        with self._lock:
            for server_id in server_ids:
                if self.remove(server_id):
                    removed_ids.append(server_id)
        
        return removed_ids 