from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from mas.core.dto import GroupedCount


class TimeSeriesPoint(BaseModel):
    """
    Single data point in a time series.

    The period granularity (hourly, daily, monthly) is determined
    by the repository implementation based on the requested time range.
    The period is truncated to the start of the bucket
    (e.g., start of the hour, day, or month).
    """
    period: datetime = Field(
        ...,
        description="Start of the time bucket (truncated to hour, day, or month depending on granularity)"
    )
    count: int = Field(
        ...,
        description="Number of items in this period"
    )


class SystemAnalyticsData(BaseModel):
    """
    Aggregated system analytics data returned by the repository layer.

    Groups session data by user+status and user+blueprint for building
    admin dashboard views (active users, top blueprints, etc.).

    The user_blueprint_counts field serves double duty:
    - User perspective: which blueprints did each user run?
    - Blueprint perspective: which users ran each blueprint?
    Both views are derived from the same (user_id, blueprint_id) grouping.

    Implementations should optimize for efficiency (e.g., batching
    multiple aggregations into a single database operation).
    """
    user_status_counts: List[GroupedCount] = Field(
        default_factory=list,
        description="Sessions grouped by user_id and status"
    )
    user_blueprint_counts: List[GroupedCount] = Field(
        default_factory=list,
        description="Sessions grouped by user_id and blueprint_id (used for both user and blueprint views)"
    )


@dataclass(frozen=True)
class RuntimeElement:
    """Complete runtime element: instance + spec + resource_spec."""
    instance: Any
    spec: Any
    resource_spec: Any  # ResourceSpec with user-defined name, config, rid, type
    
    @property
    def config(self) -> Any:
        """Get config from resource_spec."""
        return self.resource_spec.config if self.resource_spec else None


class SessionMeta(BaseModel):
    """Session metadata with Pydantic validation."""
    title: str | None = None
    tags: Dict[str, str] = Field(default_factory=dict)
    source: Optional[str] = None


class SessionChat(BaseModel):
    """Lightweight projection of a session's chat-relevant graph state."""
    messages: List = Field(default_factory=list)
    output: str = ""
