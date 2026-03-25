from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import UserQuestionNodeConfig
from .user_question import UserQuestionNode
from .identifiers import Identifier


class UserQuestionNodeFactory(BaseFactory[UserQuestionNodeConfig, UserQuestionNode]):
    """Factory for UserQuestionNode (needs no LLM/retriever/tools)."""

    def accepts(self, cfg: UserQuestionNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: UserQuestionNodeConfig, **deps) -> UserQuestionNode:
        try:
            return UserQuestionNode()
        except Exception as exc:
            raise PluginConfigurationError(
                f"UserQuestionNodeFactory.create failed: {exc}",
                cfg.dict()
            ) from exc
