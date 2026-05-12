"""
Converter from domain BaseTool to Google GenAI-native tool definitions.

Uses the SDK's ``types.FunctionDeclaration`` and ``types.Tool`` Pydantic models
so the output is validated against the API spec at construction time.

Google GenAI has stricter schema validation than other providers, so
``SchemaSanitizer`` is applied to remove patterns that would be rejected
(empty properties, title-only fields, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from google.genai import types

from ...tools.common.base_tool import BaseTool
from .schema_sanitizer import SchemaSanitizer

_EMPTY_PARAMETERS: Dict[str, Any] = {"type": "object", "properties": {}}


class GoogleGenAIToolsConverter:
    """Converts domain ``BaseTool`` instances into a Google GenAI ``types.Tool``."""

    @staticmethod
    def to_genai(tools: Optional[List[BaseTool]]) -> Optional[List[types.Tool]]:
        """Convert domain tools to Google GenAI format.

        Returns a list containing a single ``types.Tool`` with all function
        declarations, or *None* if no tools are provided.
        """
        if not tools:
            return None

        declarations = [GoogleGenAIToolsConverter._to_declaration(t) for t in tools]

        return [types.Tool(function_declarations=declarations)]

    @staticmethod
    def _to_declaration(tool: BaseTool) -> types.FunctionDeclaration:
        """Convert a single domain tool to a ``FunctionDeclaration``."""
        raw_schema = tool.get_args_schema_json()
        parameters = SchemaSanitizer.sanitize(raw_schema) if raw_schema else _EMPTY_PARAMETERS

        return types.FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters_json_schema=parameters,
        )
