"""
Output parsing system with error recovery.

DEPRECATED: This module is kept for backward compatibility.
Use the new parser system in agent.parsers instead.

The parsers have been refactored into a proper directory structure:
- agent.parsers.base: Base classes and protocols
- agent.parsers.tool_call_parser: Tool call parsing (default)  
- agent.parsers.text_parser: Structured text parsing
- agent.parsers.json_parser: JSON format parsing
- agent.parsers.registry: Parser registry and factory

For new code, use:
    from agent.parsers import ParserFactory, ParserRegistry
    
    parser = ParserFactory.create("tool_call")
    result = parser.parse(message)
"""

import warnings
from .parsers.base import ParseError, OutputParser, BaseOutputParser, ParserConfig
from .parsers.tool_call_parser import ToolCallParser
from .parsers.text_parser import TextParser as CustomTextParser
from .parsers.registry import ParserFactory, ParserRegistry

# Issue deprecation warning when this module is imported
warnings.warn(
    "agent.parsing is deprecated. Use agent.parsers instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
__all__ = [
    "ParseError",
    "OutputParser", 
    "BaseOutputParser",
    "ParserConfig",
    "ToolCallParser",
    "CustomTextParser",
    "ParserFactory",
    "ParserRegistry"
]
