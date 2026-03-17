from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Threshold Condition."""
    TYPE = "threshold"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Threshold Condition",
    description="Triggers when the state's value crosses the numeric threshold",
    tags=["condition", "threshold", "numeric"],
)
