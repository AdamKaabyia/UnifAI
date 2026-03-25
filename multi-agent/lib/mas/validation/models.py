"""
validation/models.py

Models for validation orchestration (service-level).
Element-level models live in elements/common/validator.py
"""

from typing import Dict

from pydantic import BaseModel, Field

from mas.elements.common.validator import ElementValidationResult


class BlueprintValidationResult(BaseModel):
    """Result of validating an entire blueprint."""
    blueprint_id: str
    is_valid: bool
    element_results: Dict[str, ElementValidationResult] = Field(default_factory=dict)
