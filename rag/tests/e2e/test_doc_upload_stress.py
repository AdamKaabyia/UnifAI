"""
End-to-End Stress Test for Document Upload and Embedding Pipeline.

Validates the RAG system's ability to handle concurrent document uploads
and embedding pipeline execution under load.

Uses pre-generated PDFs from ``DocumentFactory`` (via the
``batch_pdf_documents`` fixture) and feeds them into the
``StressTestRunner`` upload/embed/monitor pipeline.

Run with:
    pytest tests/e2e/test_doc_upload_stress.py -v -s
    pytest tests/e2e/test_doc_upload_stress.py -v -s \\
        --num-docs 50 --pages-per-doc 30 --profile complex
    pytest tests/e2e/test_doc_upload_stress.py -v -s \\
        --randomize --min-docs 50 --max-docs 100 \\
        --min-pages 50 --max-pages 300 --profile complex
"""

import asyncio
import logging
import random
from typing import List, Tuple

import pytest

from tests.base.base_e2e_test import BaseE2ETest
from tests.factories.document_factory import DocumentFactory
from tests.fixtures.common.api_fixtures import RagTestConfig
from tests.docs.stress_test_doc_upload import StressTestRunner

logger = logging.getLogger(__name__)


# =============================================================================
# HELPERS
# =============================================================================

def _run_async(coro):
    """Run an async coroutine from synchronous pytest test methods."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _resolve_documents(
    rag_config: RagTestConfig,
) -> List[Tuple[int, str, bytes]]:
    """Generate documents according to config (fixed or randomised)."""
    if rag_config.randomize:
        count = random.randint(
            rag_config.min_documents, rag_config.max_documents,
        )
        pages = (rag_config.min_pages_per_doc, rag_config.max_pages_per_doc)
    else:
        count = rag_config.num_documents
        pages = rag_config.pages_per_doc

    logger.info(
        "Generating %d documents (pages=%s, profile=%s)",
        count, pages, rag_config.profile,
    )
    return DocumentFactory.create_batch(
        count=count,
        start_id=1,
        prefix="stress_test_doc",
        pages=pages,
        profile=rag_config.profile,
    )


class _PregenRunner(StressTestRunner):
    """StressTestRunner subclass that uses pre-generated documents.

    Overrides ``run_upload_phase`` to skip internal PDF generation and
    use documents created by ``DocumentFactory`` instead.  All other
    behaviour (upload, embed, Celery monitoring) is inherited unchanged.
    """

    def __init__(self, config, documents: List[Tuple[int, str, bytes]]):
        super().__init__(config)
        self._documents = documents
        self.document_filenames = [fname for _, fname, _ in documents]

    async def run_upload_phase(self):
        """Upload pre-generated documents (skip PDF generation)."""
        import aiohttp
        import time as _time

        logger.info("=" * 80)
        logger.info("PHASE 1: DOCUMENT UPLOAD")
        logger.info("=" * 80)
        logger.info(
            "Uploading %d pre-generated documents...",
            len(self._documents),
        )
        logger.info("Concurrent uploads: %d", self.config.CONCURRENT_UPLOADS)

        self.upload_stats.start_time = _time.time()

        async with aiohttp.ClientSession() as session:
            for i in range(0, len(self._documents),
                           self.config.CONCURRENT_UPLOADS):
                batch = self._documents[i:i + self.config.CONCURRENT_UPLOADS]
                batch_num = (i // self.config.CONCURRENT_UPLOADS) + 1
                total_batches = (
                    (len(self._documents) + self.config.CONCURRENT_UPLOADS - 1)
                    // self.config.CONCURRENT_UPLOADS
                )

                logger.info("--- Uploading Batch %d/%d ---",
                            batch_num, total_batches)
                await self.upload_batch(session, batch)

                summary = self.upload_stats.get_summary()
                logger.info(
                    "Progress: %d/%d successful, %d failed",
                    summary["successful"],
                    len(self._documents),
                    summary["failed"],
                )

            self.upload_stats.end_time = _time.time()

            if self.upload_stats.successful_uploads > 0:
                logger.info("-" * 80)
                await self.trigger_embedding_pipeline(session)


def _build_runner(
    rag_config: RagTestConfig,
    documents: List[Tuple[int, str, bytes]],
) -> _PregenRunner:
    """Construct a runner pre-loaded with factory-generated docs.

    The runner's ``NUM_DOCUMENTS`` is set to the actual document count
    (which may differ from ``rag_config.num_documents`` when randomising).
    """
    actual_count = len(documents)

    class _Cfg:
        API_BASE_URL = rag_config.api_base_url
        UPLOAD_ENDPOINT = rag_config.upload_endpoint
        EMBED_ENDPOINT = rag_config.embed_endpoint
        MONGODB_HOST = rag_config.mongodb_host
        MONGODB_PORT = rag_config.mongodb_port
        MONGODB_DB = rag_config.mongodb_db
        NUM_DOCUMENTS = actual_count
        CONCURRENT_UPLOADS = rag_config.concurrent_uploads
        PAGES_PER_DOC = rag_config.pages_per_doc
        UPLOAD_TIMEOUT = rag_config.upload_timeout
        UPLOAD_MAX_RETRIES = 3
        CELERY_MONITOR_TIMEOUT = rag_config.celery_monitor_timeout
        CELERY_POLL_INTERVAL = rag_config.celery_poll_interval
        TEST_USER = rag_config.test_user

    return _PregenRunner(_Cfg(), documents)


# =============================================================================
# TEST CLASS
# =============================================================================

@pytest.mark.e2e
@pytest.mark.stress
@pytest.mark.document
@pytest.mark.rag
class TestDocumentUploadStress(BaseE2ETest):
    """End-to-end stress test for RAG document upload and embedding pipeline.

    Documents are pre-generated by ``DocumentFactory`` with configurable
    page counts and content profiles (simple / complex).  The
    ``StressTestRunner`` handles upload, embedding, and Celery monitoring.
    """

    @pytest.mark.slow
    def test_full_upload_and_embed_flow(
        self,
        rag_config: RagTestConfig,
        capsys,
    ):
        """Run the complete upload -> embed -> verify flow end-to-end.

        1. Generate N PDFs via DocumentFactory (profile + page count)
        2. Upload concurrently via StressTestRunner
        3. Trigger embedding pipeline
        4. Monitor Celery tasks until completion or timeout
        5. Assert pass/fail thresholds
        """
        documents = _resolve_documents(rag_config)
        runner = _build_runner(rag_config, documents)

        _run_async(runner.run())

        with capsys.disabled():
            print(
                self.build_report_lines(runner.upload_stats, runner.embedding_stats)
            )

        self.assert_full_flow_passed(
            upload_stats=runner.upload_stats,
            embedding_stats=runner.embedding_stats,
            total_docs=len(documents),
            min_upload_rate=95.0,
            min_embed_rate=95.0,
        )
