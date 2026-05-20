from mas.core.enums import ResourceCategory
from mas.elements.common.base_element_spec import BaseElementSpec
from ..config import OAuthClientConfig
from ..oauth_client_factory import OAuthClientFactory
from ..identifiers import Identifier, META


class OAuthClientElementSpec(BaseElementSpec):
    category = ResourceCategory.AUTH
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = OAuthClientConfig
    factory_cls = OAuthClientFactory
    tags = list(META.tags)
