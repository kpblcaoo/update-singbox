"""JSON API protocol definitions for sboxmgr <-> sboxagent communication.

This module defines the contract for communication between sboxmgr (Python) and
sboxagent (Go/Ruby/other). All communication happens through JSON messages with
well-defined schemas.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class AgentCommand(str, Enum):
    """Available sboxagent commands."""
    VALIDATE = "validate"
    INSTALL = "install"
    CHECK = "check"
    VERSION = "version"


class ClientType(str, Enum):
    """Supported VPN client types."""
    SING_BOX = "sing-box"
    XRAY = "xray"
    CLASH = "clash"
    HYSTERIA = "hysteria"
    MIHOMO = "mihomo"


class AgentRequest(BaseModel):
    """Base class for all agent requests.
    
    This defines the common structure for all JSON requests sent to sboxagent.
    
    Args:
        command: The agent command to execute
        version: API version for compatibility
        trace_id: Optional trace ID for request tracking
    """
    
    command: AgentCommand = Field(..., description="Command to execute")
    version: str = Field(default="1.0", description="API version")
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking")


class ValidationRequest(AgentRequest):
    """Request to validate a configuration file.
    
    Args:
        command: Must be "validate"
        config_path: Path to configuration file to validate
        client_type: Optional client type hint for validation
        strict: Whether to perform strict validation
    
    Example:
        >>> req = ValidationRequest(
        ...     command=AgentCommand.VALIDATE,
        ...     config_path="/path/to/config.json",
        ...     client_type=ClientType.SING_BOX
        ... )
    """
    
    command: AgentCommand = Field(default=AgentCommand.VALIDATE)
    config_path: str = Field(..., description="Path to configuration file")
    client_type: Optional[ClientType] = Field(None, description="Client type hint")
    strict: bool = Field(default=True, description="Strict validation mode")


class InstallRequest(AgentRequest):
    """Request to install a VPN client.
    
    Args:
        command: Must be "install"
        client_type: Type of client to install
        version: Optional specific version to install
        force: Whether to force reinstall if already present
    
    Example:
        >>> req = InstallRequest(
        ...     command=AgentCommand.INSTALL,
        ...     client_type=ClientType.SING_BOX,
        ...     version="1.8.0"
        ... )
    """
    
    command: AgentCommand = Field(default=AgentCommand.INSTALL)
    client_type: ClientType = Field(..., description="Client type to install")
    version: Optional[str] = Field(None, description="Specific version to install")
    force: bool = Field(default=False, description="Force reinstall")


class CheckRequest(AgentRequest):
    """Request to check client availability and status.
    
    Args:
        command: Must be "check"
        client_type: Optional specific client to check
    """
    
    command: AgentCommand = Field(default=AgentCommand.CHECK)
    client_type: Optional[ClientType] = Field(None, description="Client to check")


class AgentResponse(BaseModel):
    """Base class for all agent responses.
    
    This defines the common structure for all JSON responses from sboxagent.
    
    Args:
        success: Whether the operation succeeded
        message: Human-readable message
        trace_id: Trace ID from request (if provided)
        error_code: Optional error code for programmatic handling
    """
    
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Human-readable message")
    trace_id: Optional[str] = Field(None, description="Trace ID from request")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")


class ValidationResponse(AgentResponse):
    """Response from configuration validation.
    
    Args:
        success: Whether validation passed
        message: Validation result message
        errors: List of validation errors (if any)
        client_detected: Detected client type from config
        client_version: Detected client version (if available)
    
    Example:
        >>> resp = ValidationResponse(
        ...     success=False,
        ...     message="Configuration validation failed",
        ...     errors=["Missing required field: outbounds"],
        ...     client_detected=ClientType.SING_BOX
        ... )
    """
    
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    client_detected: Optional[ClientType] = Field(None, description="Detected client type")
    client_version: Optional[str] = Field(None, description="Detected client version")


class InstallResponse(AgentResponse):
    """Response from client installation.
    
    Args:
        success: Whether installation succeeded
        message: Installation result message
        client_type: Type of client that was installed
        version: Version that was installed
        binary_path: Path to installed binary
    """
    
    client_type: Optional[ClientType] = Field(None, description="Installed client type")
    version: Optional[str] = Field(None, description="Installed version")
    binary_path: Optional[str] = Field(None, description="Path to installed binary")


class CheckResponse(AgentResponse):
    """Response from client availability check.
    
    Args:
        success: Whether check completed successfully
        message: Check result message
        clients: Status of available clients
    """
    
    clients: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Client availability status"
    )


# Type aliases for convenience
AnyRequest = Union[ValidationRequest, InstallRequest, CheckRequest, AgentRequest]
AnyResponse = Union[ValidationResponse, InstallResponse, CheckResponse, AgentResponse] 