"""
Workflow models for graph execution.

Contains Step, RTStep, and ConditionMeta models for workflow execution.
"""

from typing import Set, List, Dict, Optional, Any, Callable
from pydantic import BaseModel, Field
from mas.core.enums import ResourceCategory
from mas.blueprints.models.blueprint import StepMeta


class ConditionMeta(BaseModel):
    """Metadata for a conditional branch (no callable)."""
    rid: str
    type_key: str
    reads: Set[str] = Field(default_factory=set)

    class Config:
        frozen = True


class Step(BaseModel):
    """
    Represents a single workflow step.

    Starts as logical metadata, later enriched with runtime callables.
    """
    # Identity
    uid: str
    category: ResourceCategory
    rid: str  # Resource ID for SessionRegistry lookup
    type_key: str  # Element type for validation

    # Channel dependencies
    reads: Set[str] = Field(default_factory=set)
    writes: Set[str] = Field(default_factory=set)

    # Graph structure
    after: List[str] = Field(default_factory=list)
    branches: Dict[str, str] = Field(default_factory=dict)  # outcome -> next_uid

    # Optional condition
    condition: Optional[ConditionMeta] = None

    # Metadata
    meta: StepMeta = Field(default_factory=StepMeta)

    class Config:
        arbitrary_types_allowed = True  # For Callable types

    def total_reads(self) -> Set[str]:
        """Get all channels this step reads (including condition)."""
        reads = self.reads.copy()
        if self.condition:
            reads.update(self.condition.reads)
        return reads

    def total_writes(self) -> Set[str]:
        """Get all channels this step writes (including condition)."""
        writes = self.writes.copy()
        if self.condition:
            writes.update(getattr(self.condition, 'writes', set()))
        return writes


class RTStep(BaseModel):
    """Runtime-enabled step with bound callables."""
    # All logical data (composition)
    step: Step

    # Runtime callables (required for execution)
    func: Callable[[Dict[str, Any]], Dict[str, Any]]
    exit_condition: Optional[Callable[[Dict[str, Any]], Any]] = None

    class Config:
        arbitrary_types_allowed = True

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to underlying logical step."""
        return getattr(self.step, name)

    @property
    def has_condition(self) -> bool:
        """Check if step has conditional branching."""
        return bool(self.step.branches)

    def is_fully_bound(self) -> bool:
        """Check if all required callables are present."""
        has_func = self.func is not None
        has_condition_if_needed = not self.has_condition or self.exit_condition is not None
        return has_func and has_condition_if_needed


