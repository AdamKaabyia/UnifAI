"""
Base parser interface and common functionality.

This module defines the core parsing interface that all parser implementations
must follow, along with common utilities, error types, and configuration models.

Design Principles:
- Protocol-based: Clear interface definition
- Error Recovery: Structured error handling with recovery
- Configuration: Flexible parser configuration
- Extensibility: Easy to add new parser types
"""

from abc import ABC, abstractmethod
from typing import Union, List, Protocol, runtime_checkable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from mas.elements.llms.common.chat.message import ChatMessage, Role
from ..primitives import AgentAction, AgentFinish
from ..constants import ParserDefaults, SpecialToolNames


class ParseErrorType(Enum):
    """Types of parsing errors that can occur."""
    INVALID_FORMAT = "invalid_format"
    MISSING_CONTENT = "missing_content"
    INVALID_ROLE = "invalid_role"
    MALFORMED_STRUCTURE = "malformed_structure"
    TOOL_CALL_ERROR = "tool_call_error"
    JSON_ERROR = "json_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_FORMAT = "unknown_format"


class RecoveryStrategy(Enum):
    """Strategies for recovering from parse errors."""
    REFLECTION = "reflection"        # Create reflection action
    ERROR_ACTION = "error_action"    # Create error-handling action
    IGNORE = "ignore"                # Skip the error
    FAIL_FAST = "fail_fast"         # Propagate error immediately


@dataclass
class ParserConfig:
    """Base configuration for parsers."""
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.REFLECTION
    error_action_tool: str = SpecialToolNames.PARSE_ERROR.value
    min_content_length: int = ParserDefaults.MIN_CONTENT_LENGTH
    max_content_length: int = ParserDefaults.MAX_CONTENT_LENGTH
    validate_schema: bool = ParserDefaults.VALIDATE_SCHEMA
    custom_settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_settings is None:
            self.custom_settings = {}


class ParseError(Exception):
    """
    Structured parsing error with recovery information.
    
    Provides detailed context about parsing failures including error type,
    recovery strategy, and the original content that failed to parse.
    """
    
    def __init__(
        self, 
        message: str, 
        error_type: ParseErrorType,
        raw_output: str, 
        recoverable: bool = True,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.REFLECTION,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.error_type = error_type
        self.raw_output = raw_output
        self.recoverable = recoverable
        self.recovery_strategy = recovery_strategy
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "message": str(self),
            "error_type": self.error_type.value,
            "raw_output": self.raw_output,
            "recoverable": self.recoverable,
            "recovery_strategy": self.recovery_strategy.value,
            "context": self.context
        }


@runtime_checkable  
class OutputParser(Protocol):
    """
    Protocol defining the interface for all output parsers.
    
    All parser implementations must implement these methods to ensure
    consistent behavior across the agent system.
    """
    
    def parse(self, message: ChatMessage) -> Union[List[AgentAction], AgentFinish]:
        """
        Parse assistant message into actions or finish.
        
        Args:
            message: ChatMessage from LLM (typically role=ASSISTANT)
            
        Returns:
            Either a list of AgentActions or an AgentFinish
            
        Raises:
            ParseError: If parsing fails
        """
        ...
        
    def parse_error_recovery(self, error: ParseError) -> AgentAction:
        """
        Convert parse error into recovery action.
        
        Args:
            error: The parse error that occurred
            
        Returns:
            AgentAction for error recovery/reflection
        """
        ...
    
    def validate_message(self, message: ChatMessage) -> None:
        """
        Validate message format before parsing.
        
        Args:
            message: Message to validate
            
        Raises:
            ParseError: If message format is invalid
        """
        ...


class BaseOutputParser(ABC):
    """
    Abstract base class for output parsers with common functionality.
    
    Provides common validation, error handling, and recovery functionality
    that can be shared across different parser implementations.
    """
    
    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize parser with configuration.
        
        Args:
            config: Parser configuration (uses defaults if None)
        """
        self.config = config or ParserConfig()
    
    def validate_message(self, message: ChatMessage) -> None:
        """
        Common message validation logic.
        
        Validates basic message structure that all parsers expect.
        Subclasses can override for additional validation.
        
        Args:
            message: Message to validate
            
        Raises:
            ParseError: If message is invalid
        """
        if not isinstance(message, ChatMessage):
            raise ParseError(
                f"Expected ChatMessage, got {type(message)}",
                ParseErrorType.INVALID_FORMAT,
                str(message),
                recoverable=False
            )
        
        if message.role != Role.ASSISTANT:
            raise ParseError(
                f"Expected ASSISTANT role, got {message.role}",
                ParseErrorType.INVALID_ROLE,
                message.content or "",
                recoverable=False
            )
        
        content = message.content or ""
        if len(content) < self.config.min_content_length and not hasattr(message, 'tool_calls'):
            raise ParseError(
                f"Message content too short ({len(content)} chars, min {self.config.min_content_length})",
                ParseErrorType.MISSING_CONTENT,
                content,
                recoverable=True,
                recovery_strategy=self.config.recovery_strategy
            )
        
        if len(content) > self.config.max_content_length:
            raise ParseError(
                f"Message content too long ({len(content)} chars, max {self.config.max_content_length})",
                ParseErrorType.VALIDATION_ERROR,
                content[:1000] + "...",  # Truncate for error message
                recoverable=True
            )
    
    @abstractmethod
    def parse(self, message: ChatMessage) -> Union[List[AgentAction], AgentFinish]:
        """
        Abstract parse method - must be implemented by subclasses.
        
        Args:
            message: ChatMessage to parse
            
        Returns:
            List of actions or finish result
        """
        ...
    
    def parse_error_recovery(self, error: ParseError) -> AgentAction:
        """
        Default error recovery implementation.
        
        Creates appropriate recovery action based on error type and
        recovery strategy. Can be overridden by subclasses for
        custom recovery behavior.
        
        Args:
            error: Parse error to recover from
            
        Returns:
            AgentAction for recovery
        """
        tool_name = self._get_recovery_tool_name(error)
        tool_input = self._build_recovery_input(error)
        
        return AgentAction(
            tool=tool_name,
            tool_input=tool_input,
            reasoning=f"Recovering from {error.error_type.value}: {error}",
            raw_output=error.raw_output,
            status=error.error_type.name.lower(),
            error=str(error)
        )
    
    def _get_recovery_tool_name(self, error: ParseError) -> str:
        """
        Determine recovery tool name based on error type.
        
        Args:
            error: Parse error
            
        Returns:
            Tool name for recovery
        """
        if error.recovery_strategy == RecoveryStrategy.REFLECTION:
            return self.config.error_action_tool
        elif error.recovery_strategy == RecoveryStrategy.ERROR_ACTION:
            return f"_handle_{error.error_type.value}"
        else:
            return "_generic_error"
    
    def _build_recovery_input(self, error: ParseError) -> Dict[str, Any]:
        """
        Build tool input for recovery action.
        
        Args:
            error: Parse error
            
        Returns:
            Dictionary of tool input parameters
        """
        base_input = {
            "error": str(error),
            "error_type": error.error_type.value,
            "raw_output": error.raw_output,
            "recoverable": error.recoverable
        }
        
        # Add error-specific context
        if error.error_type == ParseErrorType.TOOL_CALL_ERROR:
            base_input.update({
                "expected": "valid tool calls with proper names and arguments",
                "guidance": "Ensure tool calls have valid names and properly formatted arguments"
            })
        elif error.error_type == ParseErrorType.JSON_ERROR:
            base_input.update({
                "expected": "valid JSON format",
                "guidance": "Check JSON syntax, quotes, and brackets"
            })
        elif error.error_type == ParseErrorType.INVALID_FORMAT:
            base_input.update({
                "expected": "recognized output format",
                "guidance": "Follow the specified output format exactly"
            })
        
        # Add custom context
        base_input.update(error.context)
        
        return base_input
    
    def _create_safe_action(
        self, 
        tool: str, 
        tool_input: Dict[str, Any], 
        reasoning: str = "",
        error: Optional[str] = None,
        id: Optional[str] = None
    ) -> AgentAction:
        """
        Helper to create AgentAction with safe defaults.
        
        Args:
            tool: Tool name
            tool_input: Tool input dictionary
            reasoning: Optional reasoning text
            error: Optional error message
            id: Optional action ID (uses UUID if None)
            
        Returns:
            AgentAction with safe defaults
        """
        action_kwargs = {
            "tool": tool,
            "tool_input": tool_input,
            "reasoning": reasoning or f"Using {tool}",
            "error": error
        }
        
        if id is not None:
            action_kwargs["id"] = id
            
        return AgentAction(**action_kwargs)
    
    def _create_safe_finish(
        self,
        output: str,
        reasoning: str = "",
        return_values: Optional[Dict[str, Any]] = None
    ) -> AgentFinish:
        """
        Helper to create AgentFinish with safe defaults.
        
        Args:
            output: Final output
            reasoning: Optional reasoning
            return_values: Optional return values
            
        Returns:
            AgentFinish with safe defaults  
        """
        return AgentFinish(
            output=output,
            reasoning=reasoning or "Providing final answer",
            return_values=return_values or {}
        )
