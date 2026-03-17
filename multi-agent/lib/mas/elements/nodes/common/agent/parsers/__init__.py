"""
Agent output parsing system.

This module provides a comprehensive parsing system for converting LLM outputs
into agent actions and finishes. Supports multiple parser types with a common
interface and registry system.

Available Parsers:
- ToolCallParser: Parses ChatMessage.tool_calls (default)
- TextParser: Parses structured text formats
- JsonParser: Parses JSON-formatted responses
- CustomParser: Base for custom implementations

Registry System:
- ParserRegistry: Central registry for parser discovery
- ParserFactory: Creates parsers by name with configuration

Example:
    ```python
    from agent.parsers import ParserRegistry, ParseError
    
    # Get parser by name
    parser = ParserRegistry.get_parser("tool_call")
    
    # Parse LLM output
    try:
        result = parser.parse(message)
        if isinstance(result, list):
            # Got actions
            pass
        else:
            # Got finish
            pass
    except ParseError as e:
        # Handle parsing error
        recovery_action = parser.parse_error_recovery(e)
    ```
"""

from .base import BaseOutputParser, OutputParser, ParseError, ParseErrorType, ParserConfig
from .tool_call_parser import ToolCallParser
from .text_parser import TextParser, TextParserConfig
from .json_parser import JsonParser, JsonParserConfig
from .registry import ParserRegistry, ParserFactory

# Register default parsers with metadata
ParserRegistry.register(
    "tool_call", 
    ToolCallParser,
    description="Parses ChatMessage.tool_calls format (default)",
    supported_formats=["tool_calls", "function_calls"],
    priority=90
)

ParserRegistry.register(
    "text", 
    TextParser,
    config_class=TextParserConfig,
    description="Parses structured text formats (ReAct, etc.)",
    supported_formats=["react", "text", "structured"],
    priority=70
)

ParserRegistry.register(
    "json", 
    JsonParser,
    config_class=JsonParserConfig,
    description="Parses JSON-formatted responses",
    supported_formats=["json", "openai_functions"],
    priority=80
)

__all__ = [
    # Base classes
    "BaseOutputParser",
    "OutputParser",
    "ParseError",
    "ParseErrorType",
    "ParserConfig",
    
    # Parser implementations
    "ToolCallParser",
    "TextParser",
    "TextParserConfig",
    "JsonParser",
    "JsonParserConfig",
    
    # Registry system
    "ParserRegistry",
    "ParserFactory"
]
