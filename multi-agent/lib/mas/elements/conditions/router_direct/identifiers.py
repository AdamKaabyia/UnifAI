from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Router Direct condition."""
    TYPE = "router_direct"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Router Direct",
    description="Reads target_branch from state and returns it directly for branching",
    tags=["router_direct", "condition", "branch", "target", "direct"],
)