from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ConfigDict


class ExecutionContext(BaseModel):
    """Runtime execution context — who, what scope, when.

    Immutable (frozen) so mutations go through explicit copy methods.
    ``extra="ignore"`` ensures backward compatibility when deserializing
    older DB documents that carried fields no longer present (e.g. run_id,
    metadata, logged_in_user).
    """

    user_id: str = ""
    scope: str = "public"
    engine_name: str = ""

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    tags: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="ignore")

    def with_scope(self, scope: str) -> ExecutionContext:
        return self.model_copy(update={"scope": scope})

    def mark_finished(self) -> ExecutionContext:
        return self.model_copy(update={"finished_at": datetime.now(timezone.utc)})


class ExecutionContextHolder:
    """Mutable reference to an immutable ExecutionContext.

    Created at build time (uninitialised).  Filled at execution time
    (real values).  Elements receive a closure over this object — they
    read current values when they need them.

    Fail-fast: accessing ``context``, ``scope``, or ``user_id`` before
    the holder is filled raises ``RuntimeError`` instead of returning
    silent defaults.
    """

    __slots__ = ("_ctx",)

    def __init__(self) -> None:
        self._ctx: Optional[ExecutionContext] = None

    @property
    def context(self) -> ExecutionContext:
        if self._ctx is None:
            raise RuntimeError(
                "ExecutionContext not initialised — "
                "ensure lifecycle.begin() runs before element execution"
            )
        return self._ctx

    @context.setter
    def context(self, value: ExecutionContext) -> None:
        self._ctx = value

    @property
    def scope(self) -> str:
        return self.context.scope

    @property
    def user_id(self) -> str:
        return self.context.user_id
