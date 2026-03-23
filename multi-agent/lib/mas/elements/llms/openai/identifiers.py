from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the OpenAI LLM."""
    TYPE = "openai"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="OpenAI LLM",
    description="Official OpenAI API configuration for LLM interactions",
    tags=["llm", "openai", "api", "chat"],
)
