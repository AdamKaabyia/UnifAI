"""Docling DTOs (Data Transfer Objects)."""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import AliasChoices, AliasPath, BaseModel, Field
from global_utils.helpers.pydantic_helpers import CoercedStr


class DoclingOutputFormat(str, Enum):
    """Supported output formats for docling document conversion."""
    MARKDOWN = "md"
    TEXT = "text"


class DoclingOptions(BaseModel):
    """Options for document conversion."""
    to_formats: List[DoclingOutputFormat] = Field(
        default_factory=lambda: [DoclingOutputFormat.MARKDOWN, DoclingOutputFormat.TEXT]
    )
    image_export_mode: Optional[str] = None
    pdf_backend: Optional[str] = None


class DoclingResponse(BaseModel):
    """
    Response model for docling conversion.
    
    Handles multiple response formats using AliasChoices:
    - Direct fields: markdown, text, content
    - Nested document: document.md_content, document.text_content
    """
    markdown: CoercedStr = Field(
        default="",
        validation_alias=AliasChoices(
            "markdown",
            "md_content",
            AliasPath("document", "md_content"),
        )
    )
    text: CoercedStr = Field(
        default="",
        validation_alias=AliasChoices(
            "text",
            "text_content",
            "content",
            AliasPath("document", "text_content"),
        )
    )
    filename: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "filename",
            AliasPath("document", "filename"),
        )
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "metadata",
            AliasPath("document", "metadata"),
        )
    )
    
    @property
    def has_content(self) -> bool:
        """Check if the response contains any extractable content."""
        return bool(
            (self.markdown and self.markdown.strip()) or 
            (self.text and self.text.strip())
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format, omitting empty/falsy values."""
        return {
            key: value
            for key, value in {
                "markdown": self.markdown,
                "text": self.text,
                "filename": self.filename,
                "metadata": self.metadata,
            }.items()
            if value
        }
