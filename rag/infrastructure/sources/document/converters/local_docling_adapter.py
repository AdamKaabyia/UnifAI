"""Local Docling Adapter - uses docling library directly."""

import os
import logging
from typing import Dict, Any

from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from pypdfium2 import PdfiumError

from core.data_sources.types.document.domain.document_converter import (
    ConversionResult,
    DocumentConverterPort,
    DocumentConversionError,
)

logger = logging.getLogger(__name__)


class LocalDoclingAdapter(DocumentConverterPort):
    """
    Adapter that uses the local docling library for document conversion.
    
    This adapter loads the docling library and processes documents locally.
    Use when running in environments where the docling service is not available.
    """
    
    def __init__(self):
        """Initialize the local docling converter."""
        pdf_pipeline_options = PdfPipelineOptions(do_ocr=False)
        pdf_format_option = PdfFormatOption(
            pipeline_options=pdf_pipeline_options,
            backend=PyPdfiumDocumentBackend
        )
        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: pdf_format_option}
        )
        logger.info("LocalDoclingAdapter initialized")
    
    @property
    def is_remote(self) -> bool:
        return False

    def convert_file(self, file_path: str) -> ConversionResult:
        """Convert a local file using docling library."""
        if not os.path.exists(file_path):
            raise DocumentConversionError(f"File not found: {file_path}")
        
        try:
            logger.info(f"Converting file locally: {file_path}")
            result = self._converter.convert(file_path)
            
            text_content = result.document.export_to_text()
            
            if not text_content or not text_content.strip():
                raise DocumentConversionError(
                    f"No content extracted from '{os.path.basename(file_path)}'"
                )
            
            return ConversionResult(
                text=text_content,
                markdown=result.document.export_to_markdown(),
                metadata=self._extract_metadata(result),
            )
            
        except DocumentConversionError:
            raise
        except PdfiumError:
            raise DocumentConversionError(
                "The PDF appears to be corrupted or invalid."
            )
        except Exception as e:
            logger.error(f"Error converting file {file_path}: {e}")
            raise DocumentConversionError(str(e))
    
    def convert_url(self, document_url: str) -> ConversionResult:
        """Convert a document from URL using docling library."""
        try:
            logger.info(f"Converting URL locally: {document_url}")
            result = self._converter.convert(document_url)
            
            text_content = result.document.export_to_text()
            
            if not text_content or not text_content.strip():
                raise DocumentConversionError(
                    f"No content extracted from URL '{document_url}'"
                )
            
            return ConversionResult(
                text=text_content,
                markdown=result.document.export_to_markdown(),
                metadata=self._extract_metadata(result),
            )
            
        except DocumentConversionError:
            raise
        except PdfiumError:
            raise DocumentConversionError(
                "The PDF at the URL appears to be corrupted or invalid."
            )
        except Exception as e:
            logger.error(f"Error converting URL {document_url}: {e}")
            raise DocumentConversionError(str(e))
    
    def test_connection(self) -> bool:
        """Local adapter is always available."""
        return True
    
    def _extract_metadata(self, result) -> Dict[str, Any]:
        """Extract metadata from docling conversion result."""
        metadata = {}
        doc = result.document
        
        try:
            if hasattr(doc, "metadata") and doc.metadata:
                metadata.update(doc.metadata)
            
            metadata["title"] = doc.title if hasattr(doc, "title") else "Untitled"
            metadata["page_count"] = len(doc.pages) if hasattr(doc, "pages") else 1
            
            text = doc.export_to_text()
            metadata["character_count"] = len(text)
            metadata["word_count"] = len(text.split())
            
            # Extract table information if available
            if hasattr(result, "tables") and result.tables:
                metadata["table_count"] = len(result.tables)
            
            # Extract image information if available
            if hasattr(result, "images") and result.images:
                metadata["image_count"] = len(result.images)
                
        except Exception as e:
            logger.warning(f"Error extracting metadata: {e}")
        
        return metadata
