"""
Agent strategy implementations.

This module provides different approaches to agent planning and decision-making.
Each strategy implements the AgentStrategy protocol to determine what actions
the agent should take based on current context and history.

Available Strategies:
- ReActStrategy: Reasoning and Acting in interleaved fashion
- PlanExecuteStrategy: Plan first, then execute (future)
- CustomStrategy: Base for custom implementations

Example:
    ```python
    from agent.strategies import ReActStrategy
    from agent.parsing import ToolCallParser
    
    strategy = ReActStrategy(
        llm_chat=node._chat,
        parser=ToolCallParser(),
        max_steps=10
    )
    
    steps = strategy.think(messages, observations)
    ```
"""

from .base import AgentStrategy
from .react import ReActStrategy

__all__ = [
    "AgentStrategy",
    "ReActStrategy"
]
