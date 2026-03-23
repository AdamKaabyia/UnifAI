"""
Card builder for CustomAgentNode.

Composes skills from dependencies (tools, providers).
"""

from mas.elements.common.card.default import DefaultCardBuilder


class CustomAgentCardBuilder(DefaultCardBuilder):
    """
    CustomAgent uses default card building.

    Skills come from:
    - Tools referenced in config
    - MCP Provider tools

    Capabilities come from:
    - Retrievers referenced in config
    """
    pass
