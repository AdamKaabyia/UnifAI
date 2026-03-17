from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field
from mas.session.domain.models import TimeSeriesPoint


class TimeRangePreset(str, Enum):
    """
    Predefined time range presets for statistics filtering.

    Used at the API layer to accept human-readable time range values.
    Convert to a cutoff datetime with to_since() for use in
    service and repository layers.
    """
    TODAY = "today"
    LAST_7_DAYS = "7days"
    LAST_30_DAYS = "30days"
    ALL = "all"

    def to_since(self) -> Optional[datetime]:
        """
        Convert preset to a UTC cutoff datetime.

        Returns:
            Cutoff datetime in UTC, or None for ALL (no time limit)
        """
        now = datetime.now(timezone.utc)
        if self == TimeRangePreset.TODAY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self == TimeRangePreset.LAST_7_DAYS:
            return now - timedelta(days=7)
        elif self == TimeRangePreset.LAST_30_DAYS:
            return now - timedelta(days=30)
        return None


# ---------- User-scoped Statistics Models ----------

class ResourceCategoryStats(BaseModel):
    """Statistics for resources grouped by category."""
    category: str = Field(..., description="Resource category")
    count: int = Field(..., description="Total count of resources in this category")
    types: Dict[str, int] = Field(default_factory=dict, description="Count of resources by type within this category")


class StatisticsResponse(BaseModel):
    """Response model for aggregated statistics (user-scoped)."""
    totalWorkflows: int = Field(..., description="Total number of workflows/blueprints")
    activeSessions: int = Field(..., description="Number of active sessions")
    totalResources: int = Field(..., description="Total number of resources")
    categoriesInUse: int = Field(..., description="Number of categories with at least one configured resource")
    blueprintSessionCounts: Dict[str, int] = Field(default_factory=dict, description="Dictionary mapping blueprint_id to session count")
    resourcesByCategory: List[ResourceCategoryStats] = Field(default_factory=list, description="List of resource statistics grouped by category")


# ---------- System-wide Statistics Models (for admin dashboard) ----------

class TotalStats(BaseModel):
    """Total statistics for system-wide overview."""
    total_runs: int = Field(..., description="Total number of workflow runs")
    unique_users: int = Field(..., description="Number of unique users")
    avg_runs_per_user: float = Field(..., description="Average runs per user (can be fractional)")


class UserActivity(BaseModel):
    """
    User activity statistics for admin dashboard.

    Represents a single user's session activity within a given time range,
    including run counts, status breakdown, and blueprint usage.
    """
    user_id: str = Field(..., description="User identifier")
    run_count: int = Field(0, description="Number of session runs in the time period")
    status_breakdown: Dict[str, int] = Field(default_factory=dict, description="Run counts broken down by session status")
    unique_blueprints: int = Field(0, description="Number of distinct blueprints used")


class BlueprintUsage(BaseModel):
    """
    Blueprint usage statistics for admin dashboard.

    Represents how a single blueprint has been used across the system,
    including total runs and number of distinct users.
    """
    blueprint_id: str = Field(..., description="Blueprint identifier")
    blueprint_name: str = Field(..., description="Blueprint display name")
    run_count: int = Field(0, description="Total number of session runs")
    unique_users: int = Field(0, description="Number of distinct users who ran this blueprint")


class SystemStatsResponse(BaseModel):
    """
    Response model for system-wide statistics (admin dashboard).

    All data is scoped to the requested time range. The client can
    call the endpoint with different time_range values to get
    different views (e.g., today, last 7 days, last 30 days).
    """
    total_stats: TotalStats = Field(..., description="Total statistics: total_runs, unique_users, avg_runs_per_user")
    status_breakdown: Dict[str, int] = Field(default_factory=dict, description="Breakdown of session runs by status")
    active_users: List[UserActivity] = Field(default_factory=list, description="Users active in the selected time range, sorted by run count")
    top_blueprints: List[BlueprintUsage] = Field(default_factory=list, description="Most used blueprints in the selected time range")
    time_series: List[TimeSeriesPoint] = Field(default_factory=list, description="Session activity over time")
    generated_at: str = Field(..., description="ISO timestamp (UTC) when statistics were generated")
