from typing import ClassVar
from mas.core.enums import ResourceCategory
from mas.elements.common.base_element_spec import BaseElementSpec
from ..threshold_factory import ThresholdConditionFactory
from ..config import ThresholdConditionConfig
from ..threshold import ThresholdCondition
from ..identifiers import Identifier, META


class ThresholdConditionElementSpec(BaseElementSpec):
    """Element specification for Threshold Condition."""
    category: ClassVar[ResourceCategory] = ResourceCategory.CONDITION
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = ThresholdConditionConfig
    factory_cls = ThresholdConditionFactory
    tags = META.tags
    output_schema = ThresholdCondition.get_output_schema()
