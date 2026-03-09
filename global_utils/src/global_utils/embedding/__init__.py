"""
Embedding module - Shared client library for embedding generation.

This module provides a client library for interacting with embedding services,
designed for cross-project reusability (RAG, multi-agent, etc.).

Architecture:
    - client.py: Pure HTTP transport layer
    - service.py: Business logic, validation, error handling
    - models.py: Request/Response DTOs (Pydantic)
    - exceptions.py: Custom domain exceptions

Usage:
    from global_utils.embedding import EmbeddingClient, EmbeddingService
    
    client = EmbeddingClient(base_url="http://embedding:5002", timeout=60)
    service = EmbeddingService(client, model_name="all-MiniLM-L6-v2")
    
    embeddings = service.generate_embeddings(["Hello", "World"])
"""

from global_utils.embedding.client import EmbeddingClient
from global_utils.embedding.service import EmbeddingService
from global_utils.embedding.models import (
    EmbeddingRequest,
    EmbeddingData,
    EmbeddingResponse,
)
from global_utils.embedding.exceptions import (
    EmbeddingError,
    EmbeddingConnectionError,
    EmbeddingProcessingError,
    EmbeddingValidationError,
    EmbeddingTimeoutError,
)

__all__ = [
    # Client & Service
    "EmbeddingClient",
    "EmbeddingService",
    # Models
    "EmbeddingRequest",
    "EmbeddingData",
    "EmbeddingResponse",
    # Exceptions
    "EmbeddingError",
    "EmbeddingConnectionError",
    "EmbeddingProcessingError",
    "EmbeddingValidationError",
    "EmbeddingTimeoutError",
]
