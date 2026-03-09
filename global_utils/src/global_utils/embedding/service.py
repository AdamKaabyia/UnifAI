"""
Embedding Service - Business logic layer.

This service wraps the HTTP client and provides:
- Input validation
- Response parsing
- Error transformation
- Batch processing logic
"""

import logging
from typing import List, Optional

from global_utils.embedding.client import EmbeddingClient
from global_utils.embedding.models import EmbeddingResponse
from global_utils.embedding.exceptions import (
    EmbeddingProcessingError,
    EmbeddingValidationError,
)

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Business logic wrapper for embedding operations.
    
    Provides:
    - Input validation
    - Response parsing into typed DTOs
    - Error handling and transformation
    - Batch processing
    
    Example:
        client = EmbeddingClient(base_url="http://embedding:5002")
        service = EmbeddingService(client, model_name="all-MiniLM-L6-v2")
        embeddings = service.generate_embeddings(["Hello", "World"])
    """
    
    def __init__(
        self,
        client: EmbeddingClient,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        """
        Initialize the service.
        
        Args:
            client: EmbeddingClient instance for HTTP communication
            model_name: Model name to use for embedding generation
        """
        self._client = client
        self.model_name = model_name
        logger.info(f"EmbeddingService initialized: model={model_name}")
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
        
        Returns:
            List of embedding vectors (each vector is a list of floats)
            
        Raises:
            EmbeddingValidationError: If input is invalid
            EmbeddingProcessingError: If embedding generation fails
        """
        if not texts:
            raise EmbeddingValidationError("Texts list cannot be empty")
        
        try:
            logger.debug(f"Generating embeddings for {len(texts)} texts")
            raw_result = self._client.post_embeddings(
                texts=texts,
                model=self.model_name,
            )
            
            response = EmbeddingResponse.model_validate(raw_result)
            embeddings = response.extract_embeddings()
            
            if len(embeddings) != len(texts):
                raise EmbeddingProcessingError(
                    f"Expected {len(texts)} embeddings but got {len(embeddings)}: "
                    "embeddings cannot be safely aligned to their source texts"
                )
            
            logger.debug(f"Generated {len(embeddings)} embeddings")
            return embeddings
            
        except EmbeddingProcessingError:
            raise
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise EmbeddingProcessingError(f"Failed to generate embeddings: {e}")
    
    def test_connection(self) -> bool:
        """
        Test if the embedding service is accessible.
        
        Returns:
            True if service is healthy, False otherwise
        """
        return self._client.health_check()
