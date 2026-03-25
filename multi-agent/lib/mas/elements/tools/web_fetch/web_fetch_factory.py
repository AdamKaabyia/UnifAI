from typing import Any

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import WebFetchToolConfig
from .identifiers import Identifier
from .web_fetch import WebFetchTool


class WebFetchToolFactory(BaseFactory[WebFetchToolConfig, WebFetchTool]):

    def accepts(self, cfg: WebFetchToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: WebFetchToolConfig, **kwargs: Any) -> WebFetchTool:
        try:
            return WebFetchTool()
        except Exception as e:
            raise PluginConfigurationError(
                f"WebFetchToolFactory.create() failed: {e}",
                cfg.dict(),
            ) from e
