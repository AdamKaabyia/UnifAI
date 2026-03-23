from mas.elements.common.base_element_spec import BaseElementSpec
from ..config import RouterBooleanConditionConfig
from ..router_condition_factory import RouterBooleanConditionFactory
from ..router import RouterBooleanCondition
from ..identifiers import Identifier, META
from mas.core.enums import ResourceCategory
from typing import ClassVar


class RouterBooleanConditionElementSpec(BaseElementSpec):
    """Element specification for Router Boolean Condition."""
    category: ClassVar[ResourceCategory] = ResourceCategory.CONDITION
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = RouterBooleanConditionConfig
    factory_cls = RouterBooleanConditionFactory
    tags = META.tags
    reads = RouterBooleanCondition.READS
    output_schema = RouterBooleanCondition.get_output_schema()