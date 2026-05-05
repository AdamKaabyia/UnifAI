"""
Smoke tests for remote service readiness (Docling, Embedding).

Calls the RAG server's /service.readiness.get endpoint to verify that
external services are up before running heavier e2e tests.

Run with:
    pytest tests/smoke/test_service_health.py -v -s
"""

import os
import pytest
import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:13457/api")
READINESS_URL = f"{API_BASE_URL}/health/service.readiness.get"


@pytest.mark.smoke
@pytest.mark.health
class TestServiceHealth:
    """Verify that remote services required by the RAG pipeline are reachable."""

    def test_readiness_endpoint_responds(self):
        """The /service.readiness.get endpoint should return HTTP 200."""
        resp = requests.get(READINESS_URL, timeout=10)
        assert resp.status_code == 200, (
            f"Readiness endpoint returned {resp.status_code}: {resp.text}"
        )

    def test_docling_service_healthy(self):
        """Docling service should report healthy status."""
        resp = requests.get(READINESS_URL, timeout=10)
        data = resp.json()

        docling = data.get("docling", {})
        assert docling.get("status") == "healthy", (
            f"Docling is not healthy: {docling}"
        )

    def test_embedding_service_healthy(self):
        """Embedding service should report healthy status."""
        resp = requests.get(READINESS_URL, timeout=10)
        data = resp.json()

        embedding = data.get("embedding", {})
        assert embedding.get("status") == "healthy", (
            f"Embedding is not healthy: {embedding}"
        )

    def test_upload_enabled(self):
        """Upload should be enabled when both services are healthy."""
        resp = requests.get(READINESS_URL, timeout=10)
        data = resp.json()

        assert data.get("upload_enabled") is True, (
            f"Upload is disabled. Service status: {data}"
        )
