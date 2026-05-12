import asyncio
from typing import Optional, Type, Any, Union
from abc import ABC, abstractmethod
from pydantic import BaseModel


class BaseTool(ABC):
    """
    Abstract base class for all tools.

    Subclass this and implement `run()` (and optionally `arun()`).
    Provide ``name``, ``description``, and an optional Pydantic
    ``args_schema`` whose JSON Schema is used by LLM providers
    for function-calling.
    """

    name: str
    description: str
    args_schema: Optional[Union[Type[BaseModel], dict[str, Any], Any]] = None

    @abstractmethod
    def run(
            self,
            *args: Any,
            **kwargs: Any
    ) -> Any:
        """
        Synchronous execution logic. Must be implemented by subclass.
        """
        raise NotImplementedError("run must be implemented by subclasses")

    async def arun(self, *args: Any, **kwargs: Any) -> Any:
        """Default async wrapper - runs sync method in thread pool."""
        return await asyncio.to_thread(self.run, *args, **kwargs)

    def get_args_schema_json(self):
        return self.args_schema.model_json_schema()

    def get_args_schema_model(self):
        return self.args_schema
