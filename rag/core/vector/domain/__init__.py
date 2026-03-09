"""Vector domain layer - ports and interfaces."""

from core.vector.domain.embedder import (
    EmbeddingPort,
    EmbeddingGenerator,
    EmbeddingGenerationError,
)

__all__ = [
    "EmbeddingPort",
    "EmbeddingGenerator",
    "EmbeddingGenerationError",
]
