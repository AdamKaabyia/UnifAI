"""
Bridge between domain ``BaseTool`` and LangChain ``StructuredTool``.

Deep Agents' ``create_deep_agent`` accepts ``Callable | LangChainBaseTool | dict``
for its ``tools`` parameter.  This module converts any domain ``BaseTool`` into a
LangChain ``StructuredTool`` that preserves name, description, schema, and both
sync/async execution paths.

Why ``StructuredTool`` and not a bare callable?
    A bare ``tool.run`` reference loses the tool's name, description, and JSON
    schema.  ``StructuredTool`` is LangChain's canonical wrapper that carries all
    three, so the Deep Agent LLM sees proper function-calling metadata.

Schema handling:
    ``StructuredTool.args_schema`` accepts both a Pydantic ``BaseModel`` subclass
    and a raw JSON-schema ``dict``.  We use ``BaseTool.get_args_schema_json()``
    to obtain the schema as a dict, which preserves full fidelity (enum
    constraints, descriptions, defaults, nested types) without lossy conversion.
"""

from __future__ import annotations

from typing import List

from langchain_core.tools import StructuredTool

from mas.elements.tools.common.base_tool import BaseTool


def domain_tool_to_langchain(tool: BaseTool) -> StructuredTool:
    """Convert a single domain ``BaseTool`` to a LangChain ``StructuredTool``."""
    schema = tool.get_args_schema_json() if tool.args_schema else None

    return StructuredTool(
        name=tool.name,
        description=tool.description or "",
        func=tool.run,
        coroutine=tool.arun,
        args_schema=schema,
    )


def domain_tools_to_langchain(tools: List[BaseTool]) -> List[StructuredTool]:
    """Convert a list of domain ``BaseTool`` instances to LangChain tools."""
    return [domain_tool_to_langchain(t) for t in tools]
