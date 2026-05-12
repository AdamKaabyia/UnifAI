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
"""

from __future__ import annotations

from typing import Any, List, Optional, Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from mas.elements.tools.common.base_tool import BaseTool


def domain_tool_to_langchain(tool: BaseTool) -> StructuredTool:
    """Convert a single domain ``BaseTool`` to a LangChain ``StructuredTool``."""
    args_schema = _resolve_args_schema(tool)

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        func=tool.run,
        coroutine=tool.arun,
        args_schema=args_schema,
    )


def domain_tools_to_langchain(tools: List[BaseTool]) -> List[StructuredTool]:
    """Convert a list of domain ``BaseTool`` instances to LangChain tools."""
    return [domain_tool_to_langchain(t) for t in tools]


def _resolve_args_schema(tool: BaseTool) -> Optional[Type[BaseModel]]:
    """Extract a Pydantic model from the domain tool's ``args_schema``.

    Domain tools may carry:
      - A Pydantic ``BaseModel`` subclass  → pass through directly
      - A plain ``dict`` (JSON schema)     → dynamically build a Pydantic model
      - ``None``                           → let LangChain infer from the callable
    """
    schema = getattr(tool, "args_schema", None)
    if schema is None:
        return None

    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema

    if isinstance(schema, dict):
        return _dict_schema_to_model(tool.name, schema)

    return None


def _dict_schema_to_model(tool_name: str, schema: dict) -> Type[BaseModel]:
    """Build a dynamic Pydantic model from a JSON-schema dict.

    Uses ``get_args_schema_json()`` output (``{"type": "object", "properties": ...}``)
    to create a lightweight model that LangChain's tool infrastructure can consume.
    """
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    field_definitions: dict[str, Any] = {}
    for field_name, field_schema in properties.items():
        python_type = _json_type_to_python(field_schema.get("type", "string"))
        default = ... if field_name in required_fields else None
        field_definitions[field_name] = (python_type, default)

    model_name = f"{tool_name.replace('-', '_').title().replace('_', '')}Schema"
    return type(model_name, (BaseModel,), {"__annotations__": {
        name: defn[0] for name, defn in field_definitions.items()
    }, **{
        name: defn[1] for name, defn in field_definitions.items()
    }})


_JSON_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _json_type_to_python(json_type: str) -> type:
    """Map a JSON schema type string to a Python type."""
    return _JSON_TYPE_MAP.get(json_type, Any)
