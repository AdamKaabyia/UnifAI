from mas.elements.common.base_element_spec import BaseElementSpec
from ..mock_factory import MockLLMFactory
from mas.core.enums import ResourceCategory
from ..config import MockLLMConfig
from ..identifiers import Identifier, META


class MockLLMElementSpec(BaseElementSpec):
    """Element specification for Mock LLM - testing and development."""

    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = MockLLMConfig
    factory_cls = MockLLMFactory  # Factory not defined for mock LLM
    tags = META.tags
