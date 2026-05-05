"""Unit tests for PipelineService."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, create_autospec

import pytest

from core.pipeline.domain.model import PipelineRecord, PipelineStatus, PipelineStats
from core.pipeline.domain.repository import PipelineRepository
from core.pipeline.service import PipelineService


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_repo():
    return create_autospec(PipelineRepository, instance=True)


@pytest.fixture
def service(mock_repo):
    return PipelineService(pipeline_repo=mock_repo)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
@pytest.mark.pipeline
class TestPipelineService:
    """Tests the PipelineService CRUD operations and status management."""

    # --- register ---

    def test_register_creates_new_record(self, service, mock_repo):
        """Registering a new pipeline ID must create a record with PENDING status.

        Expected: record saved with pipeline_id='p1', source_type='DOCUMENT', status=PENDING.
        Logs: No warnings or errors.
        """
        mock_repo.find_by_id.return_value = None

        record = service.register("p1", "DOCUMENT")

        assert record.pipeline_id == "p1"
        assert record.source_type == "DOCUMENT"
        assert record.status == PipelineStatus.PENDING
        mock_repo.save.assert_called_once()

    def test_register_existing_updates_timestamp(self, service, mock_repo):
        """Re-registering an existing pipeline must update its last_updated timestamp without creating a new record.

        Expected: last_updated > old_time; save called with the existing record.
        Logs: No warnings or errors.
        """
        old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        existing = PipelineRecord(
            pipeline_id="p1",
            source_type="DOCUMENT",
            status=PipelineStatus.DONE,
            created_at=old_time,
            last_updated=old_time,
        )
        mock_repo.find_by_id.return_value = existing

        record = service.register("p1", "DOCUMENT")

        assert record.last_updated > old_time
        mock_repo.save.assert_called_once_with(existing)

    # --- update_status ---

    def test_update_status_success(self, service, mock_repo):
        """Updating status on an existing record must change the status and persist.

        Expected: result is True, record.status == COLLECTING, save called.
        Logs: No warnings or errors.
        """
        record = PipelineRecord(
            pipeline_id="p1",
            source_type="DOCUMENT",
            status=PipelineStatus.PENDING,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )
        mock_repo.find_by_id.return_value = record

        result = service.update_status("p1", PipelineStatus.COLLECTING)

        assert result is True
        assert record.status == PipelineStatus.COLLECTING
        mock_repo.save.assert_called_once()

    def test_update_status_calculates_processing_time_on_done(self, service, mock_repo):
        """Transitioning to DONE must calculate the total processing time from created_at.

        Expected: stats.processing_time > 0.
        Logs: No warnings or errors.
        """
        created = datetime(2025, 1, 1, 0, 0, 0)
        record = PipelineRecord(
            pipeline_id="p1",
            source_type="DOCUMENT",
            status=PipelineStatus.STORING,
            created_at=created,
            last_updated=created,
            stats=PipelineStats(),
        )
        mock_repo.find_by_id.return_value = record

        service.update_status("p1", PipelineStatus.DONE)

        assert record.stats.processing_time > 0

    def test_update_status_no_processing_time_on_other_statuses(self, service, mock_repo):
        """Transitioning to any status other than DONE must not calculate processing time.

        Expected: stats.processing_time == 0.0.
        Logs: No warnings or errors.
        """
        record = PipelineRecord(
            pipeline_id="p1",
            source_type="DOCUMENT",
            status=PipelineStatus.PENDING,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            stats=PipelineStats(),
        )
        mock_repo.find_by_id.return_value = record

        service.update_status("p1", PipelineStatus.COLLECTING)

        assert record.stats.processing_time == 0.0

    def test_update_status_from_string(self, service, mock_repo):
        """Status can be passed as a plain string and must be converted to the enum.

        Expected: record.status == PipelineStatus.PROCESSING after passing "PROCESSING" as string.
        Logs: No warnings or errors.
        """
        record = PipelineRecord(
            pipeline_id="p1",
            source_type="DOCUMENT",
            status=PipelineStatus.PENDING,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )
        mock_repo.find_by_id.return_value = record

        service.update_status("p1", "PROCESSING")

        assert record.status == PipelineStatus.PROCESSING

    def test_update_status_nonexistent_returns_false(self, service, mock_repo):
        """Updating status on a non-existent pipeline must return False without saving.

        Expected: result is False, save not called.
        Logs: No warnings or errors.
        """
        mock_repo.find_by_id.return_value = None

        result = service.update_status("missing", PipelineStatus.DONE)

        assert result is False
        mock_repo.save.assert_not_called()

    # --- get / delete ---

    def test_get_delegates_to_repo(self, service, mock_repo):
        """get() must delegate directly to the repository's find_by_id.

        Expected: find_by_id called once with 'p1'.
        Logs: No warnings or errors.
        """
        mock_repo.find_by_id.return_value = MagicMock()
        service.get("p1")
        mock_repo.find_by_id.assert_called_once_with("p1")

    def test_delete_delegates_to_repo(self, service, mock_repo):
        """delete() must delegate directly to the repository and return the deleted count.

        Expected: result == 1, delete called once with 'p1'.
        Logs: No warnings or errors.
        """
        mock_repo.delete.return_value = 1
        result = service.delete("p1")
        assert result == 1
        mock_repo.delete.assert_called_once_with("p1")
