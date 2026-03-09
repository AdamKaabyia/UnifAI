"""Remote Embedding Adapter - uses embedding HTTP service."""

import logging
from typing import List

import numpy as np

from global_utils.embedding import EmbeddingService

from core.health.domain.port import HealthCheckable
from core.vector.domain.embedder import EmbeddingPort, EmbeddingGenerationError

logger = logging.getLogger(__name__)


class RemoteEmbeddingAdapter(EmbeddingPort, HealthCheckable):
    """
    Adapter that uses remote embedding service for embedding generation.
    
    This adapter delegates to the EmbeddingService from global_utils.
    Use when running in environments where the embedding service is available.
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        embedding_dim: int = 384,
    ):
        """
        Initialize with an EmbeddingService instance.
        
        Args:
            embedding_service: Configured EmbeddingService for HTTP communication
            embedding_dim: Dimension of the embeddings
        """
        self._service = embedding_service
        self._embedding_dim = embedding_dim
        logger.info(f"RemoteEmbeddingAdapter initialized: dim={embedding_dim}")
    
    @property
    def is_remote(self) -> bool:
        return True

    @property
    def embedding_dim(self) -> int:
        """Get the embedding dimension."""
        return self._embedding_dim

    def encode_texts(self, texts: List[str]) -> List[np.ndarray]:
        """Encode texts using remote embedding service."""
        if not texts:
            return []
        
        try:
            embeddings = self._service.generate_embeddings(texts)
            return [np.array(e) for e in embeddings]
        except EmbeddingGenerationError:
            raise
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise EmbeddingGenerationError(str(e)) from e
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single text."""
        if not text:
            raise ValueError("Text cannot be empty")
        
        try:
            embeddings = self._service.generate_embeddings([text])
            return np.array(embeddings[0])
        except EmbeddingGenerationError:
            raise
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise EmbeddingGenerationError(str(e)) from e
    
    def test_connection(self) -> bool:
        """Test if remote embedding service is available."""
        try:
            return self._service.test_connection()
        except Exception:
            return False
