"""Template models package."""

from mas.templates.models.template import (
    Template,
    TemplateSummary,
    PlaceholderMeta,
    PlaceholderPointer,
    ResourcePlaceholders,
    CategoryPlaceholders,
    TemplateMetadata,
    InputValidationResult,
    MaterializeResult,
)

__all__ = [
    # Template core models
    "Template",
    "TemplateSummary",
    "PlaceholderMeta",
    "PlaceholderPointer",
    "ResourcePlaceholders",
    "CategoryPlaceholders",
    "TemplateMetadata",
    # Result models
    "InputValidationResult",
    "MaterializeResult",
]
