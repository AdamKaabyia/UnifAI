from mas.elements.common.base_element_spec import BaseElementSpec
from ..config import RouterDirectConditionConfig
from ..router_condition_factory import RouterDirectConditionFactory
from ..router import RouterDirectCondition
from ..identifiers import Identifier, META
from mas.core.enums import ResourceCategory
from typing import ClassVar


class RouterDirectConditionElementSpec(BaseElementSpec):
    """Element specification for Router Direct Condition."""
    category: ClassVar[ResourceCategory] = ResourceCategory.CONDITION
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = RouterDirectConditionConfig
    factory_cls = RouterDirectConditionFactory
    reads = RouterDirectCondition.READS
    tags = META.tags
    output_schema = RouterDirectCondition.get_output_schema()
