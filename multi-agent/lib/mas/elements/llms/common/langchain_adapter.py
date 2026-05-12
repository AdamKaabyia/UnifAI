"""
Adapter that presents any domain ``BaseLLM`` as a LangChain ``BaseChatModel``.

This lets LangChain-based systems (Deep Agents, LangGraph, chains) use
any of our LLM implementations transparently::

    from deepagents import create_deep_agent

    adapter = BaseLLMChatModelAdapter(llm=my_openai_llm)
    agent   = create_deep_agent(model=adapter, tools=[...])

The adapter delegates all work to the underlying ``BaseLLM`` and converts
between LangChain message types and domain ``ChatMessage`` objects using
the existing ``LangChainConverter``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict

from ..common.base_llm import BaseLLM
from ..common.chat.converter import LangChainConverter
from ..common.chat.message import ChatMessage
from ...tools.common.base_tool import BaseTool


# ---------------------------------------------------------------------------
# Schema-only domain tool (LangChain → domain bridge for bind_tools)
# ---------------------------------------------------------------------------

class _SchemaOnlyTool(BaseTool):
    """Lightweight domain tool carrying only the schema extracted from a LangChain tool.

    Used exclusively by ``BaseLLMChatModelAdapter.bind_tools()`` to forward
    tool definitions to the underlying ``BaseLLM``.  Execution never goes
    through this class — LangChain's agent loop handles tool execution.
    """

    def __init__(self, name: str, description: str, parameters: Dict[str, Any]) -> None:
        self.name = name
        self.description = description
        self._parameters = parameters

    def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            f"Tool '{self.name}' is schema-only and cannot be executed directly. "
            "Tool execution is handled by the LangChain agent loop."
        )

    def get_args_schema_json(self) -> Dict[str, Any]:
        return self._parameters


def _to_domain_tool(
    tool: Union[Dict[str, Any], type, Callable, LangChainBaseTool],
) -> _SchemaOnlyTool:
    """Convert any LangChain-accepted tool format to a domain ``_SchemaOnlyTool``."""
    openai_schema = convert_to_openai_tool(tool)
    func = openai_schema.get("function", openai_schema)
    return _SchemaOnlyTool(
        name=func["name"],
        description=func.get("description", ""),
        parameters=func.get("parameters", {"type": "object", "properties": {}}),
    )


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

class BaseLLMChatModelAdapter(BaseChatModel):
    """Wraps any domain ``BaseLLM`` as a LangChain ``BaseChatModel``.

    This enables usage with LangChain agents, LangGraph, Deep Agents,
    and any other LangChain-based system that expects a ``BaseChatModel``.

    Example::

        adapter = BaseLLMChatModelAdapter(llm=OpenAILLM(...))
        result  = adapter.invoke([HumanMessage(content="Hello")])
    """

    llm: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ------------------------------------------------------------------
    # Required overrides
    # ------------------------------------------------------------------

    @property
    def _llm_type(self) -> str:
        return f"unifai-{self.llm.name}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        domain_msgs = LangChainConverter.from_lc(messages)
        result = self.llm.chat(domain_msgs)
        ai_message = LangChainConverter.to_lc_message(result)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    # ------------------------------------------------------------------
    # Optional: streaming
    # ------------------------------------------------------------------

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        domain_msgs = LangChainConverter.from_lc(messages)
        for token_or_msg in self.llm.stream(domain_msgs):
            if isinstance(token_or_msg, str):
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content=token_or_msg),
                )
            elif isinstance(token_or_msg, ChatMessage):
                yield ChatGenerationChunk(
                    message=LangChainConverter.to_lc_message_chunk(token_or_msg),
                )

    # ------------------------------------------------------------------
    # Optional: tool binding
    # ------------------------------------------------------------------

    def bind_tools(
        self,
        tools: Sequence[Dict[str, Any] | type | Callable | LangChainBaseTool],
        *,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseLLMChatModelAdapter:
        """Bind LangChain-format tools to the underlying ``BaseLLM``.

        Converts each tool to a domain schema via ``convert_to_openai_tool``,
        delegates to ``BaseLLM.bind_tools()``, and returns a new adapter
        wrapping the tool-bound LLM.
        """
        domain_tools: List[BaseTool] = [_to_domain_tool(t) for t in tools]
        bound_llm = self.llm.bind_tools(domain_tools)
        return BaseLLMChatModelAdapter(llm=bound_llm)
