"""Document domain layer - ports, models, and interfaces."""

from core.data_sources.types.document.domain.document_converter import (
    ConversionResult,
    DocumentConverterPort,
    DocumentConversionError,
)
from core.data_sources.types.document.domain.processed_document import ProcessedDocument
from core.data_sources.types.document.domain.processor import DocumentProcessor

__all__ = [
    "ConversionResult",
    "DocumentConverterPort",
    "DocumentConversionError",
    "ProcessedDocument",
    "DocumentProcessor",
]
