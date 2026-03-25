"""
A2A Agent Node Specification
"""

from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import A2AAgentNodeConfig
from ..a2a_agent_node import A2AAgentNode
from ..a2a_agent_node_factory import A2AAgentNodeFactory
from ..identifiers import Identifier, META
from ..validator import A2AAgentNodeValidator
from ..card_builder import A2AAgentCardBuilder


class A2AAgentNodeElementSpec(BaseElementSpec):
    """Element specification for A2A Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = A2AAgentNodeConfig
    factory_cls = A2AAgentNodeFactory
    validator_cls = A2AAgentNodeValidator
    card_builder_cls = A2AAgentCardBuilder
    reads = A2AAgentNode.total_reads()
    writes = A2AAgentNode.total_writes()
    tags = META.tags

