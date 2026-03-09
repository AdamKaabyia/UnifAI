"""Local Embedding Adapter - uses SentenceTransformers directly."""

import logging
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from core.health.domain.port import HealthCheckable
from core.vector.domain.embedder import EmbeddingPort, EmbeddingGenerationError

logger = logging.getLogger(__name__)


class LocalEmbeddingAdapter(EmbeddingPort, HealthCheckable):
    """
    Adapter that uses local SentenceTransformers for embedding generation.
    
    This adapter loads a SentenceTransformer model and generates embeddings locally.
    Use when running in environments where the embedding service is not available.
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
    ):
        """
        Initialize with a SentenceTransformer model.

        Args:
            model_name: Name of the SentenceTransformer model
            device: Device to run on ("cuda", "cpu", or None for auto-detect)
        """
        logger.info(f"Loading SentenceTransformer model: {model_name}")
        self._model = SentenceTransformer(model_name, device=device)
        dim = self._model.get_sentence_embedding_dimension()
        if dim is None:
            raise ValueError(
                f"Model '{model_name}' does not report an embedding dimension. "
                "Ensure the model has a pooling layer that exposes its output size."
            )
        self._embedding_dim: int = dim
        logger.info(
            f"LocalEmbeddingAdapter initialized: model={model_name}, "
            f"dim={self._embedding_dim}"
        )
    
    @property
    def is_remote(self) -> bool:
        return False

    @property
    def embedding_dim(self) -> int:
        """Get the embedding dimension."""
        return self._embedding_dim

    def encode_texts(self, texts: List[str]) -> List[np.ndarray]:
        """Encode texts using local SentenceTransformer model."""
        if not texts:
            return []
        
        try:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            
            if isinstance(embeddings, np.ndarray) and embeddings.ndim == 2:
                return [embeddings[i] for i in range(len(embeddings))]
            return list(embeddings)
        except EmbeddingGenerationError:
            raise
        except Exception as e:
            logger.error(f"Error encoding texts locally: {e}")
            raise EmbeddingGenerationError(str(e)) from e
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single text."""
        if not text:
            raise ValueError("Text cannot be empty")
        
        try:
            return self._model.encode(text)
        except EmbeddingGenerationError:
            raise
        except Exception as e:
            logger.error(f"Error encoding text locally: {e}")
            raise EmbeddingGenerationError(str(e)) from e
    
    def test_connection(self) -> bool:
        """Local adapter is always available."""
        return True
