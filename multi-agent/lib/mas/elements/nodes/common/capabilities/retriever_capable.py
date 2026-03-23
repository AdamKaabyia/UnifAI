from typing import Any
from mas.elements.llms.common.chat.message import ChatMessage


class RetrieverCapableMixin:
    """Adds document retrieval."""

    def __init__(self, *, retriever: Any = None, **kwargs: Any):
        super().__init__(**kwargs)  # MRO
        self.retriever = retriever

    def _retrieve(self, query: str) -> str:
        return "" if self.retriever is None else self.retriever.retrieve(query)

    def augment_with_context(self, user_message: ChatMessage) -> ChatMessage:
        """
        If a retriever is available, retrieves context for the user message's content
        and returns a new ChatMessage with the context prepended.
        If no retriever or no content, returns the original message.
        If no context is found, returns the original message.
        """
        if not self.retriever or not user_message.content:
            return user_message  # No retriever or no content to retrieve for

        prompt = user_message.content
        ctx = self._retrieve(prompt)  # Use the existing _retrieve method

        if not ctx:  # No context was retrieved
            return user_message

        # Return a new ChatMessage with the context added
        return ChatMessage(
            role=user_message.role,  # Retain the original message's role (e.g., Role.USER)
            content=f"context: {ctx}\nuser:\n{prompt}"  # Standardized format
        )
