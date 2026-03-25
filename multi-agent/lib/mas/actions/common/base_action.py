from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Union, Set, Optional, Tuple
from pydantic import BaseModel
from .action_models import ActionType
import inspect
from global_utils.utils.async_bridge import get_async_bridge


class BaseAction(ABC):
    """
    Base action interface supporting both sync and async execution.
    Actions are independent units that can operate on any compatible element.
    """

    # Required action metadata (to be defined by subclasses)
    uid: str                                    # Unique identifier for action
    name: str                                   # Human-readable name
    description: str                            # Action description
    action_type: ActionType                     # Type category
    input_schema: Type[BaseModel]               # Input validation schema
    output_schema: Type[BaseModel]              # Output schema
    
    # Optional metadata
    version: str = "1.0.0"                     # Action version
    tags: Set[str] = set()                     # Action tags
    elements: Set[Tuple[str, str]] = set()     # Element tuples (category, type) this action works with
    
    def __init_subclass__(cls, **kwargs):
        """Validate that required attributes are defined"""
        super().__init_subclass__(**kwargs)
        
        required_attrs = ['uid', 'name', 'description', 'action_type', 'input_schema', 'output_schema']
        missing = [attr for attr in required_attrs if not hasattr(cls, attr) or getattr(cls, attr) is None]
        
        if missing:
            raise TypeError(f"{cls.__name__} is missing required action attributes: {missing}")

    @abstractmethod
    def execute(self, input_data: BaseModel, context: Optional[Dict[str, Any]] = None) -> Union[BaseModel, Any]:
        """
        Execute the action with validated input.
        
        Args:
            input_data: Validated input according to input_schema
            context: Optional execution context (element configs, etc.)
            
        Returns:
            Result according to output_schema (sync or awaitable)
        """
        pass

    def execute_sync(self, input_data: BaseModel, context: Optional[Dict[str, Any]] = None) -> BaseModel:
        """
        Execute the action synchronously.
        If the action is async, this will run it using AsyncBridge for safe execution.
        
        Args:
            input_data: Validated input according to input_schema
            context: Optional execution context
            
        Returns:
            Result according to output_schema
        """
        result = self.execute(input_data, context)

        # If the result is a coroutine, run it using AsyncBridge
        if inspect.iscoroutine(result):
            with get_async_bridge() as bridge:
                return bridge.run(result)

        # Otherwise, return the sync result
        return result

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get action metadata for API consumers"""
        return {
            "uid": cls.uid,
            "name": cls.name,
            "description": cls.description,
            "action_type": cls.action_type.value,
            "version": getattr(cls, 'version', '1.0.0'),
            "tags": list(getattr(cls, 'tags', set())),
            "elements": [{"category": cat, "type": typ} for cat, typ in getattr(cls, 'elements', set())],
            "input_schema": cls.input_schema.model_json_schema(),
            "output_schema": cls.output_schema.model_json_schema()
        }

    def validate_input(self, input_data: Dict[str, Any]) -> BaseModel:
        """Validate input data against input schema"""
        return self.input_schema.model_validate(input_data)
