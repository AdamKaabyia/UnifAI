"""
session/collector.py

SessionConfigCollector - collects configs from SessionRegistry.

This is a general-purpose utility for extracting element metadata
from a SessionRegistry. Used by RTGraphPlan for card building.
"""

from typing import List

from mas.core.enums import ResourceCategory
from mas.core.ref import RefWalker
from mas.core.element_meta import ElementConfigMeta
from mas.session.domain.session_registry import SessionRegistry


class SessionConfigCollector:
    """
    Collects element configs from a SessionRegistry.

    SessionRegistry contains runtime elements that were resolved
    from a blueprint. This collector extracts their metadata
    for card building.

    Responsible for:
    - Iterating through all categories in the session
    - Extracting config metadata for each runtime element
    - Identifying dependency rids for each config (using RefWalker)

    Used by:
    - RTGraphPlan._build_all_cards()
    """

    def collect(self, session: SessionRegistry) -> List[ElementConfigMeta]:
        """
        Collect all configs from a session registry.

        Args:
            session: SessionRegistry containing runtime elements

        Returns:
            List of ElementConfigMeta for all elements in the session
        """
        result: List[ElementConfigMeta] = []

        for category in ResourceCategory:
            for rid, runtime_element in session._store[category].items():
                resource_spec = runtime_element.resource_spec
                if resource_spec and resource_spec.config:
                    dep_rids = list(RefWalker.all_rids(resource_spec.config))

                    result.append(ElementConfigMeta(
                        rid=rid,
                        category=category,
                        type_key=resource_spec.type,
                        name=resource_spec.name,
                        config=resource_spec.config,
                        dependency_rids=dep_rids,
                    ))

        return result
