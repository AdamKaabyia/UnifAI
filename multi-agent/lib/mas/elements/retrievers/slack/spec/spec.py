from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import SlackRetrieverConfig
from ..slack_retriever_factory import SlackRetrieverFactory
from ..identifiers import Identifier, META
from mas.elements.retrievers.common.card_builder import RetrieverCardBuilder


class SlackRetrieverElementSpec(BaseElementSpec):
    """Element specification for Slack Retriever."""

    category = ResourceCategory.RETRIEVER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = SlackRetrieverConfig
    factory_cls = SlackRetrieverFactory
    tags = META.tags
    card_builder_cls = RetrieverCardBuilder
