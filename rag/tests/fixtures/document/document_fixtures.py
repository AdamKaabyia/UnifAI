"""
Document fixtures for RAG end-to-end tests.

Provides pytest fixtures for:
- document_factory    - DocumentFactory instance
- sample_pdf_document - single (doc_id, filename, bytes) tuple
- batch_pdf_documents - list of (doc_id, filename, bytes) tuples sized by config
"""

import pytest
from typing import List, Tuple

from tests.factories.document_factory import DocumentFactory
from tests.fixtures.common.api_fixtures import RagTestConfig


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def document_factory() -> DocumentFactory:
    """Provide a DocumentFactory instance for the test session."""
    return DocumentFactory()


@pytest.fixture
def sample_pdf_document() -> Tuple[int, str, bytes]:
    """Generate a single PDF document for lightweight tests.

    Returns:
        Tuple of (doc_id=1, filename, pdf_bytes).
    """
    filename = DocumentFactory.make_filename(1, prefix="test_doc")
    pdf_bytes = DocumentFactory.create_pdf(1, filename)
    return 1, filename, pdf_bytes


@pytest.fixture(scope="session")
def batch_pdf_documents(rag_config: RagTestConfig) -> List[Tuple[int, str, bytes]]:
    """Generate the full batch of PDF documents defined by rag_config.

    Documents are generated once per session and shared across tests to
    avoid expensive PDF re-generation.

    When ``rag_config.randomize`` is enabled the document count is drawn
    from ``(min_documents, max_documents)`` and each document receives a
    random page count from ``(min_pages_per_doc, max_pages_per_doc)``.

    Returns:
        List of (doc_id, filename, pdf_bytes) tuples.
    """
    import random

    if rag_config.randomize:
        count = random.randint(
            rag_config.min_documents, rag_config.max_documents,
        )
        pages = (rag_config.min_pages_per_doc, rag_config.max_pages_per_doc)
    else:
        count = rag_config.num_documents
        pages = rag_config.pages_per_doc

    return DocumentFactory.create_batch(
        count=count,
        start_id=1,
        prefix="stress_test_doc",
        pages=pages,
        profile=rag_config.profile,
    )
