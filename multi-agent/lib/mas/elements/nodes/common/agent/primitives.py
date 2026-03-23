"""
Core agent primitives with robust error tracking.

This module defines the fundamental data structures for agent execution:
- Immutable action/observation/finish types
- Status tracking for actions
- Step types for execution flow
- Time tracking and metadata support

Design Principles:
- Immutability: Actions and observations are frozen dataclasses
- Status Tracking: Actions track their execution status
- Error First: Errors are first-class citizens with detailed context
- Composability: All types work together cleanly
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class StepType(Enum):
    """Types of steps in agent execution."""
    PLANNING = "planning"       # Strategy thinking/reasoning
    ACTION = "action"          # Tool execution intent  
    OBSERVATION = "observation" # Tool execution result
    ERROR = "error"            # Execution or parsing error
    FINISH = "finish"          # Final agent output


class ActionStatus(Enum):
    """Status of an action through its lifecycle."""
    PENDING = "pending"        # Created, not yet executed
    EXECUTING = "executing"    # Currently being executed
    SUCCESS = "success"        # Executed successfully
    FAILED = "failed"          # Execution failed
    INVALID = "invalid"        # Invalid action (bad tool/args)
    SKIPPED = "skipped"        # Skipped by policy/user


@dataclass(frozen=True)
class AgentAction:
    """
    Immutable representation of agent's intent to use a tool.
    
    Represents what the agent wants to do (tool + input) along with
    its reasoning and current status. Actions are immutable - status
    updates create new instances.
    
    Example:
        action = AgentAction(
            tool="calculator",
            tool_input={"expression": "5 + 3"},
            reasoning="I need to calculate the sum"
        )
        
        executing_action = action.with_status(ActionStatus.EXECUTING)
        completed_action = executing_action.with_status(ActionStatus.SUCCESS)
    """
    tool: str
    tool_input: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reasoning: str = ""
    raw_output: Optional[str] = None
    status: ActionStatus = ActionStatus.PENDING
    error: Optional[str] = None
    
    def with_status(self, status: ActionStatus, error: Optional[str] = None) -> "AgentAction":
        """
        Create new action instance with updated status.
        
        Args:
            status: New status for the action
            error: Optional error message for failed statuses
            
        Returns:
            New AgentAction instance with updated status
        """
        from dataclasses import replace
        return replace(self, status=status, error=error)
    
    def is_terminal(self) -> bool:
        """Check if this action has reached a terminal state."""
        return self.status in (ActionStatus.SUCCESS, ActionStatus.FAILED, ActionStatus.SKIPPED)
    
    def is_successful(self) -> bool:
        """Check if this action completed successfully."""
        return self.status == ActionStatus.SUCCESS


@dataclass(frozen=True)
class AgentObservation:
    """
    Immutable representation of tool execution result.
    
    Contains the output from executing an AgentAction, including
    success/failure status, timing information, and error details.
    
    Example:
        observation = AgentObservation(
            action_id=action.id,
            tool="calculator", 
            output=8,
            success=True,
            execution_time=0.05
        )
    """
    action_id: str
    tool: str
    output: Any
    success: bool = True
    error: Optional[Exception] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def content(self) -> str:
        """Get observation content as string for LLM context."""
        if self.success:
            return str(self.output)
        return f"Error: {self.error}"
    
    def is_error(self) -> bool:
        """Check if this observation represents an error."""
        return not self.success or self.error is not None


@dataclass(frozen=True)
class AgentFinish:
    """
    Immutable representation of final agent output.
    
    Represents the agent's final answer or completion state.
    Contains the output, reasoning, and any additional return values.
    
    Example:
        finish = AgentFinish(
            output="The answer is 8",
            reasoning="I calculated 5 + 3 using the calculator tool",
            return_values={"calculation_result": 8}
        )
    """
    output: Any
    reasoning: str = ""
    return_values: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def as_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary output for API/serialization.
        
        Returns:
            Dictionary with output, reasoning, and return_values
        """
        result = dict(self.return_values)
        result["output"] = self.output
        if self.reasoning:
            result["reasoning"] = self.reasoning
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class AgentStep:
    """
    Mutable step in agent execution flow.
    
    Represents a single step in the agent's execution, containing
    the step type, associated data, timing, and metadata.
    Unlike actions/observations, steps are mutable for efficiency
    during execution.
    
    Example:
        step = AgentStep(
            type=StepType.ACTION,
            data=action,
            metadata={"strategy": "react"}
        )
    """
    type: StepType
    data: Union[AgentAction, AgentObservation, AgentFinish, Exception, Any]
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_terminal(self) -> bool:
        """Check if this step ends execution."""
        return self.type in (StepType.FINISH, StepType.ERROR)
    
    def is_action(self) -> bool:
        """Check if this step represents an action."""
        return self.type == StepType.ACTION
    
    def is_observation(self) -> bool:
        """Check if this step represents an observation."""
        return self.type == StepType.OBSERVATION
    
    def is_finish(self) -> bool:
        """Check if this step represents completion."""
        return self.type == StepType.FINISH
    
    def is_error(self) -> bool:
        """Check if this step represents an error."""
        return self.type == StepType.ERROR


@dataclass(frozen=True)
class SystemError:
    """
    Immutable system-level error for LLM feedback.
    
    Represents errors that need to be communicated back to the LLM
    for learning and recovery, distinct from tool execution errors.
    
    Example:
        error = SystemError.from_parse_error(parse_error)
        guidance = error.guidance  # Ready-to-use LLM feedback
    """
    message: str
    error_type: str
    raw_output: Optional[str] = None
    guidance: Optional[str] = None
    recoverable: bool = True
    
    @classmethod
    def from_parse_error(cls, parse_error) -> 'SystemError':
        """Factory method for parse errors."""
        from ..constants import ErrorMessages
        
        return cls(
            message=str(parse_error),
            error_type="parse_error",
            raw_output=getattr(parse_error, 'raw_output', None),
            guidance=ErrorMessages.get_parse_error_guidance(parse_error),
            recoverable=getattr(parse_error, 'recoverable', True)
        )
    
    @classmethod
    def from_exception(cls, exception: Exception, error_type: str = "system_error") -> 'SystemError':
        """Factory method for general exceptions."""
        return cls(
            message=str(exception),
            error_type=error_type,
            guidance=f"System error occurred: {exception}. Please try a different approach.",
            recoverable=False
        )


# Type aliases for cleaner signatures
ActionObservationPair = tuple[AgentAction, AgentObservation]
ExecutionHistory = List[AgentStep]
