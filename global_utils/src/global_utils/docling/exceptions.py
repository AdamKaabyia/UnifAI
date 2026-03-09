"""Docling domain exceptions."""


class DoclingError(Exception):
    """Base exception for all docling-related errors."""
    pass


class DoclingConnectionError(DoclingError):
    """Raised when the docling service is unreachable."""
    pass


class DoclingProcessingError(DoclingError):
    """Raised when document processing fails."""
    pass


class DoclingValidationError(DoclingError):
    """Raised when input validation fails."""
    pass


class DoclingTimeoutError(DoclingError):
    """Raised when a request times out."""
    pass
