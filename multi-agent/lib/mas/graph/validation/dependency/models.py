from typing import Literal
from enum import Enum
from pydantic import BaseModel, ConfigDict


class DependencyIssueType(str, Enum):
    MISSING_STEP = "missing_step"
    MISSING_BRANCH_TARGET = "missing_branch_target"


class DependencyType(str, Enum):
    AFTER = "after"
    BRANCH = "branch"


class DependencyFixType(str, Enum):
    CREATE_MISSING_STEP = "create_missing_step"
    REMOVE_DEPENDENCY = "remove_dependency"
    REPLACE_WITH_EXISTING = "replace_with_existing"
    CREATE_MISSING_TARGET = "create_missing_target"
    REMOVE_BRANCH = "remove_branch"
    REDIRECT_TO_EXISTING = "redirect_to_existing"


class DependencyIssue(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    step_id: str
    missing_dependency: str
    issue_type: DependencyIssueType 