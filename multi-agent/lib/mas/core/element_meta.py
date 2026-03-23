"""
core/element_meta.py

Universal metadata for element configurations.

Used by:
- Card building (ElementCardService)
- Validation (ElementValidationService)
- Any service that needs to process element configs
"""

from typing import List, Any

from pydantic import BaseModel, Field, ConfigDict

from mas.core.enums import ResourceCategory


class ElementConfigMeta(BaseModel):
    """
    Universal metadata about an element configuration.

    This is a plain data object that any module can create from its own
    data structures (BlueprintSpec, ResourceDoc, SessionRegistry, etc.)

    Used as input for:
    - ElementCardService.build_all_cards()
    - ElementValidationService.validate_ordered()
    """
    rid: str
    category: ResourceCategory
    type_key: str
    name: str
    config: Any
    dependency_rids: List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
