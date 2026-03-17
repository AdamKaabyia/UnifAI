"""
Card builder for A2AAgentNode.

Uses agent_card from config to build the element card.
"""

from typing import List, Dict, Any
from a2a.types import AgentCard
from mas.elements.common.card.models import ElementCard, Skill, Capability, CardBuildInput
from mas.elements.common.card.interface import CardBuilder


class A2AAgentCardBuilder(CardBuilder):
    """
    A2A Agent builds card from agent_card in config.

    The agent_card is fetched from remote agent at save time and contains
    the remote agent's name, description, skills, and capabilities.
    """

    @staticmethod
    def _dump_value(value: Any) -> Dict[str, Any]:
        """Dump any value to dict - works with Pydantic models or simple types."""
        try:
            return value.model_dump()
        except AttributeError:
            return {"value": value}

    def build(self, input: CardBuildInput) -> ElementCard:
        """Build card from agent_card or fallback to basic card."""
        agent_card = input.config.agent_card

        if agent_card is None:
            return self._build_basic_card(input)

        if isinstance(agent_card, dict):
            agent_card = AgentCard(**agent_card)

        return self._build_from_agent_card(input, agent_card)

    def _build_from_agent_card(
        self,
        input: CardBuildInput,
        agent_card: AgentCard
    ) -> ElementCard:
        """Build card using data from remote agent's card."""
        skills: List[Skill] = []
        if agent_card.skills:
            for agent_skill in agent_card.skills:
                skill_data = agent_skill.model_dump()
                skills.append(Skill(**skill_data))

        capabilities: List[Capability] = []
        if agent_card.capabilities:
            for field_name, field_value in agent_card.capabilities:
                if field_value is not None:
                    capabilities.append(Capability(
                        name=field_name,
                        **self._dump_value(field_value)
                    ))

        return ElementCard(
            uid=input.rid,
            category=input.spec_metadata.category,
            type_key=input.spec_metadata.type_key,
            name=agent_card.name or input.name,
            description=agent_card.description or "",
            skills=skills,
            capabilities=capabilities,
            configuration={},
            metadata=None
        )

    def _build_basic_card(self, input: CardBuildInput) -> ElementCard:
        """Build basic card when no agent_card available."""
        return ElementCard(
            uid=input.rid,
            category=input.spec_metadata.category,
            type_key=input.spec_metadata.type_key,
            name=input.name,
            description=input.spec_metadata.description,
            skills=[],
            capabilities=[],
            configuration={},
            metadata=None
        )
