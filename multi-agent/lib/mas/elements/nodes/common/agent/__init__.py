"""
Agent orchestration system for multi-agent framework.

This module provides a SOLID architecture for agent behavior:
- Core primitives for actions, observations, and state
- Pluggable strategies for different agent approaches (ReAct, PlanAndExecute, etc.)
- Execution control with multiple modes (auto, guided)
- Integration with existing mixin capabilities

Key Components:
- AgentAction: Represents intent to use a tool
- AgentObservation: Tool execution result
- AgentFinish: Final agent output
- AgentStrategy: Planning and decision-making logic
- AgentIterator: Step-by-step execution control
- AgentActionExecutor: Bridge to existing tool system

Example:
    ```python
    from agent import ReActStrategy, AgentIterator, AgentActionExecutor
    
    # In your AgentCapableMixin
    strategy = ReActStrategy(llm_chat=self._chat)
    executor = AgentActionExecutor(self.tools)
    iterator = AgentIterator(strategy=strategy, tool_executor=executor.execute)
    
    for step in iterator:
        if step.type == StepType.FINISH:
            return step.data.output
    ```
"""

from .primitives import (
    AgentAction,
    AgentObservation,
    AgentFinish,
    AgentStep,
    StepType,
    ActionStatus,
    SystemError,
    ActionObservationPair,
    ExecutionHistory
)

from .parsing import (
    OutputParser,
    ParseError,
    ToolCallParser,
    CustomTextParser
)

from .strategies import (
    AgentStrategy,
    ReActStrategy
)

from .execution import (
    AgentIterator,
    ExecutionMode,
    AgentActionExecutor,
)

from .runner import (
    AgentRunner,
    RunnerConfig,
    StreamingRunner
)

from .config import (
    AgentConfig
)

from .constants import (
    StrategyType,
    SpecialToolNames,
    ToolHandlingPolicy,
    EarlyStoppingPolicy,
    ParserType,
    StrategyDefaults,
    ToolExecutionDefaults,
    ExecutionDefaults,
    ParserDefaults
)

__all__ = [
    # Core primitives
    "AgentAction",
    "AgentObservation", 
    "AgentFinish",
    "AgentStep",
    "StepType",
    "ActionStatus",
    "SystemError",
    "ActionObservationPair",
    "ExecutionHistory",
    
    # Parsing
    "OutputParser",
    "ParseError",
    "ToolCallParser",
    "CustomTextParser",
    
    # Strategies
    "AgentStrategy",
    "ReActStrategy",
    
    # Execution
    "AgentIterator",
    "ExecutionMode",
    "AgentActionExecutor", 
    
    # Runners
    "AgentRunner",
    "RunnerConfig",
    "StreamingRunner",
    
    # Configuration
    "AgentConfig",
    
    # Constants and enums
    "StrategyType",
    "SpecialToolNames",
    "ToolHandlingPolicy",
    "EarlyStoppingPolicy",
    "ParserType",
    "StrategyDefaults",
    "ToolExecutionDefaults",
    "ExecutionDefaults",
    "ParserDefaults"
]
