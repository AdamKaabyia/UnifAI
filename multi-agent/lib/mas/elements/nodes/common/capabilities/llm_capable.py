from mas.elements.llms.common.chat.message import ChatMessage, Role
from typing import Any, TypeVar, Generic, List, ClassVar, Optional
from mas.core.contracts import SupportsStreaming
from mas.elements.llms.common.base_llm import BaseLLM
from mas.elements.tools.common.base_tool import BaseTool

TSupportStream = TypeVar("TSupportStream", bound=SupportsStreaming)


class LlmCapableMixin(Generic[TSupportStream]):
    """
    Clean LLM capability mixin with streaming support.
    
    Provides chat functionality with optional tool binding, supporting both
    streaming and non-streaming modes. Designed for composition with other
    node capabilities.
    
    Responsibilities:
    - LLM chat with optional dynamic tool binding
    - Streaming token forwarding when enabled
    - Clean separation between sync and async operations
    
    Requirements:
    - Host class must implement SupportsStreaming (_stream, is_streaming)
    """

    MIXIN_READS: ClassVar[set[str]] = set()
    MIXIN_WRITES: ClassVar[set[str]] = set()

    def __init_subclass__(cls) -> None:
        """Verify that host class implements required streaming interface."""
        if not issubclass(cls, SupportsStreaming):
            raise TypeError(
                f"{cls.__name__} requires streaming support (_stream + is_streaming)."
            )
        super().__init_subclass__()

    def __init__(
            self,
            *,
            llm: BaseLLM,
            system_message: str = "",
            **kwargs: Any,
    ):
        """
        Initialize LLM capability.

        Args:
            llm: LLM instance providing chat() and stream() methods
            system_message: Optional system prompt for conversations
        """
        super().__init__(**kwargs)
        self.llm = llm
        self.system_message = system_message

    # -------------------------------------------------------------------------
    # Public API - Core Methods
    # -------------------------------------------------------------------------

    def chat(
            self: TSupportStream,
            messages: List[ChatMessage],
            tools: Optional[List[BaseTool]] = None
    ) -> ChatMessage:
        """
        Primary chat interface with optional dynamic tool binding.
        
        Supports both streaming and non-streaming modes. When tools are provided,
        creates a temporary LLM instance with tools bound for this specific call.
        
        Args:
            messages: Conversation messages to send to LLM
            tools: Optional tools to bind for this specific chat
            
        Returns:
            ChatMessage response from LLM
        """
        # Print compact chat history before LLM call
        print(f"\n💬 Chat ({len(messages)} messages):")
        for i, msg in enumerate(messages, 1):
            role_icon = "👤" if msg.role.value == "user" else "🤖" if msg.role.value == "assistant" else "⚙️"
            # Show very compact: first 80 chars only
            content = msg.content.replace('\n', ' ')[:80]
            if len(msg.content) > 80:
                content += "..."
            print(f"   {i}. {role_icon} {content}")
        
        llm_instance = self.llm.bind_tools(tools)

        if self.is_streaming():
            return self._stream_chat(messages, llm_instance)
        else:
            return llm_instance.chat(messages)

    def bind_tools(self, tools: List[BaseTool]) -> None:
        """
        Permanently bind tools to this instance's LLM.
        
        Creates a new LLM instance with tools bound, replacing the current one.
        Use sparingly - prefer dynamic binding via chat(tools=...) for most use cases.
        
        Args:
            tools: Tools to bind permanently to this LLM instance
        """
        self.llm = self.llm.bind_tools(tools)

    def _stream_chat(
            self: TSupportStream,
            messages: List[ChatMessage],
            llm_instance: BaseLLM,
            *,
            event_type: str = "llm_token"
    ) -> ChatMessage:
        """
        Handle streaming chat with any LLM instance.
        
        Processes streaming responses and forwards tokens via _stream() when
        streaming is enabled. Handles both token streams and complete messages.
        
        Args:
            messages: Messages to send to LLM
            llm_instance: LLM instance to use (may have tools bound)
            event_type: Event type for streaming tokens
            
        Returns:
            Final ChatMessage from LLM
        """
        accumulated_text = ""
        final_message: Optional[ChatMessage] = None

        for chunk in llm_instance.stream(messages):
            if isinstance(chunk, str):
                # Token chunk - accumulate and stream
                accumulated_text += chunk
                if self.is_streaming():
                    self._stream({"type": event_type, "chunk": chunk})

            elif isinstance(chunk, ChatMessage):
                # Complete message (possibly with tool calls)
                final_message = chunk
                break
            else:
                raise TypeError(
                    f"LLM stream returned unexpected type: {type(chunk)}"
                )

        # Return final message or construct from accumulated tokens
        return final_message or ChatMessage(
            role=Role.ASSISTANT,
            content=accumulated_text
        )
