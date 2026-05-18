"""
Global test configuration and shared fixtures for RAG tests.

This module imports ALL fixtures from the organised structure and provides
pytest configuration (CLI options, marker registration, auto-marking).

ALL TESTS SHOULD:
- Use fixtures from tests/fixtures/
- Use factories from tests/factories/
- Inherit from base classes in tests/base/ where applicable
- Be organised under tests/{e2e,integration,unit}/
"""

import sys
import os
import pytest

# Add the rag/ directory to Python path so that ``from rag.core...`` works
# as well as ``from tests...`` relative imports.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# =============================================================================
# IMPORT ALL FIXTURES FROM ORGANISED STRUCTURE
# =============================================================================

# Common fixtures – API config, Celery monitor
from tests.fixtures.common.api_fixtures import (  # noqa: F401  (re-export)
    RagTestConfig,
    rag_config,
    celery_monitor,
)

# Document fixtures – PDF generation
from tests.fixtures.document.document_fixtures import (  # noqa: F401
    document_factory,
    sample_pdf_document,
    batch_pdf_documents,
)


# =============================================================================
# PYTEST CLI OPTIONS
# =============================================================================

def pytest_addoption(parser):
    """Register custom command-line options for RAG tests."""

    group = parser.getgroup("rag", "RAG stress test options")

    group.addoption(
        "--api-base-url",
        action="store",
        default=None,
        help="Base URL for the RAG API (default: http://localhost:13457/api)",
    )
    group.addoption(
        "--mongodb-host",
        action="store",
        default=None,
        help="MongoDB host for Celery task monitoring (default: 0.0.0.0)",
    )
    group.addoption(
        "--mongodb-port",
        action="store",
        type=int,
        default=None,
        help="MongoDB port (default: 27017)",
    )
    group.addoption(
        "--mongodb-db",
        action="store",
        default=None,
        help="MongoDB database name for Celery tasks (default: celery)",
    )
    group.addoption(
        "--num-docs",
        action="store",
        type=int,
        default=None,
        help="Number of documents to upload in stress test (default: 100)",
    )
    group.addoption(
        "--concurrent-uploads",
        action="store",
        type=int,
        default=None,
        help="Number of concurrent uploads (default: 10)",
    )
    group.addoption(
        "--upload-timeout",
        action="store",
        type=int,
        default=None,
        help="Per-upload timeout in seconds (default: 300)",
    )
    group.addoption(
        "--celery-timeout",
        action="store",
        type=int,
        default=None,
        help="Total Celery monitoring timeout in seconds (default: 1800)",
    )
    group.addoption(
        "--test-user",
        action="store",
        default=None,
        help="Logged-in user sent in embedding pipeline requests (default: stress_test_user)",
    )
    group.addoption(
        "--pages-per-doc",
        action="store",
        type=int,
        default=None,
        help="Fixed number of pages per document (default: 2)",
    )
    group.addoption(
        "--profile",
        action="store",
        default=None,
        help="Content profile: 'simple' (text only) or 'complex' (tables, images, charts) (default: simple)",
    )
    group.addoption(
        "--randomize",
        action="store_true",
        default=None,
        help="Randomize document count and pages-per-doc within min/max ranges",
    )
    group.addoption(
        "--min-docs",
        action="store",
        type=int,
        default=None,
        help="Minimum document count when --randomize is set (default: 50)",
    )
    group.addoption(
        "--max-docs",
        action="store",
        type=int,
        default=None,
        help="Maximum document count when --randomize is set (default: 100)",
    )
    group.addoption(
        "--min-pages",
        action="store",
        type=int,
        default=None,
        help="Minimum pages per doc when --randomize is set (default: 50)",
    )
    group.addoption(
        "--max-pages",
        action="store",
        type=int,
        default=None,
        help="Maximum pages per doc when --randomize is set (default: 300)",
    )


# =============================================================================
# MARKER REGISTRATION
# =============================================================================

def pytest_configure(config):
    """Register all custom markers used across RAG tests."""
    markers = [
        # Test levels
        "unit: Unit tests (isolated component testing)",
        "integration: Integration tests (multi-component testing)",
        "e2e: End-to-end tests (complete system testing)",
        # RAG domain markers
        "rag: RAG system tests",
        "document: Document upload and processing tests",
        "pipeline: Embedding pipeline tests",
        "embedding: Vector embedding tests",
        "retrieval: Document retrieval tests",
        "health: Health check and readiness tests",
        # Behaviour markers
        "fast: Fast running tests (< 1s)",
        "slow: Slow running tests (> 5s)",
        "stable: Stable, reliable tests",
        "flaky: Potentially unstable tests",
        # Special categories
        "smoke: Smoke tests for basic functionality",
        "regression: Regression tests for bug fixes",
        "stress: Stress and load tests",
        "performance: Performance and throughput tests",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)


# =============================================================================
# AUTOMATIC MARKER INJECTION
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """Auto-add markers to tests based on their directory path."""
    for item in items:
        path = str(item.fspath)

        # Test-level markers from directory
        if "/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/e2e/" in path:
            item.add_marker(pytest.mark.e2e)
        elif "/smoke/" in path:
            item.add_marker(pytest.mark.smoke)

        # Domain markers from directory
        if "/document/" in path or "doc_upload" in path or "doc_embed" in path:
            item.add_marker(pytest.mark.document)
        if "/pipeline/" in path:
            item.add_marker(pytest.mark.pipeline)
        if "/embedding/" in path:
            item.add_marker(pytest.mark.embedding)
        if "/retrieval/" in path:
            item.add_marker(pytest.mark.retrieval)
        if "/health/" in path:
            item.add_marker(pytest.mark.health)
