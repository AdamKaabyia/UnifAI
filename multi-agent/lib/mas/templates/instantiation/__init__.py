"""
Template instantiation module.

Handles merging user input into templates and materializing resources.
"""
from mas.templates.instantiation.models import (
    CollectedResource,
    InstantiationResult,
    MaterializationResult,
)
from mas.templates.instantiation.instantiator import TemplateInstantiator
from mas.templates.instantiation.materializer import ResourceMaterializer

# Re-export error models from central location
from mas.templates.errors import (
    MergeError,
    MergeErrorType,
    MergeFieldError,
    MaterializationError,
    MaterializationErrorType,
    MaterializationFieldError,
)

__all__ = [
    # Models
    "CollectedResource",
    "InstantiationResult",
    "MaterializationResult",
    
    # Classes
    "TemplateInstantiator",
    "ResourceMaterializer",
    
    # Error models (re-exported for convenience)
    "MergeError",
    "MergeErrorType",
    "MergeFieldError",
    "MaterializationError",
    "MaterializationErrorType",
    "MaterializationFieldError",
]
