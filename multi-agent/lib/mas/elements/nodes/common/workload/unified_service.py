"""
Unified Workload Service - Composition root for all workload services.

SOLID design providing clean access to all workload-related services.
Acts as the main entry point for workload operations.
"""

from abc import ABC, abstractmethod
from typing import Optional
from mas.graph.state.state_view import StateView

from .thread_service import IThreadService, ThreadService
from .workspace_service import IWorkspaceService, WorkspaceService
from .storage import IWorkloadStorage, InMemoryStorage, StateBoundStorage
from .thread import Thread
from .workspace import Workspace


class IWorkloadService(ABC):
    """
    Unified interface providing access to all workload services.
    
    SOLID ISP: Provides focused service access, not all operations directly.
    Acts as composition root for the workload domain.
    """
    
    @abstractmethod
    def get_thread_service(self) -> IThreadService:
        """Get thread service for hierarchy and lifecycle operations."""
        pass
    
    @abstractmethod
    def get_workspace_service(self) -> IWorkspaceService:
        """Get workspace service for content management (includes work plans)."""
        pass
    
    # ========== LEGACY COMPATIBILITY METHODS ==========
    # These delegate to the appropriate services for backward compatibility
    
    def create_thread(self, title: str, objective: str, initiator: str) -> Thread:
        """Create thread (delegates to thread service)."""
        return self.get_thread_service().create_root_thread(title, objective, initiator)
    
    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread (delegates to thread service)."""
        return self.get_thread_service().get_thread(thread_id)
    
    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace (delegates to workspace service)."""
        return self.get_workspace_service().get_workspace(thread_id)
    
    def add_fact(self, thread_id: str, fact: str) -> None:
        """Add fact (delegates to workspace service)."""
        self.get_workspace_service().add_fact(thread_id, fact)
    
    def set_variable(self, thread_id: str, key: str, value) -> None:
        """Set variable (delegates to workspace service)."""
        self.get_workspace_service().set_variable(thread_id, key, value)
    
    def get_variable(self, thread_id: str, key: str, default=None):
        """Get variable (delegates to workspace service)."""
        return self.get_workspace_service().get_variable(thread_id, key, default)


class UnifiedWorkloadService(IWorkloadService):
    """
    Concrete implementation providing all workload services.
    
    SOLID composition over inheritance.
    Acts as the composition root for the entire workload domain.
    """
    
    def __init__(self, storage: IWorkloadStorage):
        """
        Initialize with storage implementation.
        
        Args:
            storage: Storage implementation (InMemoryStorage or StateBoundStorage)
        """
        # Initialize service layer
        self._thread_service = ThreadService(storage)
        self._workspace_service = WorkspaceService(storage)
    
    def get_thread_service(self) -> IThreadService:
        """Get thread service."""
        return self._thread_service
    
    def get_workspace_service(self) -> IWorkspaceService:
        """Get workspace service (includes work plan operations)."""
        return self._workspace_service
    
    @classmethod
    def create_in_memory(cls) -> 'UnifiedWorkloadService':
        """
        Create instance with in-memory storage.
        
        Returns:
            UnifiedWorkloadService with in-memory storage
        """
        storage = InMemoryStorage()
        return cls(storage)
    
    @classmethod
    def create_state_bound(cls, state: StateView) -> 'UnifiedWorkloadService':
        """
        Create instance with GraphState-bound storage.
        
        Args:
            state: StateView for GraphState access
            
        Returns:
            UnifiedWorkloadService with state-bound storage
        """
        storage = StateBoundStorage(state)
        return cls(storage)

