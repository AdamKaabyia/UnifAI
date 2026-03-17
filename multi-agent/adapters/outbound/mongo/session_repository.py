import pymongo
from pymongo.collection import Collection
from typing import List, Mapping, Any, Dict, Optional
from datetime import datetime, timezone, timedelta
import logging

from mas.session.repository.repository import SessionRepository
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.models import TimeSeriesPoint, SystemAnalyticsData
from mas.core.dto import GroupedCount
from global_utils.utils.time_utils import format_utc_iso

logger = logging.getLogger(__name__)


class MongoSessionRepository(SessionRepository):
    """
    MongoDB-backed SessionRepository.

    Handles both user-scoped operations and system-wide analytics queries.
    Optimized for efficient aggregations with proper indexing.
    """

    # Field paths (centralized for easy schema changes)
    _TIME_FIELD = "run_context.started_at"
    _USER_FIELD = "user_id"
    _STATUS_FIELD = "status"
    _BLUEPRINT_FIELD = "blueprint_id"
    _RUN_ID_FIELD = "run_id"
    # Maximum number of data points returned in a time series query
    _MAX_TIME_SERIES_POINTS = 1000

    def __init__(
            self,
            mongodb_port: str = "27017",
            mongodb_ip: str = "localhost",
            db_name: str = "UnifAI",
            collection_name: str = "workflow_sessions",
    ):
        mongo_uri = f"mongodb://{mongodb_ip}:{mongodb_port}/"
        client = pymongo.MongoClient(mongo_uri)
        db = client[db_name]
        self._col: Collection = db[collection_name]
        self._ensure_indexes()

    # ---------- Index Management ----------

    def _ensure_indexes(self) -> None:
        """Create indexes for all query patterns. Safe to call multiple times."""
        # Primary lookup (existing)
        self._col.create_index(
            [(self._USER_FIELD, pymongo.ASCENDING), (self._RUN_ID_FIELD, pymongo.ASCENDING)],
            unique=True,
            background=True
        )

        # Fetch by run_id alone (used by fetch() and delete())
        self._col.create_index(
            [(self._RUN_ID_FIELD, pymongo.ASCENDING)],
            background=True
        )

        # Time-based analytics (system-wide queries)
        self._col.create_index(
            [(self._TIME_FIELD, pymongo.DESCENDING)],
            background=True
        )

        # User + time (user activity queries)
        self._col.create_index(
            [(self._USER_FIELD, pymongo.ASCENDING), (self._TIME_FIELD, pymongo.DESCENDING)],
            background=True
        )

    # ---------- Core CRUD Operations ----------

    def save(self, record: SessionRecord) -> None:
        doc = record.model_dump(mode="json")
        self._col.replace_one(
            {self._USER_FIELD: record.user_id, self._RUN_ID_FIELD: record.run_id},
            doc,
            upsert=True,
        )

    def fetch(self, run_id: str) -> SessionRecord:
        doc = self._col.find_one({self._RUN_ID_FIELD: run_id}, {"_id": 0})
        if not doc:
            raise KeyError(f"No session for {run_id}")
        return SessionRecord.model_validate(doc)

    def list_runs(self, user_id: str) -> List[str]:
        cursor = self._col.find(
            {self._USER_FIELD: user_id},
            {self._RUN_ID_FIELD: 1, "_id": 0}
        )
        return [d[self._RUN_ID_FIELD] for d in cursor]

    def list_docs(self, user_id: str) -> List[Mapping[str, Any]]:
        """Return all session documents for a user in a single query."""
        return list(self._col.find(
            {self._USER_FIELD: user_id},
            {"_id": 0}
        ))

    def delete(self, run_id: str) -> bool:
        """Delete a session by run_id. Returns True if deleted, False if not found."""
        result = self._col.delete_one({self._RUN_ID_FIELD: run_id})
        return result.deleted_count > 0

    # ---------- User-scoped Statistics ----------

    def count(self, user_id: str, filter: Dict[str, Any]) -> int:
        """Count sessions matching filter criteria for a user."""
        query = {self._USER_FIELD: user_id, **filter}
        return self._col.count_documents(query)

    def group_count(
        self,
        user_id: str,
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group documents by specified fields and return counts.
        Uses MongoDB aggregation for efficient server-side grouping.

        Args:
            user_id: The user ID to filter by
            group_by: List of field names to group by
            filter: Optional additional filter criteria

        Returns:
            List of GroupedCount DTOs with grouped field values and count.
        """
        match = {self._USER_FIELD: user_id, **(filter or {})}
        return self._aggregate_group_count(match, group_by)

    # ---------- System-wide Statistics (for admin analytics) ----------

    def count_system(self, since: Optional[datetime] = None) -> int:
        """Count all sessions system-wide, optionally filtered by time."""
        return self._col.count_documents(self._time_match(since))

    def get_distinct_users(self, since: Optional[datetime] = None) -> List[str]:
        """Get distinct user IDs, optionally filtered by time."""
        return self._col.distinct(self._USER_FIELD, self._time_match(since))

    def group_count_system(
        self,
        group_by: List[str],
        since: Optional[datetime] = None
    ) -> List[GroupedCount]:
        """Group all sessions by specified fields and return counts (system-wide)."""
        return self._aggregate_group_count(self._time_match(since), group_by)

    def get_session_activity_series(
        self,
        since: Optional[datetime] = None
    ) -> List[TimeSeriesPoint]:
        """
        Get session activity data grouped by appropriate time intervals.

        Automatically determines granularity:
        - Less than 1 day -> hourly
        - 1 to 30 days -> daily
        - Over 30 days or all time -> monthly
        """
        now = datetime.now(timezone.utc)
        truncate_unit = self._determine_granularity(since, now)

        pipeline = [
            {"$match": self._time_match(since, require_exists=True)},
            {"$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": {"$dateFromString": {"dateString": f"${self._TIME_FIELD}"}},
                        "unit": truncate_unit
                    }
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}},
            {"$limit": self._MAX_TIME_SERIES_POINTS}
        ]

        try:
            return [
                TimeSeriesPoint(period=doc["_id"], count=doc["count"])
                for doc in self._col.aggregate(pipeline, allowDiskUse=True)
            ]
        except Exception as e:
            logger.warning(f"Failed to get session activity series: {e}")
            return []

    def get_system_analytics(
        self,
        since: Optional[datetime] = None
    ) -> SystemAnalyticsData:
        """
        Get aggregated system analytics using MongoDB $facet.

        Optimizations:
        - Pre-filters by time BEFORE $facet (single collection scan)
        - Only 2 facets (user+blueprint serves both user and blueprint views)
        - Uses allowDiskUse for large datasets
        """
        pipeline = [
            {"$match": self._time_match(since)},
            {"$facet": {
                "user_status": [
                    {"$group": {
                        "_id": {
                            self._USER_FIELD: f"${self._USER_FIELD}",
                            self._STATUS_FIELD: f"${self._STATUS_FIELD}"
                        },
                        "count": {"$sum": 1}
                    }}
                ],
                "user_blueprint": [
                    {"$group": {
                        "_id": {
                            self._USER_FIELD: f"${self._USER_FIELD}",
                            self._BLUEPRINT_FIELD: f"${self._BLUEPRINT_FIELD}"
                        },
                        "count": {"$sum": 1}
                    }}
                ]
            }}
        ]

        try:
            results = list(self._col.aggregate(pipeline, allowDiskUse=True))
            if not results:
                return SystemAnalyticsData()

            facet = results[0]
            user_blueprint = self._to_grouped_counts(facet.get("user_blueprint", []))

            return SystemAnalyticsData(
                user_status_counts=self._to_grouped_counts(facet.get("user_status", [])),
                user_blueprint_counts=user_blueprint,
            )
        except Exception as e:
            logger.warning(f"Failed to get system analytics: {e}")
            return SystemAnalyticsData()

    # ---------- Private Helpers ----------

    def _time_match(
        self,
        since: Optional[datetime],
        require_exists: bool = False
    ) -> Dict[str, Any]:
        """
        Build a MongoDB match filter for time-based queries.

        Args:
            since: Cutoff datetime (None = no time filter)
            require_exists: If True, also require the time field to exist
                            (needed for $dateFromString in time series)
        """
        if since is None:
            return {self._TIME_FIELD: {"$exists": True}} if require_exists else {}

        cutoff = format_utc_iso(since)
        return {self._TIME_FIELD: {"$gte": cutoff}}

    def _aggregate_group_count(
        self,
        match: Dict[str, Any],
        group_by: List[str]
    ) -> List[GroupedCount]:
        """Shared aggregation logic for both user-scoped and system-wide grouping."""
        group_id = {field: f"${field}" for field in group_by}

        pipeline = [
            {"$match": match},
            {"$group": {"_id": group_id, "count": {"$sum": 1}}}
        ]

        return self._to_grouped_counts(
            list(self._col.aggregate(pipeline, allowDiskUse=True))
        )

    @staticmethod
    def _determine_granularity(since: Optional[datetime], now: datetime) -> str:
        """
        Determine the $dateTrunc unit for time series grouping.

        Returns appropriate granularity:
        - Hourly for < 1 day
        - Daily for 1-30 days
        - Monthly for > 30 days or all-time
        """
        if since is None:
            return "month"

        delta = now - since
        if delta < timedelta(days=1):
            return "hour"
        if delta <= timedelta(days=30):
            return "day"
        return "month"

    @staticmethod
    def _to_grouped_counts(docs: List[Dict]) -> List[GroupedCount]:
        """Transform MongoDB aggregation results to GroupedCount DTOs."""
        return [GroupedCount(fields=doc["_id"], count=doc["count"]) for doc in docs]
