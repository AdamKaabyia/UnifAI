from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Router Boolean condition."""
    TYPE = "router_boolean"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Router Boolean",
    description="Returns a configured boolean value (true/false) for symbolic branching",
    tags=["router_boolean", "condition", "boolean", "symbolic", "config"],
)