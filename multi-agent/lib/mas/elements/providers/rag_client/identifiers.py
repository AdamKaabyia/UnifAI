from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    TYPE = "rag_client"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="RAG Provider",
    description="Client for querying vector database and document metadata via RAG service",
    tags=["provider", "rag", "vector", "documents", "retrieval"],
)

