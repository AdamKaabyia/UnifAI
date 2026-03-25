from typing import Literal

from mas.elements.tools.common.base_config import BaseToolConfig
from .identifiers import Identifier


class WebFetchToolConfig(BaseToolConfig):
    type: Literal[Identifier.TYPE] = Identifier.TYPE
