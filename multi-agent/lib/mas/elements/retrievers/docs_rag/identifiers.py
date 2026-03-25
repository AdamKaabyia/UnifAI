from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    TYPE = "docs_rag"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Docs RAG Retriever",
    description="Retrieves document passages via RAG vector database",
    tags=["retriever", "docs", "rag", "vector", "search"],
)

