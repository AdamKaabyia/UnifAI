"""
Docling Service - Business logic layer.

This service wraps the HTTP client and provides:
- Input validation
- Response parsing
- Error transformation
- Business logic for document processing
"""

import os
import logging
from typing import Optional

from global_utils.docling.client import DoclingClient
from global_utils.docling.models import DoclingOutputFormat, DoclingResponse
from global_utils.docling.exceptions import (
    DoclingProcessingError,
    DoclingValidationError,
)

logger = logging.getLogger(__name__)


class DoclingService:
    """
    Business logic wrapper for docling operations.
    
    Provides:
    - File/URL validation
    - Response parsing into typed DTOs
    - Error handling and transformation
    
    Example:
        client = DoclingClient(base_url="http://docling:5001")
        service = DoclingService(client, image_export_mode="placeholder")
        response = service.process_file("/path/to/document.pdf")
        print(response.markdown)
    """
    
    def __init__(
        self,
        client: DoclingClient,
        image_export_mode: Optional[str] = None,
        pdf_backend: Optional[str] = None,
        default_formats: Optional[list] = None,
    ):
        """
        Initialize the service.
        
        Args:
            client: DoclingClient instance for HTTP communication
            image_export_mode: Default mode for image export (e.g., "placeholder")
            pdf_backend: Default PDF backend (e.g., "pypdfium2")
            default_formats: Default output formats (defaults to MARKDOWN and TEXT)
        """
        self._client = client
        self.image_export_mode = image_export_mode
        self.pdf_backend = pdf_backend
        self.default_formats = default_formats or [DoclingOutputFormat.MARKDOWN, DoclingOutputFormat.TEXT]
        logger.info(
            f"DoclingService initialized: image_mode={image_export_mode}, "
            f"pdf_backend={pdf_backend}"
        )
    
    def process_file(
        self, 
        file_path: str, 
    ) -> DoclingResponse:
        """
        Process a local file through the docling service.
        
        Args:
            file_path: Path to the file to process
        
        Returns:
            DoclingResponse with extracted content
            
        Raises:
            DoclingValidationError: If file doesn't exist or is invalid
            DoclingProcessingError: If processing fails
        """
        # Validate file exists
        if not os.path.exists(file_path):
            raise DoclingValidationError(f"File not found: {file_path}")
        
        formats = self.default_formats
        
        try:
            logger.info(f"Processing file: {file_path}")
            raw_result = self._client.post_file(
                file_path=file_path,
                to_formats=formats,
                image_export_mode=self.image_export_mode,
                pdf_backend=self.pdf_backend,
            )
            
            response = DoclingResponse.model_validate(raw_result)
            
            if not response.has_content:
                raise DoclingProcessingError(
                    f"No content extracted from '{os.path.basename(file_path)}'"
                )
            
            logger.info(f"Successfully processed: {file_path}")
            return response
            
        except DoclingProcessingError:
            raise
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise DoclingProcessingError(
                f"Failed to process '{os.path.basename(file_path)}': {e}"
            )
    
    def process_url(
        self, 
        document_url: str, 
    ) -> DoclingResponse:
        """
        Process a document from URL through the docling service.
        
        Note: This functionality exists but is not yet fully implemented.
        URL validation (format, scheme, network accessibility) and richer
        error handling are planned for future iterations.
        
        Args:
            document_url: HTTP/HTTPS URL of the document. Must be accessible
                from the Docling service's network (e.g. public URLs like arXiv,
                S3 presigned URLs, or internal URLs reachable from the Docling
                pod). file:// and localhost URLs are not supported.
        
        Returns:
            DoclingResponse with extracted content
            
        Raises:
            DoclingValidationError: If URL is empty or invalid
            DoclingProcessingError: If processing fails
        """
        # TODO: Add full URL validation when network document ingestion is officially supported:
        #   - Validate URL format and scheme (must be http:// or https://)
        #   - Check that the URL is reachable from the Docling service's network
        if not document_url:
            raise DoclingValidationError("Document URL cannot be empty")
        
        formats = self.default_formats
        
        try:
            logger.info(f"Processing URL: {document_url}")
            raw_result = self._client.post_url(
                document_url=document_url,
                to_formats=formats,
                image_export_mode=self.image_export_mode,
                pdf_backend=self.pdf_backend,
            )
            
            response = DoclingResponse.model_validate(raw_result)
            
            if not response.has_content:
                raise DoclingProcessingError(
                    f"No content extracted from URL '{document_url}'"
                )
            
            logger.info(f"Successfully processed URL: {document_url}")
            return response
            
        except DoclingProcessingError:
            raise
        except Exception as e:
            logger.error(f"Error processing URL {document_url}: {e}")
            raise DoclingProcessingError(
                f"Failed to process URL '{document_url}': {e}"
            )
    
    def test_connection(self) -> bool:
        """
        Test if the docling service is accessible.
        
        Returns:
            True if service is healthy, False otherwise
        """
        return self._client.health_check()
