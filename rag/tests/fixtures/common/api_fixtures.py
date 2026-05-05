"""
Common API fixtures for RAG end-to-end tests.

Provides pytest fixtures for:
- RagTestConfig  - built from CLI options / env vars
- CeleryMonitor  - MongoDB-backed Celery task monitor
- http_session   - aiohttp ClientSession (async) for upload tests
"""

import os
import pytest
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# CONFIGURATION DATACLASS
# =============================================================================

@dataclass
class RagTestConfig:
    """Runtime configuration for RAG e2e tests.

    Values are populated from pytest CLI options first, then fall back to
    environment variables, and finally to hardcoded defaults.
    """

    # API
    api_base_url: str = "http://localhost:13457/api"

    # MongoDB (Celery backend)
    mongodb_host: str = "0.0.0.0"
    mongodb_port: int = 27017
    mongodb_db: str = "celery"

    # Load parameters
    num_documents: int = 100
    concurrent_uploads: int = 10
    pages_per_doc: int = 2

    # Content profile: "simple" (text only) or "complex" (tables, images, charts)
    profile: str = "simple"

    # Randomization — when enabled, num_documents and pages_per_doc are
    # ignored and replaced with random values drawn from the ranges below.
    randomize: bool = False
    min_documents: int = 10
    max_documents: int = 50
    min_pages_per_doc: int = 5
    max_pages_per_doc: int = 30

    # Timeouts (seconds)
    upload_timeout: int = 300
    celery_monitor_timeout: int = 1800
    celery_poll_interval: int = 5

    # User
    test_user: str = "stress_test_user"

    # Derived endpoints (populated post-init)
    upload_endpoint: str = field(init=False)
    embed_endpoint: str = field(init=False)

    def __post_init__(self):
        self.upload_endpoint = f"{self.api_base_url}/docs/upload"
        self.embed_endpoint = f"{self.api_base_url}/pipelines/embed"


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def rag_config(request) -> RagTestConfig:
    """Provide a RagTestConfig populated from CLI options and env vars.

    CLI options take precedence over environment variables which take
    precedence over hardcoded defaults.
    """

    def _opt(cli_key: str, env_key: str, default, cast=str):
        """Resolve value: CLI → env → default."""
        cli_val = request.config.getoption(cli_key, default=None)
        if cli_val is not None:
            return cast(cli_val)
        env_val = os.getenv(env_key)
        if env_val is not None:
            return cast(env_val)
        return default

    def _bool_opt(cli_key: str, env_key: str, default: bool) -> bool:
        """Resolve a boolean value: CLI → env → default."""
        cli_val = request.config.getoption(cli_key, default=None)
        if cli_val is not None:
            return bool(cli_val)
        env_val = os.getenv(env_key)
        if env_val is not None:
            return env_val.lower() in ("1", "true", "yes")
        return default

    return RagTestConfig(
        api_base_url=_opt("--api-base-url", "API_BASE_URL", "http://localhost:13457/api"),
        mongodb_host=_opt("--mongodb-host", "MONGODB_HOST", "0.0.0.0"),
        mongodb_port=_opt("--mongodb-port", "MONGODB_PORT", 27017, int),
        mongodb_db=_opt("--mongodb-db", "MONGODB_DB", "celery"),
        num_documents=_opt("--num-docs", "NUM_DOCUMENTS", 100, int),
        concurrent_uploads=_opt("--concurrent-uploads", "CONCURRENT_UPLOADS", 10, int),
        pages_per_doc=_opt("--pages-per-doc", "PAGES_PER_DOC", 2, int),
        profile=_opt("--profile", "TEST_PROFILE", "simple"),
        randomize=_bool_opt("--randomize", "RANDOMIZE", False),
        min_documents=_opt("--min-docs", "MIN_DOCUMENTS", 10, int),
        max_documents=_opt("--max-docs", "MAX_DOCUMENTS", 50, int),
        min_pages_per_doc=_opt("--min-pages", "MIN_PAGES_PER_DOC", 5, int),
        max_pages_per_doc=_opt("--max-pages", "MAX_PAGES_PER_DOC", 30, int),
        upload_timeout=_opt("--upload-timeout", "UPLOAD_TIMEOUT", 300, int),
        celery_monitor_timeout=_opt(
            "--celery-timeout", "CELERY_MONITOR_TIMEOUT", 1800, int
        ),
        test_user=_opt("--test-user", "TEST_USER", "stress_test_user"),
    )


@pytest.fixture(scope="session")
def celery_monitor(rag_config: RagTestConfig):
    """Provide a connected CeleryMonitor for the test session.

    The monitor connects to MongoDB at session start and disconnects after
    all tests have run.
    """
    from tests.docs.stress_test_doc_upload import CeleryMonitor as _CeleryMonitor

    # Build a minimal config-compatible object that CeleryMonitor expects
    class _Cfg:
        MONGODB_HOST = rag_config.mongodb_host
        MONGODB_PORT = rag_config.mongodb_port
        MONGODB_DB = rag_config.mongodb_db

    monitor = _CeleryMonitor(_Cfg())
    monitor.connect()
    yield monitor
    monitor.disconnect()
