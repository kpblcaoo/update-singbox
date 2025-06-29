"""Exclusion management module."""

from ..interfaces import ExclusionManagerInterface
from .manager import ExclusionManager
from .models import ExclusionEntry, ExclusionList

# Clean API exports
__all__ = [
    "ExclusionManager",
    "ExclusionManagerInterface",
    "ExclusionEntry",
    "ExclusionList",
]

# Convenience function for backward compatibility
def get_default_manager() -> ExclusionManager:
    """Get default ExclusionManager instance.
    
    Returns:
        Default ExclusionManager singleton
    """
    return ExclusionManager.default() 