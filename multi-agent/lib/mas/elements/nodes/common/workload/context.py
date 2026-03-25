"""
Workspace context models for shared data management.

Clean, focused design for workspace context data structures.
Separated from task.py to maintain single responsibility principle.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List
from .models import AgentResult, WorkPlan
from .task import Task
from mas.elements.llms.common.chat.message import ChatMessage


class WorkspaceContext(BaseModel):
    """
    Workspace context data model.
    
    Contains all shared context data for a workspace.
    Provides centralized storage for facts, results, artifacts, tasks, and work plans.
    """
    # Shared Context Data
    facts: List[str] = Field(default_factory=list)
    results: List[AgentResult] = Field(default_factory=list)
    artifacts: Dict[str, Any] = Field(default_factory=dict)  # Will be ArtifactRef when imported
    variables: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[ChatMessage] = Field(default_factory=list)
    
    # Task storage for response tracking
    tasks: List[Task] = Field(default_factory=list, description="Processed tasks for this thread")
    
    # Work Plans storage - dedicated field for clean separation
    work_plans: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Work plans by owner_uid. Each value is a serialized WorkPlan."
    )
