"""Global utilities package."""

from global_utils.helpers.pydantic_helpers import CoercedStr, coerce_to_str
from global_utils.docling import (
    DoclingClient,
    DoclingService,
    DoclingResponse,
    DoclingProcessingError,
)
from global_utils.embedding import (
    EmbeddingClient,
    EmbeddingService,
    EmbeddingResponse,
    EmbeddingProcessingError,
)

__all__ = [
    # Pydantic helpers
    "CoercedStr",
    "coerce_to_str",
    # Docling
    "DoclingClient",
    "DoclingService",
    "DoclingResponse",
    "DoclingProcessingError",
    # Embedding
    "EmbeddingClient",
    "EmbeddingService",
    "EmbeddingResponse",
    "EmbeddingProcessingError",
]
