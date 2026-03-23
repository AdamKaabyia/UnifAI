"""
Storage layer abstraction for workload services.

Clean separation between service logic and storage implementation.
Supports both in-memory and state-bound storage.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import Channel
from .thread import Thread, ThreadStatus
from .workspace import Workspace


class IWorkloadStorage(ABC):
    """
    Storage abstraction for workload persistence.
    
    SOLID SRP: Focused only on data persistence.
    Separated from business logic in services.
    """
    
    # ========== THREAD STORAGE ==========
    
    @abstractmethod
    def save_thread(self, thread: Thread) -> Thread:
        """Save thread to storage."""
        pass
    
    @abstractmethod
    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread by ID."""
        pass
    
    @abstractmethod
    def delete_thread(self, thread_id: str) -> bool:
        """Delete thread from storage."""
        pass
    
    @abstractmethod
    def list_threads(self) -> List[Thread]:
        """List all threads."""
        pass
    
    # ========== WORKSPACE STORAGE ==========
    
    @abstractmethod
    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace for thread."""
        pass
    
    @abstractmethod
    def update_workspace(self, workspace: Workspace) -> Workspace:
        """Update workspace in storage."""
        pass


class InMemoryStorage(IWorkloadStorage):
    """
    In-memory storage implementation.
    
    For testing and standalone usage.
    """
    
    def __init__(self):
        self._threads: Dict[str, Thread] = {}
        self._workspaces: Dict[str, Workspace] = {}
    
    def save_thread(self, thread: Thread) -> Thread:
        """Save thread to memory."""
        self._threads[thread.thread_id] = thread
        
        # Ensure workspace exists
        if thread.thread_id not in self._workspaces:
            workspace = Workspace.create(thread.thread_id)
            self._workspaces[thread.thread_id] = workspace
        
        return thread
    
    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread by ID."""
        return self._threads.get(thread_id)
    
    def delete_thread(self, thread_id: str) -> bool:
        """Delete thread from memory."""
        if thread_id in self._threads:
            del self._threads[thread_id]
            if thread_id in self._workspaces:
                del self._workspaces[thread_id]
            return True
        return False
    
    def list_threads(self) -> List[Thread]:
        """List all threads."""
        return list(self._threads.values())
    
    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace for thread."""
        if thread_id not in self._workspaces:
            self._workspaces[thread_id] = Workspace.create(thread_id)
        return self._workspaces[thread_id]
    
    def update_workspace(self, workspace: Workspace) -> Workspace:
        """Update workspace in memory."""
        self._workspaces[workspace.thread_id] = workspace
        return workspace


class StateBoundStorage(IWorkloadStorage):
    """
    GraphState-bound storage implementation.
    
    Integrates with existing GraphState system.
    """
    
    def __init__(self, state: StateView):
        self._state = state
    
    def save_thread(self, thread: Thread) -> Thread:
        """Save thread to GraphState."""
        threads = self._state.get(Channel.THREADS, {})
        threads[thread.thread_id] = thread.model_dump()
        self._state[Channel.THREADS] = threads
        
        # Ensure workspace exists
        workspaces = self._state.get(Channel.WORKSPACES, {})
        if thread.thread_id not in workspaces:
            workspace = Workspace.create(thread.thread_id)
            workspaces[thread.thread_id] = workspace.model_dump()
            self._state[Channel.WORKSPACES] = workspaces
        
        return thread
    
    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread by ID from state."""
        threads = self._state.get(Channel.THREADS, {})
        thread_data = threads.get(thread_id)
        
        if thread_data:
            return Thread(**thread_data)
        return None
    
    def delete_thread(self, thread_id: str) -> bool:
        """Delete thread from GraphState."""
        threads = self._state.get(Channel.THREADS, {})
        
        if thread_id not in threads:
            return False
        
        # Delete thread
        del threads[thread_id]
        self._state[Channel.THREADS] = threads
        
        # Delete workspace
        workspaces = self._state.get(Channel.WORKSPACES, {})
        if thread_id in workspaces:
            del workspaces[thread_id]
            self._state[Channel.WORKSPACES] = workspaces
        
        return True
    
    def list_threads(self) -> List[Thread]:
        """List all threads from state."""
        threads = self._state.get(Channel.THREADS, {})
        return [Thread(**thread_data) for thread_data in threads.values()]
    
    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace for thread from state."""
        workspaces = self._state.get(Channel.WORKSPACES, {})
        
        if thread_id not in workspaces:
            # Create new workspace
            workspace = Workspace.create(thread_id)
            workspaces[thread_id] = workspace.model_dump()
            self._state[Channel.WORKSPACES] = workspaces
            return workspace
        
        return Workspace(**workspaces[thread_id])
    
    def update_workspace(self, workspace: Workspace) -> Workspace:
        """Update workspace in state."""
        workspaces = self._state.get(Channel.WORKSPACES, {})
        workspaces[workspace.thread_id] = workspace.model_dump()
        self._state[Channel.WORKSPACES] = workspaces
        return workspace

