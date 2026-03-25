from typing import Set, Optional
import json
from pydantic import Field
from pydantic_settings import BaseSettings


class ValidationSettings(BaseSettings):
    """Environment-driven settings for graph validation rules."""

    required_start_nodes: Set[str] = Field(default_factory=lambda: {"user_question_node"})
    required_end_nodes: Set[str] = Field(default_factory=lambda: {"final_answer_node"})
    required_any_nodes: Set[str] = Field(default_factory=set)
    
    # Maximum node constraints (None = unlimited)
    max_start_nodes: Optional[int] = Field(default=1)
    max_end_nodes: Optional[int] = Field(default=1)
    max_any_nodes: Optional[int] = Field(default=30)

    class Config:
        env_prefix = "GRAPH_"  # e.g. GRAPH_REQUIRED_START_NODES, GRAPH_MAX_END_NODES
        case_sensitive = False