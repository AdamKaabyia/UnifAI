from typing import ClassVar
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import RagProviderConfig
from ..rag_provider_factory import RagProviderFactory
from ..identifiers import Identifier, META


class RagProviderElementSpec(BaseElementSpec):
    """
    Element specification for RAG Provider.

    Provides vector database query and document retrieval capabilities
    via the RAG service.
    """

    category: ClassVar[ResourceCategory] = ResourceCategory.PROVIDER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = RagProviderConfig
    factory_cls = RagProviderFactory
    tags = META.tags

