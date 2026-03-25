"""
Workload Management Module

SOLID design for thread and workspace management in the multi-agent system.
Provides focused interfaces and implementations for workload orchestration.
"""

# Core models
from .models import (
    AgentResult,
    WorkPlan,
    WorkItem,
    WorkItemStatus,
    WorkItemKind,
    ToolArguments,
    WorkItemResult,
    WorkItemStatusCounts,
    WorkPlanStatus,
    LocalExecution,
    DelegationExchange,
)
from .task import Task
from .context import WorkspaceContext
from .thread import Thread, ThreadStatus
from .workspace import Workspace, ArtifactRef
from .agent_thread import AgentThread

# New SOLID services
from .thread_service import IThreadService, ThreadService
from .workspace_service import IWorkspaceService, WorkspaceService
from .storage import IWorkloadStorage, InMemoryStorage, StateBoundStorage
from .unified_service import IWorkloadService, UnifiedWorkloadService

# Hooks
from .hooks import WorkPlanHook, BaseWorkPlanHook, WorkPlanHookPoint
from .streaming_hook import WorkPlanStreamingHook

# Legacy components can be imported from storage and unified_service if needed

__all__ = [
    # Core models
    'AgentResult',
    'WorkspaceContext', 
    'Task',
    'Thread',
    'ThreadStatus',
    'Workspace',
    'ArtifactRef',
    'AgentThread',
    
    # Work plan components (WorkPlanService removed - use WorkspaceService.load_work_plan() instead)
    'WorkPlan',
    'WorkItem',
    'WorkItemStatus',
    'WorkItemKind',
    'ToolArguments',
    'WorkItemResult',
    'WorkItemStatusCounts',
    'WorkPlanStatus',
    'LocalExecution',
    'DelegationExchange',
    
    # New SOLID services
    'IThreadService',
    'ThreadService',
    'IWorkspaceService', 
    'WorkspaceService',
    'IWorkloadStorage',
    'InMemoryStorage',
    'StateBoundStorage',
    'IWorkloadService',
    'UnifiedWorkloadService',
    
    # Hooks
    'WorkPlanHook',
    'BaseWorkPlanHook',
    'WorkPlanHookPoint',
    'WorkPlanStreamingHook',
]