"""Required fields validator for parsed servers.

This module provides validation for essential server configuration fields.
It ensures that all parsed servers have the minimum required fields (type,
address, port) and validates field values for consistency and security
before configuration export.
"""
from .base import BaseParsedValidator, register_parsed_validator, ValidationResult
from sboxmgr.subscription.models import PipelineContext

@register_parsed_validator("required_fields")
class RequiredFieldsValidator(BaseParsedValidator):
    """Validates required fields for ParsedServer: type, address, port, and value acceptability.
    
    This validator ensures that all parsed servers have the essential fields
    required for configuration export. It checks for type, address, and port
    fields and validates their values are within acceptable ranges.
    """
    
    def validate(self, servers: list, context: PipelineContext) -> ValidationResult:
        """Validate that servers have all required fields with valid values.
        
        Checks each server for required fields (type, address, port) and validates
        that field values are within acceptable ranges and formats.
        
        Args:
            servers: List of ParsedServer objects to validate.
            context: Pipeline context containing validation settings.
            
        Returns:
            ValidationResult: Contains validation errors and list of valid servers.
        """
        errors = []
        valid_servers = []
        for idx, s in enumerate(servers):
            err = None
            if not hasattr(s, 'type') or not s.type:
                err = f"Server[{idx}]: missing type"
            elif not hasattr(s, 'address') or not s.address:
                err = f"Server[{idx}]: missing address"
            elif not hasattr(s, 'port') or not isinstance(s.port, int) or not (1 <= s.port <= 65535):
                err = f"Server[{idx}]: invalid port: {getattr(s, 'port', None)}"
            if err:
                errors.append(err)
            else:
                valid_servers.append(s)
        
        return ValidationResult(valid=bool(valid_servers), errors=errors, valid_servers=valid_servers) 