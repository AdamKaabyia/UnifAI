from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import DocsRagRetrieverConfig
from .docs_rag_retriever import DocsRagRetriever
from .identifiers import Identifier


class DocsRagRetrieverFactory(BaseFactory[DocsRagRetrieverConfig, DocsRagRetriever]):
    """
    Factory for creating DocsRagRetriever instances from configuration.
    """

    def accepts(self, cfg: DocsRagRetrieverConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: DocsRagRetrieverConfig, **kwargs: Any) -> DocsRagRetriever:
        try:
            return DocsRagRetriever(
                top_k_results=cfg.top_k_results,
                threshold=cfg.threshold,
                timeout=cfg.timeout,
                docs=cfg.docs,
                tags=cfg.tags,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"DocsRagRetrieverFactory.create() failed: {e}",
                cfg.model_dump()
            ) from e

