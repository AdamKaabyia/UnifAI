from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseRetriever(ABC):
    """
    Abstract base class for all Retriever integrations (Slack, Jira, PDF, etc.).
    """

    @abstractmethod
    def retrieve(self, state: Dict[str, Any]) -> Any:
        """
        Given the current state dict, fetch and return retrieval results.
        E.g. look up state[input_key] and return list of contexts.
        """
        ...
