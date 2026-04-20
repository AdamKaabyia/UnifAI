"""
Base test class for RAG end-to-end tests.

Provides common assertion utilities, HTTP client helpers, and shared
patterns for testing the RAG document upload and embedding pipeline.
"""

from typing import Dict, Optional


class BaseE2ETest:
    """
    Base class for RAG end-to-end tests.

    E2E tests validate the full RAG system behavior through HTTP API calls,
    Celery task monitoring, and vector storage verification.

    This class provides assertion helpers and reporting utilities. Actual
    HTTP interaction and config are handled via fixtures.
    """

    # ------------------------------------------------------------------
    # Upload assertions
    # ------------------------------------------------------------------

    def assert_upload_success_rate(
        self,
        stats: "UploadStats",
        min_rate: float = 95.0,
    ) -> None:
        """Assert that upload success rate meets the minimum threshold.

        Args:
            stats: Populated UploadStats instance.
            min_rate: Minimum acceptable success rate (0-100).
        """
        summary = stats.get_summary()
        actual_rate = summary["success_rate"]
        assert actual_rate >= min_rate, (
            f"Upload success rate {actual_rate:.2f}% is below minimum threshold "
            f"{min_rate:.1f}%.\n"
            f"Upload summary: {summary}"
        )

    def assert_no_upload_errors(self, stats: "UploadStats") -> None:
        """Assert that no upload errors occurred."""
        summary = stats.get_summary()
        assert summary["failed"] == 0, (
            f"Expected 0 upload failures, got {summary['failed']}.\n"
            f"Errors: {summary['errors']}"
        )

    def assert_upload_count(
        self,
        stats: "UploadStats",
        expected: int,
        tolerance: int = 0,
    ) -> None:
        """Assert the number of successful uploads is within tolerance.

        Args:
            stats: Populated UploadStats instance.
            expected: Expected number of successful uploads.
            tolerance: Allowed deviation from expected count.
        """
        summary = stats.get_summary()
        actual = summary["successful"]
        assert abs(actual - expected) <= tolerance, (
            f"Expected ~{expected} successful uploads (±{tolerance}), "
            f"got {actual}.\n"
            f"Upload summary: {summary}"
        )

    # ------------------------------------------------------------------
    # Embedding / Celery assertions
    # ------------------------------------------------------------------

    def assert_embedding_tasks_completed(
        self,
        stats: "EmbeddingStats",
        min_success: Optional[int] = None,
        allow_failures: bool = False,
    ) -> None:
        """Assert that embedding Celery tasks completed successfully.

        Args:
            stats: Populated EmbeddingStats instance.
            min_success: Minimum number of successful tasks required.
                         If None, checks that failed_tasks == 0.
            allow_failures: If False, assert no task failures occurred.
        """
        summary = stats.get_summary()

        if not allow_failures:
            assert summary["failed_tasks"] == 0, (
                f"Expected 0 embedding task failures, got {summary['failed_tasks']}.\n"
                f"Embedding summary: {summary}"
            )

        if min_success is not None:
            assert summary["successful_tasks"] >= min_success, (
                f"Expected at least {min_success} successful embedding tasks, "
                f"got {summary['successful_tasks']}.\n"
                f"Embedding summary: {summary}"
            )

    def assert_embedding_success_rate(
        self,
        stats: "EmbeddingStats",
        total_docs: int,
        min_rate: float = 95.0,
    ) -> None:
        """Assert embedding task success rate meets the minimum threshold.

        Args:
            stats: Populated EmbeddingStats instance.
            total_docs: Total number of documents submitted for embedding.
            min_rate: Minimum acceptable success rate (0-100).
        """
        summary = stats.get_summary()
        successful = summary["successful_tasks"]
        rate = (successful / total_docs * 100) if total_docs > 0 else 0.0
        assert rate >= min_rate, (
            f"Embedding success rate {rate:.2f}% is below minimum threshold "
            f"{min_rate:.1f}% ({successful}/{total_docs} tasks succeeded).\n"
            f"Embedding summary: {summary}"
        )

    # ------------------------------------------------------------------
    # Full-flow assertion
    # ------------------------------------------------------------------

    def assert_full_flow_passed(
        self,
        upload_stats: "UploadStats",
        embedding_stats: "EmbeddingStats",
        total_docs: int,
        min_upload_rate: float = 95.0,
        min_embed_rate: float = 95.0,
    ) -> None:
        """Assert both upload and embedding phases met their thresholds.

        Args:
            upload_stats: Populated UploadStats instance.
            embedding_stats: Populated EmbeddingStats instance.
            total_docs: Total number of documents submitted.
            min_upload_rate: Minimum upload success rate (0-100).
            min_embed_rate: Minimum embedding success rate (0-100).
        """
        upload_summary = upload_stats.get_summary()
        embed_summary = embedding_stats.get_summary()

        upload_ok = upload_summary["success_rate"] >= min_upload_rate
        successful_embeds = embed_summary["successful_tasks"]
        embed_rate = (successful_embeds / total_docs * 100) if total_docs > 0 else 0.0
        embed_ok = embed_rate >= min_embed_rate and embed_summary["failed_tasks"] == 0

        errors = []
        if not upload_ok:
            errors.append(
                f"Upload success rate {upload_summary['success_rate']:.2f}% "
                f"< {min_upload_rate:.1f}%"
            )
        if not embed_ok:
            errors.append(
                f"Embedding success rate {embed_rate:.2f}% "
                f"< {min_embed_rate:.1f}% or failures={embed_summary['failed_tasks']}"
            )

        assert not errors, (
            "Full flow stress test FAILED:\n  "
            + "\n  ".join(errors)
            + f"\n\nUpload summary: {upload_summary}"
            + f"\nEmbedding summary: {embed_summary}"
        )

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------

    def assert_avg_upload_time(
        self,
        stats: "UploadStats",
        max_seconds: float,
    ) -> None:
        """Assert average upload time does not exceed max_seconds."""
        summary = stats.get_summary()
        avg = summary["avg_upload_time"]
        assert avg <= max_seconds, (
            f"Average upload time {avg:.2f}s exceeds max {max_seconds:.1f}s.\n"
            f"Upload summary: {summary}"
        )

    def build_report_lines(
        self,
        upload_stats: "UploadStats",
        embedding_stats: "EmbeddingStats",
    ) -> str:
        """Build a human-readable report string for stdout logging.

        Args:
            upload_stats: Populated UploadStats instance.
            embedding_stats: Populated EmbeddingStats instance.

        Returns:
            Formatted multi-line report string.
        """
        u = upload_stats.get_summary()
        e = embedding_stats.get_summary()

        lines = [
            "",
            "=" * 70,
            "RAG STRESS TEST REPORT",
            "=" * 70,
            "",
            "--- UPLOAD PHASE ---",
            f"  Total attempts   : {u['total_attempts']}",
            f"  Successful       : {u['successful']}",
            f"  Failed           : {u['failed']}",
            f"  Success rate     : {u['success_rate']:.2f}%",
            f"  Avg upload time  : {u['avg_upload_time']:.2f}s",
            f"  Min upload time  : {u['min_upload_time']:.2f}s",
            f"  Max upload time  : {u['max_upload_time']:.2f}s",
            f"  Total duration   : {u['total_duration']:.2f}s",
        ]
        if u.get("errors"):
            lines.append("  Errors:")
            for err, count in u["errors"].items():
                lines.append(f"    - {err}: {count}")

        lines += [
            "",
            "--- EMBEDDING PHASE ---",
            f"  Successful tasks : {e['successful_tasks']}",
            f"  Failed tasks     : {e['failed_tasks']}",
            f"  Pending tasks    : {e['pending_tasks']}",
            f"  Avg task time    : {e['avg_task_duration']:.2f}s",
            f"  Total monitoring : {e['total_monitoring_duration']:.2f}s",
        ]
        if e.get("status_breakdown"):
            lines.append("  Status breakdown:")
            for status, count in e["status_breakdown"].items():
                lines.append(f"    - {status}: {count}")

        lines += ["", "=" * 70, ""]
        return "\n".join(lines)
