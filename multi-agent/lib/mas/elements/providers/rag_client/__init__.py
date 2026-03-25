"""
RAG Client Provider

This package provides synchronous RAG service integration for vector database
queries and document retrieval.
"""

from .rag_provider import RagProvider
from .rag_provider_factory import RagProviderFactory
from .client import RagClient, RagClientError, RagConnectionError
from .config import RagProviderConfig
from .identifiers import Identifier, META
from .models import (
    TagOption,
    AvailableTagsResponse,
    DocumentInfo,
    AvailableDocsResponse,
    QueryMatchResult,
    QueryMatchResponse,
    HealthResponse,
)

__all__ = [
    "RagProvider",
    "RagProviderFactory",
    "RagClient",
    "RagClientError",
    "RagConnectionError",
    "RagProviderConfig",
    "Identifier",
    "META",
    "TagOption",
    "AvailableTagsResponse",
    "DocumentInfo",
    "AvailableDocsResponse",
    "QueryMatchResult",
    "QueryMatchResponse",
    "HealthResponse",
]

