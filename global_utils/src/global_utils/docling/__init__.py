"""
Docling module - Shared client library for document processing.

This module provides a client library for interacting with docling services,
designed for cross-project reusability (RAG, multi-agent, etc.).

Architecture:
    - client.py: Pure HTTP transport layer
    - service.py: Business logic, validation, error handling
    - models.py: Request/Response DTOs (Pydantic)
    - exceptions.py: Custom domain exceptions

Usage:
    from global_utils.docling import DoclingClient, DoclingService
    
    client = DoclingClient(base_url="http://docling:5001", timeout=300)
    service = DoclingService(client, image_export_mode="placeholder")
    
    response = service.process_file("/path/to/document.pdf")
    print(response.markdown)
"""

from global_utils.docling.client import DoclingClient
from global_utils.docling.service import DoclingService
from global_utils.docling.models import (
    DoclingOptions,
    DoclingResponse,
)
from global_utils.docling.exceptions import (
    DoclingError,
    DoclingConnectionError,
    DoclingProcessingError,
    DoclingValidationError,
    DoclingTimeoutError,
)

__all__ = [
    # Client & Service
    "DoclingClient",
    "DoclingService",
    # Models
    "DoclingOptions",
    "DoclingResponse",
    # Exceptions
    "DoclingError",
    "DoclingConnectionError",
    "DoclingProcessingError",
    "DoclingValidationError",
    "DoclingTimeoutError",
]
