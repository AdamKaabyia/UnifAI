from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, List, Union
from mas.elements.tools.common.base_tool import BaseTool
from .chat.message import ChatMessage


class BaseLLM(ABC):
    """
    Abstract base class for all LLM integrations (OpenAI, LlamaStack, etc.)
    """

    @abstractmethod
    def chat(self, messages: List[ChatMessage], stream: bool = False) -> ChatMessage:
        """
        Perform a conversational completion.
        messages = list of {"role": "user"/"assistant", "content": "..."}
        """
        pass

    @abstractmethod
    def stream(self, messages: List[ChatMessage], **call_params: Any) -> Iterator[Union[str, ChatMessage]]:
        """
        Stream conversational completion with real-time token generation.
        
        Yields either incremental text tokens (str) or complete ChatMessage objects.
        For tool calling, yields final ChatMessage with tool_calls populated.
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """
        Returns the identifier for the LLM (for logging/debug).
        """
        pass

    @abstractmethod
    def bind_tools(self, tools: List[BaseTool]) -> "BaseLLM":
        """
        Bind tools to the LLM, returning a new instance to avoid cross-contamination.
        
        Returns:
            A new LLM instance with tools bound, leaving the original unchanged.
        """
        pass
