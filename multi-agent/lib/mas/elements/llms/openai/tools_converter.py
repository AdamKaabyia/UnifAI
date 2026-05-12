"""
Converter from domain BaseTool to OpenAI-native tool definitions.

Uses the SDK's own ``ChatCompletionToolParam`` and ``FunctionDefinition``
TypedDicts so the output is type-checked against the API spec — misspelled
keys or wrong value types are caught by the type checker, not at runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionToolParam
from openai.types.shared_params import FunctionDefinition

from ...tools.common.base_tool import BaseTool

_EMPTY_PARAMETERS: Dict[str, Any] = {"type": "object", "properties": {}}


class OpenAIToolsConverter:
    """Converts domain ``BaseTool`` instances into OpenAI ``ChatCompletionToolParam`` dicts."""

    @staticmethod
    def to_openai(tools: Optional[List[BaseTool]]) -> Optional[List[ChatCompletionToolParam]]:
        if not tools:
            return None
        return [OpenAIToolsConverter._convert(t) for t in tools]

    @staticmethod
    def _convert(tool: BaseTool) -> ChatCompletionToolParam:
        parameters = tool.get_args_schema_json()

        function: FunctionDefinition = {
            "name": tool.name,
            "description": tool.description,
            "parameters": parameters if parameters is not None else _EMPTY_PARAMETERS,
        }

        return ChatCompletionToolParam(
            type="function",
            function=function,
        )
