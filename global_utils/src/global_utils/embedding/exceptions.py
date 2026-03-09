"""Embedding domain exceptions."""


class EmbeddingError(Exception):
    """Base exception for all embedding-related errors."""
    pass


class EmbeddingConnectionError(EmbeddingError):
    """Raised when the embedding service is unreachable."""
    pass


class EmbeddingProcessingError(EmbeddingError):
    """Raised when embedding generation fails."""
    pass


class EmbeddingValidationError(EmbeddingError):
    """Raised when input validation fails."""
    pass


class EmbeddingTimeoutError(EmbeddingError):
    """Raised when a request times out."""
    pass
