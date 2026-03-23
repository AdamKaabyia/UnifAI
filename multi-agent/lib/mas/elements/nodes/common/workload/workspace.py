"""
Workspace model for shared context and collaboration.

Clean, minimal design for managing shared data, results, and artifacts within a thread.
Enables agent collaboration through centralized context management.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List
from datetime import datetime, timezone
from .models import AgentResult, ArtifactRef
from .context import WorkspaceContext
from mas.elements.llms.common.chat.message import ChatMessage


class Workspace(BaseModel):
    """
    Workspace for shared context and collaboration.
    
    Manages shared data, results, and artifacts within a thread context.
    Enables agent collaboration through centralized state management.
    """
    
    # Workspace Identity
    thread_id: str
    
    # Shared Context Data (structured model)
    context: WorkspaceContext = Field(default_factory=WorkspaceContext)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # ========== CLASS METHODS ==========
    
    @classmethod
    def create(cls, thread_id: str) -> 'Workspace':
        """Create a new workspace for a thread."""
        return cls(thread_id=thread_id)
    
    # ========== INSTANCE METHODS ==========
    
    def add_fact(self, fact: str) -> 'Workspace':
        """Add a fact to the workspace."""
        if fact not in self.context.facts:
            self.context.facts.append(fact)
            self._update_timestamp()
        return self
    
    def remove_fact(self, fact: str) -> 'Workspace':
        """Remove a fact from the workspace."""
        if fact in self.context.facts:
            self.context.facts.remove(fact)
            self._update_timestamp()
        return self
    
    def add_result(self, result: AgentResult) -> 'Workspace':
        """Add an agent result to the workspace."""
        self.context.results.append(result)
        self._update_timestamp()
        return self
    
    def add_artifact(self, name: str, artifact_type: str, location: str, 
                     created_by: str, metadata: Dict[str, Any] = None) -> 'Workspace':
        """Add an artifact reference to the workspace."""
        artifact_ref = ArtifactRef(
            name=name,
            type=artifact_type,
            location=location,
            created_by=created_by,
            metadata=metadata or {}
        )
        self.context.artifacts[name] = artifact_ref
        self._update_timestamp()
        return self
    
    def remove_artifact(self, name: str) -> 'Workspace':
        """Remove an artifact from the workspace."""
        if name in self.context.artifacts:
            del self.context.artifacts[name]
            self._update_timestamp()
        return self
    
    def set_variable(self, key: str, value: Any) -> 'Workspace':
        """Set a variable in the workspace."""
        self.context.variables[key] = value
        self._update_timestamp()
        return self
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a variable from the workspace."""
        return self.context.variables.get(key, default)
    
    def remove_variable(self, key: str) -> 'Workspace':
        """Remove a variable from the workspace."""
        if key in self.context.variables:
            del self.context.variables[key]
            self._update_timestamp()
        return self
    
    def clear_results(self) -> 'Workspace':
        """Clear all results from the workspace."""
        self.context.results.clear()
        self._update_timestamp()
        return self
    
    def clear_facts(self) -> 'Workspace':
        """Clear all facts from the workspace."""
        self.context.facts.clear()
        self._update_timestamp()
        return self
    
    def clear_all(self) -> 'Workspace':
        """Clear all data from the workspace."""
        self.context.facts.clear()
        self.context.results.clear()
        self.context.artifacts.clear()
        self.context.variables.clear()
        self.context.conversation_history.clear()
        self._update_timestamp()
        return self
    
    # ========== CONVERSATION HISTORY MANAGEMENT ==========
    
    def add_message(self, message: ChatMessage) -> 'Workspace':
        """
        Add a message to the conversation history.
        
        Args:
            message: ChatMessage to add
            
        Returns:
            Self for chaining
        """
        self.context.conversation_history.append(message)
        self._update_timestamp()
        return self
    
    def add_messages(self, messages: List[ChatMessage]) -> 'Workspace':
        """
        Add multiple messages to the conversation history.
        
        Args:
            messages: List of ChatMessages to add
            
        Returns:
            Self for chaining
        """
        self.context.conversation_history.extend(messages)
        self._update_timestamp()
        return self
    
    def copy_messages_from_graphstate(self, graphstate_messages: List[ChatMessage]) -> 'Workspace':
        """
        Copy messages from GraphState to workspace conversation history.
        
        Creates a deep copy to avoid mutations affecting the original.
        
        Args:
            graphstate_messages: Messages from GraphState to copy
            
        Returns:
            Self for chaining
        """
        from copy import deepcopy
        copied_messages = deepcopy(graphstate_messages)
        self.add_messages(copied_messages)
        return self
    
    def append_messages_from_graphstate(self, graphstate_messages: List[ChatMessage]) -> 'Workspace':
        """
        Append new messages from GraphState, avoiding duplicates.
        
        Compares message content and role to detect duplicates.
        Useful for incremental updates from GraphState.
        
        Args:
            graphstate_messages: Messages from GraphState to append
            
        Returns:
            Self for chaining
        """
        existing_signatures = {
            (msg.role, msg.content) for msg in self.context.conversation_history
        }
        
        new_messages = [
            msg for msg in graphstate_messages
            if (msg.role, msg.content) not in existing_signatures
        ]
        
        if new_messages:
            self.add_messages(new_messages)
        
        return self
    
    def clear_conversation_history(self) -> 'Workspace':
        """
        Clear all conversation history.
        
        Returns:
            Self for chaining
        """
        self.context.conversation_history.clear()
        self._update_timestamp()
        return self
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the conversation history.
        
        Returns:
            Dictionary with conversation statistics
        """
        if not self.context.conversation_history:
            return {
                "message_count": 0,
                "participants": [],
                "latest_message": None
            }
        
        # Count messages by role
        role_counts = {}
        participants = set()
        
        for msg in self.context.conversation_history:
            role_str = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
            role_counts[role_str] = role_counts.get(role_str, 0) + 1
            participants.add(role_str)
        
        latest_message = self.context.conversation_history[-1]
        
        return {
            "message_count": len(self.context.conversation_history),
            "role_counts": role_counts,
            "participants": list(participants),
            "latest_message": {
                "role": latest_message.role.value if hasattr(latest_message.role, 'value') else str(latest_message.role),
                "content_preview": latest_message.content[:100] + "..." if len(latest_message.content) > 100 else latest_message.content
            }
        }
    
    def get_recent_messages(self, count: int = 10) -> List[ChatMessage]:
        """
        Get the most recent messages from conversation history.
        
        Args:
            count: Number of recent messages to return
            
        Returns:
            List of recent ChatMessages
        """
        return self.context.conversation_history[-count:] if self.context.conversation_history else []
    
    def get_messages_by_role(self, role) -> List[ChatMessage]:
        """
        Get all messages from a specific role.
        
        Args:
            role: Role to filter by (Role enum or string)
            
        Returns:
            List of ChatMessages from the specified role
        """
        target_role = role.value if hasattr(role, 'value') else str(role)
        return [
            msg for msg in self.context.conversation_history
            if (msg.role.value if hasattr(msg.role, 'value') else str(msg.role)) == target_role
        ]
    
    # ========== HELPER METHODS ==========
    
    def get_latest_result(self) -> AgentResult:
        """Get the most recent agent result."""
        return self.results[-1] if self.results else None
    
    def get_results_by_agent(self, agent_id: str) -> List[AgentResult]:
        """Get all results from a specific agent."""
        return [result for result in self.results 
                if hasattr(result, 'agent_id') and result.agent_id == agent_id]
    
    def get_artifact_by_type(self, artifact_type: str) -> List[ArtifactRef]:
        """Get all artifacts of a specific type."""
        return [artifact for artifact in self.context.artifacts.values() 
                if artifact.type == artifact_type]
    
    def has_fact(self, fact: str) -> bool:
        """Check if a fact exists in the workspace."""
        return fact in self.context.facts
    
    def has_artifact(self, name: str) -> bool:
        """Check if an artifact exists in the workspace."""
        return name in self.context.artifacts
    
    def has_variable(self, key: str) -> bool:
        """Check if a variable exists in the workspace."""
        return key in self.variables
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of the workspace context."""
        return {
            "thread_id": self.thread_id,
            "facts_count": len(self.context.facts),
            "results_count": len(self.context.results),
            "artifacts_count": len(self.context.artifacts),
            "variables_count": len(self.context.variables),
            "conversation_history_count": len(self.context.conversation_history),
            "created_at": self.created_at,
            "last_updated": self.last_updated
        }
    
    def _update_timestamp(self) -> None:
        """Update the last updated timestamp."""
        self.last_updated = datetime.now(timezone.utc)


# Rebuild models to resolve forward references
try:
    Workspace.model_rebuild()
except Exception:
    pass  # Ignore rebuild errors during import