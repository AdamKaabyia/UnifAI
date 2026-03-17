from enum import Enum


class EdgeType(str, Enum):
    AFTER = "after"
    BRANCH = "branch"
    UNKNOWN = "unknown"


class CycleFixType(str, Enum):
    REMOVE_BRANCH = "remove_branch"
    REVIEW_BRANCHES = "review_branches"
    REMOVE_DEPENDENCY = "remove_dependency"
    ADD_EXIT_NODE = "add_exit_node" 