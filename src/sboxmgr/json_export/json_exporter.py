"""
JSON Export Framework for sboxmgr

Provides standardized JSON output format for all subbox client configurations
with metadata, validation, and schema compliance.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..logging import get_logger
from ..config.validation import ConfigValidationError
from ..config.config_validator import validate_temp_config_json

logger = get_logger(__name__)


class JSONExporter:
    """Standardized JSON exporter for subbox configurations"""
    
    def __init__(self, validate: bool = True):
        self.version = self._get_version()
        self.logger = logger
        self.validate = validate
    
    def export_config(self, 
                     client_type: str, 
                     config_data: Dict[str, Any],
                     subscription_url: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     validate: Optional[bool] = None) -> Dict[str, Any]:
        """
        Export configuration in standardized JSON format
        
        Args:
            client_type: Type of client (sing-box, clash, xray, mihomo)
            config_data: Client-specific configuration data
            subscription_url: Source subscription URL
            metadata: Additional metadata
            validate: Override validation setting
            
        Returns:
            Standardized JSON configuration
        """
        try:
            # Create base export structure
            exported: Dict[str, Any] = {
                "client": client_type,
                "version": self._get_client_version(client_type),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "config": config_data,
                "metadata": self._generate_metadata(subscription_url, metadata)
            }
            
            # Calculate checksum
            exported["metadata"]["checksum"] = self._calculate_checksum(exported)
            
            # Validate if requested
            should_validate = validate if validate is not None else self.validate
            if should_validate:
                try:
                    self._validate_export(exported)
                    self._validate_client_config(client_type, config_data)
                    self.logger.info(f"Configuration validation passed for {client_type}")
                except ConfigValidationError as e:
                    self.logger.error(f"Configuration validation failed: {e}")
                    raise
            
            self.logger.info(f"Exported {client_type} configuration with metadata")
            return exported
            
        except Exception as e:
            self.logger.error(f"Failed to export {client_type} configuration: {e}")
            raise
    
    def export_to_file(self,
                      client_type: str,
                      config_data: Dict[str, Any],
                      output_path: Path,
                      subscription_url: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      pretty: bool = True,
                      validate: Optional[bool] = None) -> Path:
        """
        Export configuration to file
        
        Args:
            client_type: Type of client
            config_data: Configuration data
            output_path: Output file path
            subscription_url: Source subscription URL
            metadata: Additional metadata
            pretty: Pretty print JSON
            validate: Override validation setting
            
        Returns:
            Path to created file
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Export configuration
            exported = self.export_config(client_type, config_data, subscription_url, metadata, validate)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                if pretty:
                    json.dump(exported, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(exported, f, ensure_ascii=False)
            
            self.logger.info(f"Exported {client_type} configuration to {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to export {client_type} configuration to file: {e}")
            raise
    
    def export_multiple(self,
                       configs: List[Dict[str, Any]],
                       output_dir: Path,
                       pretty: bool = True,
                       validate: Optional[bool] = None) -> List[Path]:
        """
        Export multiple configurations
        
        Args:
            configs: List of config dicts with keys: client_type, config_data, subscription_url, metadata
            output_dir: Output directory
            pretty: Pretty print JSON
            validate: Override validation setting
            
        Returns:
            List of created file paths
        """
        created_files = []
        
        for config in configs:
            try:
                client_type = config["client_type"]
                config_data = config["config_data"]
                subscription_url = config.get("subscription_url")
                metadata = config.get("metadata")
                
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{client_type}_{timestamp}.json"
                output_path = output_dir / filename
                
                # Export
                file_path = self.export_to_file(
                    client_type, config_data, output_path,
                    subscription_url, metadata, pretty, validate
                )
                created_files.append(file_path)
                
            except Exception as e:
                self.logger.error(f"Failed to export config {config.get('client_type', 'unknown')}: {e}")
                continue
        
        return created_files
    
    def _generate_metadata(self, 
                          subscription_url: Optional[str] = None,
                          additional_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate metadata for exported configuration"""
        metadata = {
            "source": subscription_url or "manual",
            "generator": f"sboxmgr-{self.version}",
            "format": "json",
            "schema_version": "1.0"
        }
        
        if additional_metadata:
            metadata.update(additional_metadata)
        
        return metadata
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate SHA256 checksum of configuration data"""
        # Create a copy without checksum for consistent hashing
        data_copy = data.copy()
        if "metadata" in data_copy and "checksum" in data_copy["metadata"]:
            del data_copy["metadata"]["checksum"]
        
        json_str = json.dumps(data_copy, sort_keys=True, ensure_ascii=False)
        return f"sha256:{hashlib.sha256(json_str.encode('utf-8')).hexdigest()}"
    
    def _get_version(self) -> str:
        """Get sboxmgr version from package metadata."""
        try:
            from sboxmgr import __version__
            return __version__
        except Exception:
            return "unknown"
    
    def _get_client_version(self, client_type: str) -> str:
        """Get client version if available"""
        # This could be enhanced to detect actual client versions
        client_versions = {
            "sing-box": "1.8.0",
            "clash": "1.18.0", 
            "xray": "1.8.0",
            "mihomo": "1.8.0"
        }
        return client_versions.get(client_type, "unknown")
    
    def _validate_export(self, exported: Dict[str, Any]) -> None:
        """Validate exported configuration structure.
        
        Args:
            exported: Exported configuration dictionary
            
        Raises:
            ConfigValidationError: If validation fails
        """
        required_fields = ["client", "version", "created_at", "config", "metadata"]
        for field in required_fields:
            if field not in exported:
                raise ConfigValidationError(f"Exported configuration missing required field: {field}")
        
        if not isinstance(exported["client"], str):
            raise ConfigValidationError("'client' field must be a string")
        
        if not isinstance(exported["config"], dict):
            raise ConfigValidationError("'config' field must be a dictionary")
        
        if not isinstance(exported["metadata"], dict):
            raise ConfigValidationError("'metadata' field must be a dictionary")
    
    def _validate_client_config(self, client_type: str, config_data: Dict[str, Any]) -> None:
        """Validate client-specific configuration.
        
        Args:
            client_type: Type of client
            config_data: Configuration data
            
        Raises:
            ConfigValidationError: If validation fails
        """
        if client_type == "sing-box":
            # Use internal sing-box validator
            try:
                config_json = json.dumps(config_data)
                validate_temp_config_json(config_json)
            except Exception as e:
                raise ConfigValidationError(f"Sing-box configuration validation failed: {e}")
        elif client_type in ["clash", "xray", "mihomo"]:
            # Basic validation for other clients
            if not isinstance(config_data, dict):
                raise ConfigValidationError(f"{client_type} configuration must be a dictionary")
        else:
            raise ConfigValidationError(f"Unsupported client type: {client_type}")


class JSONExporterFactory:
    """Factory for creating JSON exporters with different configurations"""
    
    @staticmethod
    def create_exporter(config: Optional[Dict[str, Any]] = None) -> JSONExporter:
        """Create JSON exporter with optional configuration"""
        validate = config.get("validate", True) if config else True
        return JSONExporter(validate=validate)
    
    @staticmethod
    def create_batch_exporter() -> JSONExporter:
        """Create exporter optimized for batch operations"""
        return JSONExporter(validate=True) 