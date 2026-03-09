"""
Docling HTTP Client - Pure transport layer.

This client handles only HTTP communication with the docling service.
Business logic, validation, and error transformation are in the service layer.
"""

import os
import logging
from typing import Dict, Any, Optional, List

import httpx

from global_utils.docling.exceptions import (
    DoclingConnectionError,
    DoclingTimeoutError,
)

logger = logging.getLogger(__name__)


class DoclingClient:
    """
    Pure HTTP client for docling service.
    
    Handles only transport concerns:
    - HTTP requests/responses
    - Connection management
    - Timeout handling
    
    Example:
        client = DoclingClient(
            base_url="http://docling-service:5001",
            timeout=300,
        )
        raw_response = client.post_file("/path/to/doc.pdf", options={...})
    """
    
    def __init__(
        self, 
        base_url: str,
        timeout: int = 300,
    ):
        """
        Initialize the HTTP client.
        
        Args:
            base_url: Base URL for the docling service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
        )
        logger.info(f"DoclingClient initialized: {self.base_url}, timeout={self.timeout}s")
    
    def post_file(
        self, 
        file_path: str, 
        to_formats: List[str],
        image_export_mode: Optional[str] = None,
        pdf_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST a file to the docling service for conversion.
        
        Args:
            file_path: Path to the file to convert
            to_formats: List of output formats (e.g., ["md", "text"])
            image_export_mode: Mode for image export (e.g., "placeholder")
            pdf_backend: PDF parsing backend (e.g., "pypdfium2")
        
        Returns:
            Raw JSON response from the service
            
        Raises:
            DoclingConnectionError: If service is unreachable
            DoclingTimeoutError: If request times out
        """
        url = "/v1/convert/file"
        
        try:
            with open(file_path, 'rb') as f:
                # httpx multipart format: all fields in 'files' parameter
                # File: (field_name, (filename, content, content_type))
                # Form field: (field_name, (None, value))
                multipart_data = [
                    ('files', (os.path.basename(file_path), f, 'application/octet-stream')),
                ]
                
                for fmt in to_formats:
                    multipart_data.append(('to_formats', (None, fmt)))
                
                if image_export_mode:
                    multipart_data.append(('image_export_mode', (None, image_export_mode)))
                
                if pdf_backend:
                    multipart_data.append(('pdf_backend', (None, pdf_backend)))
                
                response = self._client.post(url, files=multipart_data)
                response.raise_for_status()
                return response.json()
                
        except httpx.ConnectError as e:
            raise DoclingConnectionError(f"Cannot connect to docling service: {e}")
        except httpx.TimeoutException as e:
            raise DoclingTimeoutError(f"Request timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise DoclingConnectionError(f"HTTP error {e.response.status_code}: {e}")
        except httpx.TransportError as e:
            raise DoclingConnectionError(f"Transport error communicating with docling service: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in post_file: {e}", exc_info=True)
            raise

    def post_url(
        self, 
        document_url: str, 
        to_formats: List[str],
        image_export_mode: Optional[str] = None,
        pdf_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST a URL to the docling service for conversion.
        
        Args:
            document_url: URL of the document to convert
            to_formats: List of output formats
            image_export_mode: Mode for image export
            pdf_backend: PDF parsing backend
        
        Returns:
            Raw JSON response from the service
            
        Raises:
            DoclingConnectionError: If service is unreachable
            DoclingTimeoutError: If request times out
        """
        url = "/v1/convert/source"
        
        try:
            payload = {
                "sources": [{"kind": "http", "url": document_url}],
                "to_formats": to_formats
            }
            
            if image_export_mode:
                payload["image_export_mode"] = image_export_mode
            
            if pdf_backend:
                payload["pdf_backend"] = pdf_backend
            
            response = self._client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.ConnectError as e:
            raise DoclingConnectionError(f"Cannot connect to docling service: {e}")
        except httpx.TimeoutException as e:
            raise DoclingTimeoutError(f"Request timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise DoclingConnectionError(f"HTTP error {e.response.status_code}: {e}")
        except httpx.TransportError as e:
            raise DoclingConnectionError(f"Transport error communicating with docling service: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in post_url: {e}", exc_info=True)
            raise

    def health_check(self) -> bool:
        """
        Check if the docling service is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self._client.get("/health", timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
