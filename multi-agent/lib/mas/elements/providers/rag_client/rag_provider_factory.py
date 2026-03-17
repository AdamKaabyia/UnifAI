"""
RAG Provider Factory
"""
from typing import Any

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import RagProviderConfig
from .rag_provider import RagProvider
from .identifiers import Identifier


class RagProviderFactory(BaseFactory[RagProviderConfig, RagProvider]):
    """
    Factory for creating RAG Provider instances from configuration.
    """

    def accepts(self, cfg: RagProviderConfig, element_type: str) -> bool:
        """Check if this factory accepts the given config type."""
        return element_type == Identifier.TYPE

    def create(self, cfg: RagProviderConfig, **kwargs: Any) -> RagProvider:
        """
        Create RAG Provider instance.

        Args:
            cfg: Validated RagProviderConfig
            **kwargs: Additional arguments

        Returns:
            Initialized RagProvider

        Raises:
            PluginConfigurationError: If creation fails
        """
        try:
            return RagProvider(
                base_url=cfg.base_url,
                top_k=cfg.top_k,
                timeout=cfg.timeout,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"RagProvider creation failed: {e}",
                cfg.model_dump()
            ) from e

