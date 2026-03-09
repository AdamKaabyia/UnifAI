"""Embedding domain - ports and exceptions for embedding generation."""

import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class EmbeddingPort(ABC):
    """
    Abstract interface for embedding generation.
    
    This port defines the contract for generating vector embeddings from text.
    Implementations can be local (SentenceTransformers) or remote (HTTP service).
    """

    @property
    @abstractmethod
    def is_remote(self) -> bool:
        """True if this adapter calls an external service; False if purely local."""
        ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Get the dimension of generated embeddings."""
        pass
    
    @abstractmethod
    def encode_texts(self, texts: List[str]) -> List[np.ndarray]:
        """
        Encode multiple texts into embeddings.
        
        Args:
            texts: List of text strings to encode
            
        Returns:
            List of embedding vectors as numpy arrays
        """
        pass
    
    @abstractmethod
    def encode_single(self, text: str) -> np.ndarray:
        """
        Encode a single text into an embedding.
        
        Args:
            text: Text string to encode
            
        Returns:
            Embedding vector as numpy array
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the embedding generator is available.
        
        Returns:
            True if available, False otherwise
        """
        pass


class EmbeddingGenerator(ABC):
    """
    Application-level port for embedding generation with batching.
    
    Consumers depend on this ABC; concrete implementation
    (batch processing, error recovery, logging) lives in infrastructure.
    """

    @property
    @abstractmethod
    def is_remote(self) -> bool:
        """True if the underlying adapter calls an external service."""
        ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Get the embedding dimension."""
        pass
    
    @abstractmethod
    def generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for all chunks.
        
        Args:
            chunks: List of chunks with text and metadata
            
        Returns:
            List of chunks with embeddings added
        """
        pass
    
    @abstractmethod
    def generate_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate an embedding for a search query.
        
        Args:
            query: Search query text
            
        Returns:
            Embedding vector for the query
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the embedding service is available.
        
        Returns:
            True if available, False otherwise
        """
        pass


class EmbeddingGenerationError(Exception):
    """Raised when embedding generation fails."""
    pass
