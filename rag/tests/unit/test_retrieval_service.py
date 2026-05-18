"""Unit tests for RetrievalService (document search)."""
from unittest.mock import create_autospec

import numpy as np
import pytest

from core.retrieval.service import RetrievalService, SearchQuery
from core.vector.domain.embedder import EmbeddingGenerator
from core.vector.domain.model import SearchResult
from core.vector.domain.repository import VectorRepository
from infrastructure.retrieval.source_filter_resolver import SourceFilterResolver


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_embedder():
    embedder = create_autospec(EmbeddingGenerator, instance=True)
    embedder.generate_query_embedding.return_value = np.array([0.1, 0.2, 0.3])
    return embedder


@pytest.fixture
def mock_vector_repo():
    repo = create_autospec(VectorRepository, instance=True)
    repo.search.return_value = []
    return repo


@pytest.fixture
def mock_resolver():
    return create_autospec(SourceFilterResolver, instance=True)


@pytest.fixture
def service(mock_embedder, mock_vector_repo, mock_resolver):
    return RetrievalService(
        embedder=mock_embedder,
        vector_repo=mock_vector_repo,
        filter_resolver=mock_resolver,
        source_type="DOCUMENT",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
@pytest.mark.retrieval
class TestRetrievalService:
    """Tests the RetrievalService search logic: filter resolution, scope handling,
    embedding generation, and result mapping."""

    def test_search_no_filters(self, service, mock_resolver, mock_vector_repo, mock_embedder):
        """A search with no filters must generate an embedding and search without filter constraints.

        Expected: generate_query_embedding called with the query; filters is None.
        Logs: INFO 'Search returned 0 results for query: test query...'
        """
        mock_resolver.resolve.return_value = None

        service.search(query="test query", limit=5)

        mock_embedder.generate_query_embedding.assert_called_once_with("test query")
        call_kwargs = mock_vector_repo.search.call_args
        assert call_kwargs.kwargs.get("filters") is None or call_kwargs[1].get("filters") is None

    def test_search_early_exit_empty_filter(self, service, mock_resolver, mock_vector_repo, mock_embedder):
        """When filters resolve to an empty set, search must return [] without generating embeddings.

        Expected: result == [], embedding not generated, vector search not called.
        Logs: INFO 'Filter resolved to empty set - returning no results'
        """
        mock_resolver.resolve.return_value = set()

        result = service.search(query="test", limit=5)

        assert result == []
        mock_embedder.generate_query_embedding.assert_not_called()
        mock_vector_repo.search.assert_not_called()

    def test_search_with_doc_ids(self, service, mock_resolver, mock_vector_repo):
        """Passing doc_ids must restrict the search to those specific source IDs.

        Expected: filters['metadata.source_id'] == {'src_1', 'src_2'}.
        Logs: INFO 'Search returned 0 results for query: test...'
        """
        mock_resolver.resolve.return_value = {"src_1", "src_2"}

        service.search(query="test", limit=5, doc_ids=["src_1", "src_2"])

        call_kwargs = mock_vector_repo.search.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert set(filters["metadata.source_id"]) == {"src_1", "src_2"}

    def test_search_private_scope(self, service, mock_resolver, mock_vector_repo):
        """Private scope must add a metadata.upload_by filter for the requesting user.

        Expected: filters['metadata.upload_by'] == 'alice'.
        Logs: INFO 'Search returned 0 results for query: test...'
        """
        mock_resolver.resolve.return_value = None

        service.search(query="test", limit=5, scope="private", user="alice")

        call_kwargs = mock_vector_repo.search.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert filters["metadata.upload_by"] == "alice"

    def test_search_public_scope(self, service, mock_resolver, mock_vector_repo):
        """Public scope must not add an upload_by filter, returning results from all users.

        Expected: filters is None or does not contain 'metadata.upload_by'.
        Logs: INFO 'Search returned 0 results for query: test...'
        """
        mock_resolver.resolve.return_value = None

        service.search(query="test", limit=5, scope="public", user="alice")

        call_kwargs = mock_vector_repo.search.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert filters is None or "metadata.upload_by" not in (filters or {})

    def test_search_result_mapping(self, service, mock_resolver, mock_vector_repo):
        """SearchResult domain objects must be mapped to plain dicts with id, score, content, metadata.

        Expected: 2 results, first result matches the full expected dict.
        Logs: INFO 'Search returned 2 results for query: test...'
        """
        mock_resolver.resolve.return_value = None
        mock_vector_repo.search.return_value = [
            SearchResult(id="r1", score=0.95, content="hello world", metadata={"source_id": "s1"}),
            SearchResult(id="r2", score=0.80, content="foo bar", metadata={"source_id": "s2"}),
        ]

        results = service.search(query="test", limit=2)

        assert len(results) == 2
        assert results[0] == {
            "id": "r1",
            "score": 0.95,
            "content": "hello world",
            "metadata": {"source_id": "s1"},
        }
        assert results[1]["id"] == "r2"

    def test_search_with_query_delegates(self, service, mock_resolver, mock_vector_repo):
        """search_with_query must unpack the SearchQuery DTO and delegate to the resolver.

        Expected: resolver.resolve called with source_type, doc_ids, and tags from the query.
        Logs: INFO 'Search returned 0 results for query: find docs...'
        """
        mock_resolver.resolve.return_value = None

        query = SearchQuery(
            query_text="find docs",
            source_type="DOCUMENT",
            top_k=3,
            scope="private",
            user="bob",
            doc_ids=["d1"],
            tags=["tag1"],
        )
        service.search_with_query(query)

        mock_resolver.resolve.assert_called_once_with(
            source_type="DOCUMENT",
            doc_ids=["d1"],
            tags=["tag1"],
        )
