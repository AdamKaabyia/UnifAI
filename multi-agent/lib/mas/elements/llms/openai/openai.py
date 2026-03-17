from typing import Any, Dict, List, Optional, Iterator, Union
import copy
from langchain_openai import ChatOpenAI
from ..common.base_llm import BaseLLM
from mas.core.contracts import SupportsStreaming
from ..common.chat.converter import LangChainConverter
from ..common.chat.message import ChatMessage
from ...tools.common.base_tool import BaseTool
from ...tools.common.converter import LangChainToolsConverter


class OpenAILLM(BaseLLM, SupportsStreaming):
    """
    LLM client for vLLM-served Qwen model using LangChain's ChatOpenAI wrapper.
    """

    def __init__(
            self,
            base_url: str,
            model_name: str,
            temperature: float = 0.7,
            max_tokens: int = 1024,
            api_key: str = "EMPTY",
            **extra: Any
    ):
        """
        :param base_url:     vLLM API base (OpenAI-compatible).
        :param model_name:   Qwen model ID (e.g. "Qwen/Qwen1.5-7B-Chat").
        :param temperature:  Sampling temperature.
        :param max_tokens:   Max tokens to generate.
        :param extra:        Extra kwargs passed to ChatOpenAI.
        """
        self._name = "vllm-qwen"
        self.client = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            **extra
        )

    def chat(
            self,
            messages: List[ChatMessage],
            *,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
            stream: bool = False,
            **kwargs: Any
    ) -> ChatMessage:
        """
        Send a chat request to the vLLM model.

        :param messages: List of {"role": "user"/"assistant"/"system", "content": "..."}
        """
        call_params: Dict[str, Any] = {}
        if temperature is not None:
            call_params["temperature"] = temperature
        if max_tokens is not None:
            call_params["max_tokens"] = max_tokens
        call_params.update(kwargs)

        # Convert to LangChain message objects
        lc_messages = LangChainConverter.to_lc(messages)

        response = self.client.invoke(lc_messages, stream=stream, **call_params)
        return LangChainConverter.from_lc_message(response)

    def stream(
            self,
            messages: List[ChatMessage],
            **call_params: Any,
    ) -> Iterator[Union[str, ChatMessage]]:
        """
        Provider-level streaming:

        • Yields `str` tokens for regular answers.
        • Aggregates *all* `tool_call_chunks` via the LangChain "+" operator
          and, at the very end, yields **one** `ChatMessage` representing
          the full assistant reply with `tool_calls=[…]`.
        """
        # Translate our domain history → LangChain
        lc_history = LangChainConverter.to_lc(messages)

        aggregated: Any | None = None  # will hold the growing AIMessage

        for chunk in self.client.stream(lc_history, stream=True, **call_params):
            # Tool-call partials -------------------------------------------------
            if getattr(chunk, "tool_call_chunks", None):
                aggregated = chunk if aggregated is None else aggregated + chunk
                # we do NOT yield yet — wait until provider is done
                continue

            # Plain token path --------------------------------------------------
            token = chunk.content or ""
            if token:
                yield token

        # Provider finished ------------------------------------------------------
        if aggregated:
            # LangChain "+" produced a final AIMessage with complete tool_calls,
            # Convert once to our ChatMessage model and yield it.
            yield LangChainConverter.from_lc_message(aggregated)

    def bind_tools(self, tools: List[BaseTool]) -> "OpenAILLM":
        """
        Return a new OpenAILLM instance with tools bound, avoiding cross-contamination.
        
        This creates a copy of the current LLM with tools bound to the client,
        ensuring the original LLM instance remains unchanged.
        """
        # Create a shallow copy of the current instance
        new_llm = copy.copy(self)
        
        # Create a new client with tools bound (LangChain's bind_tools returns a copy)
        new_llm.client = self.client.bind_tools(LangChainToolsConverter.to_lc(tools))
        
        return new_llm

    @property
    def name(self) -> str:
        return self._name
