"""Base validator interfaces for subscription data validation.

This module defines the abstract base classes for validators that ensure
subscription data quality and consistency. It provides interfaces for
validating raw subscription data, parsed servers, and final configurations
before export to client applications.
"""

from abc import ABC, abstractmethod
from typing import List
from sboxmgr.subscription.models import PipelineContext

class ValidationResult:
    """Result of a validation operation.
    
    Contains the validation status and any error messages that occurred
    during the validation process.
    
    Attributes:
        valid: Whether the validation passed.
        errors: List of error messages if validation failed.
        valid_servers: List of valid servers (for parsed validators).
    """
    
    def __init__(self, valid: bool, errors: List[str] = None, valid_servers: List = None):
        """Initialize validation result.
        
        Args:
            valid: Whether the validation passed.
            errors: Optional list of error messages.
            valid_servers: Optional list of valid servers.
        """
        self.valid = valid
        self.errors = errors or []
        self.valid_servers = valid_servers or []

RAW_VALIDATOR_REGISTRY = {}

def register_raw_validator(name):
    """Register a raw validator plugin with the given name.
    
    Args:
        name: The name to register the validator under.
        
    Returns:
        Decorator function that registers the validator class.
    """
    def decorator(cls):
        RAW_VALIDATOR_REGISTRY[name] = cls
        return cls
    return decorator

class BaseRawValidator(ABC):
    """Abstract base class for raw data validator plugins.
    
    This class provides the interface for validating raw subscription data
    before parsing. Raw validators can check data format, size limits,
    content validity, etc.
    
    Attributes:
        plugin_type: Plugin type identifier for auto-discovery and filtering.
    """
    
    plugin_type = "validator"
    
    @abstractmethod
    def validate(self, raw: bytes, context: PipelineContext) -> ValidationResult:
        """Validate raw subscription data.
        
        Args:
            raw: Raw subscription data to validate.
            context: Pipeline execution context.
            
        Returns:
            ValidationResult indicating success or failure with error details.
            
        Raises:
            NotImplementedError: If called directly on base class.
        """
        pass

@register_raw_validator("noop")
class NoOpRawValidator(BaseRawValidator):
    """No-operation validator that always passes validation.
    
    This validator is useful for testing or when no validation is needed.
    """
    
    def validate(self, raw: bytes, context: PipelineContext) -> ValidationResult:
        """Always return successful validation.
        
        Args:
            raw: Raw subscription data (ignored).
            context: Pipeline execution context (ignored).
            
        Returns:
            ValidationResult with valid=True.
        """
        return ValidationResult(valid=True)

PARSED_VALIDATOR_REGISTRY = {}

def register_parsed_validator(name):
    """Register a parsed validator plugin with the given name.
    
    Args:
        name: The name to register the validator under.
        
    Returns:
        Decorator function that registers the validator class.
    """
    def decorator(cls):
        PARSED_VALIDATOR_REGISTRY[name] = cls
        return cls
    return decorator

class BaseParsedValidator(ABC):
    """Abstract base class for parsed data validator plugins.
    
    This class provides the interface for validating parsed server data
    after parsing but before processing. Parsed validators can check
    server configurations, required fields, protocol validity, etc.
    
    Attributes:
        plugin_type: Plugin type identifier for auto-discovery and filtering.
    """
    
    plugin_type = "parsed_validator"
    
    @abstractmethod
    def validate(self, servers: list, context: PipelineContext) -> ValidationResult:
        """Validate parsed server configurations.
        
        Args:
            servers: List of parsed server objects to validate.
            context: Pipeline execution context.
            
        Returns:
            ValidationResult indicating success or failure with error details.
            
        Raises:
            NotImplementedError: If called directly on base class.
        """
        pass

class BaseValidator(ABC):
    """Abstract base class for general validator plugins.
    
    This class provides a generic interface for validator plugins used
    in template generation and plugin discovery. It serves as a base
    for both raw and parsed validators.
    
    Attributes:
        plugin_type: Plugin type identifier for auto-discovery and filtering.
    """
    
    plugin_type = "validator"
    
    @abstractmethod
    def validate(self, raw: bytes, context: PipelineContext = None):
        """Validate data with optional pipeline context.
        
        Args:
            raw: Raw data to validate.
            context: Optional pipeline execution context.
            
        Returns:
            Validation result or raises appropriate exceptions.
            
        Raises:
            NotImplementedError: If called directly on base class.
        """
        pass 