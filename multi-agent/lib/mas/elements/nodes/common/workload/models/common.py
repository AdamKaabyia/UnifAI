"""
Common models for workload operations.

Shared data structures used across different node types.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class AgentResult(BaseModel):
    """Result from agent processing.
    
    Pydantic model (not dataclass) to preserve type when nested in other Pydantic models.
    This ensures isinstance(result, AgentResult) works correctly in orchestrator.
    """
    content: str = Field(..., description="Main result content")
    agent_id: str = Field(..., description="ID of the agent that produced this result")
    agent_name: str = Field(..., description="Name of the agent")
    artifacts: List[str] = Field(default_factory=list, description="List of artifact paths/names produced")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")
    success: bool = Field(default=True, description="Whether the agent task succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    reasoning: str = Field(default="", description="Agent's reasoning process")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata")


class ArtifactRef(BaseModel):
    """Reference to an artifact with metadata."""
    name: str
    type: str
    location: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

