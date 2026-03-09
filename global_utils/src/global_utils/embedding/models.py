"""Embedding DTOs (Data Transfer Objects)."""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    """Request model for embedding generation."""
    texts: List[str]
    model: Optional[str] = None


class EmbeddingData(BaseModel):
    """Single embedding data item."""
    object: str = "embedding"
    index: int = 0
    embedding: List[float] = Field(default_factory=list)


class EmbeddingResponse(BaseModel):
    """
    Response model for embedding generation.

    Compatible with OpenAI embeddings API format.
    Pydantic v2 coerces each dict in the raw JSON response into EmbeddingData
    during model_validate, so data is always fully typed.
    """
    object: str = Field(default="list")
    data: List[EmbeddingData] = Field(default_factory=list)
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

    def extract_embeddings(self) -> List[List[float]]:
        """Extract embedding vectors from the response."""
        return [item.embedding for item in self.data]

    @property
    def embedding_count(self) -> int:
        """Get the number of embeddings in the response."""
        return len(self.data)
