"""
Default card builder implementation.

Used when an element doesn't define its own card builder.
Composes skills and capabilities from dependency cards.
"""

from typing import Dict, List, Any
from mas.elements.common.card.models import ElementCard, Skill, Capability, CardBuildInput
from mas.elements.common.card.interface import CardBuilder


class DefaultCardBuilder(CardBuilder):
    """
    Default card builder - handles common cases.

    Composes skills and capabilities by aggregating from dependency cards.
    Extracts configuration from own config (like system_message).
    """

    def build(self, input: CardBuildInput) -> ElementCard:
        """Build element card by composing from dependencies."""
        skills = self._compose_skills_from_dependencies(input.dependency_cards)
        capabilities = self._compose_capabilities_from_dependencies(input.dependency_cards)

        for cap_name in input.spec_metadata.capability_names:
            capabilities.append(Capability(name=cap_name))

        configuration = self._extract_configuration(input.config)

        return ElementCard(
            uid=input.rid,
            category=input.spec_metadata.category,
            type_key=input.spec_metadata.type_key,
            name=input.name,
            description=input.spec_metadata.description,
            skills=skills,
            capabilities=capabilities,
            configuration=configuration,
            metadata=None
        )

    def _compose_skills_from_dependencies(
        self,
        dependency_cards: Dict[str, ElementCard]
    ) -> List[Skill]:
        """Aggregate skills from all dependency cards."""
        all_skills: List[Skill] = []
        for card in dependency_cards.values():
            all_skills.extend(card.skills)
        return all_skills

    def _compose_capabilities_from_dependencies(
        self,
        dependency_cards: Dict[str, ElementCard]
    ) -> List[Capability]:
        """Aggregate capabilities from all dependency cards."""
        all_capabilities: List[Capability] = []
        for card in dependency_cards.values():
            all_capabilities.extend(card.capabilities)
        return all_capabilities

    def _extract_configuration(self, config: Any) -> Dict[str, Any]:
        """Extract relevant configuration from config."""
        configuration: Dict[str, Any] = {}

        if hasattr(config, 'system_message'):
            system_message = config.system_message
            if system_message and isinstance(system_message, str) and system_message.strip():
                configuration['system_message'] = system_message

        return configuration
