"""Document converter port - domain interface for document conversion."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ConversionResult:
    """Domain model representing the output of a document conversion."""

    text: str = ""
    markdown: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentConverterPort(ABC):
    """
    Abstract interface for document conversion.

    This port defines the contract for converting documents to text/markdown.
    Implementations can be local (docling library) or remote (HTTP service).
    """

    @property
    @abstractmethod
    def is_remote(self) -> bool:
        """True if this adapter calls an external service; False if purely local."""
        ...

    @abstractmethod
    def convert_file(self, file_path: str) -> ConversionResult:
        """
        Convert a local file to text/markdown.

        Args:
            file_path: Path to the file to convert

        Returns:
            ConversionResult with text, markdown, and metadata

        Raises:
            DocumentConversionError: If conversion fails
        """
        pass

    @abstractmethod
    def convert_url(self, document_url: str) -> ConversionResult:
        """
        Convert a document from URL to text/markdown.

        Args:
            document_url: URL of the document to convert

        Returns:
            ConversionResult with text, markdown, and metadata

        Raises:
            DocumentConversionError: If conversion fails
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the converter is available.

        Returns:
            True if available, False otherwise
        """
        pass


class DocumentConversionError(Exception):
    """Raised when document conversion fails."""
    pass
