from typing import Dict, List, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from .models import MessageCode


class FixType(str, Enum):
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    MODIFY_CONNECTION = "modify_connection"
    ADD_CHANNEL = "add_channel"


class FixSuggestion(BaseModel):
    """A specific actionable fix suggestion."""
    model_config = ConfigDict(frozen=True)
    
    text: str
    fix_type: FixType
    code: MessageCode | None = None  # Links to validation message
    context: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0  # Higher = more important


class FixReport(BaseModel):
    """Collection of fix suggestions from a single provider."""
    model_config = ConfigDict(frozen=True)
    
    provider_name: str
    suggestions: List[FixSuggestion] = Field(default_factory=list)
    
    @property
    def has_suggestions(self) -> bool:
        return len(self.suggestions) > 0