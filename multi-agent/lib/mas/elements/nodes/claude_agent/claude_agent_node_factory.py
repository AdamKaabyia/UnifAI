"""
Claude Agent Node Factory
"""

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import ClaudeAgentNodeConfig
from .claude_agent_node import ClaudeAgentNode
from .identifiers import Identifier


class ClaudeAgentNodeFactory(BaseFactory[ClaudeAgentNodeConfig, ClaudeAgentNode]):
    """
    Factory for creating Claude Agent Node instances.

    Dependencies injected:
    - retriever: Optional retriever instance (resolved from RetrieverRef)
    """

    def accepts(self, cfg: ClaudeAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: ClaudeAgentNodeConfig, **deps):
        try:
            return ClaudeAgentNode(
                # Auth (Vertex AI)
                vertex_project_id=cfg.vertex_project_id,
                vertex_region=cfg.vertex_region,
                # Model
                model=cfg.model,
                # Agent behavior
                system_prompt=cfg.system_prompt,
                max_turns=cfg.max_turns,
                permission_mode=cfg.permission_mode,
                allowed_tools=cfg.allowed_tools,
                disallowed_tools=cfg.disallowed_tools,
                # Skills
                skills_repos=cfg.skills_repos,
                cwd=cfg.cwd,
                # Advanced
                env_vars=cfg.env_vars,
                # Standard
                retriever=deps.pop("retriever"),
                retries=cfg.retries,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"ClaudeAgentNodeFactory.create failed: {e}",
                cfg.dict(),
            ) from e
