from typing import Set
from enum import Enum
from pydantic import BaseModel, ConfigDict


class NodePosition(str, Enum):
    START = "start"
    END = "end"
    ANY = "any"


class RequiredNodeFixType(str, Enum):
    ADD_REQUIRED_START = "add_required_start"
    ADD_REQUIRED_END = "add_required_end"
    ADD_REQUIRED_ANYWHERE = "add_required_anywhere"


class RequiredNodeIssue(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    node_type: NodePosition
    expected: str
    actual: str | None


class RequiredNodesDetails(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    required_node_issues: list[RequiredNodeIssue]
    missing_start_nodes: Set[str]
    missing_end_nodes: Set[str] 