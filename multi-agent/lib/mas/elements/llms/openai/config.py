from typing import Literal, Dict, Any
from pydantic import Field, HttpUrl
from ..common.base_config import BaseLLMConfig
from .identifiers import Identifier


class OpenAIConfig(BaseLLMConfig):
    """
    Configuration for the official OpenAI API.
    Extracted from legacy structure and cleaned up.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    temperature: float = Field(
        0.7, ge=0.0, le=1.0,
        description="Sampling temperature"
    )
    max_tokens: int = Field(
        4096,
        description="Maximum number of tokens to generate"
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific kwargs passed through as is"
    )
