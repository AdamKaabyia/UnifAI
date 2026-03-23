from enum import Enum


class ConnectionType(str, Enum):
    DEPENDENCY = "dependency"
    BRANCH = "branch"


class OrphanFixType(str, Enum):
    REMOVE_ORPHAN = "remove_orphan"
    CONNECT_TO_WORKFLOW = "connect_to_workflow"