from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import WebFetchToolConfig
from ..identifiers import Identifier, META
from ..web_fetch_factory import WebFetchToolFactory


class WebFetchToolElementSpec(BaseElementSpec):

    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = WebFetchToolConfig
    factory_cls = WebFetchToolFactory
    tags = META.tags
