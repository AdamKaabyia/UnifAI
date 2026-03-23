from enum import Enum
from typing import List, Union
from pydantic import BaseModel, Field


class BranchType(str, Enum):
    SYMBOLIC = "symbolic"  # Pre-defined symbols that need mapping
    DIRECT = "direct"  # Returns node UIDs directly
    FLEXIBLE = "flexible"  # Can return either symbolic or direct


class SymbolicBranchDef(BaseModel):
    """Defines a symbolic branch with a fixed name and description."""
    name: Union[str, bool, int, float] = Field(..., description="Branch symbol (literal value)")
    display_name: str = Field(..., description="Human-readable label")
    description: str = Field("", description="What this branch represents")


class DirectBranchDef(BaseModel):
    """Defines direct branching rules."""
    description: str = Field("", description="What direct branches represent")


class ConditionOutputSchema(BaseModel):
    """Defines what outputs a condition can produce and how they map to branches."""
    branch_type: BranchType = Field(..., description="Type of branching this condition supports")

    # For symbolic branches
    symbolic_branches: List[SymbolicBranchDef] = Field(default_factory=list)

    # For direct branches  
    direct_config: DirectBranchDef = Field(default_factory=lambda: DirectBranchDef())

    # Metadata
    default_branch: str = Field(None, description="Default branch if no match")
    description: str = Field("", description="Overall description of the branching logic")
