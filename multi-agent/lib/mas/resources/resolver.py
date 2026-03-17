"""
resources/resolver.py

DependencyResolver - resolves resources with their transitive dependencies.
Returns rids in topological order (dependencies first).

This is a general-purpose utility for resolving resource dependencies.
Used by validation, card building, and other services.
"""

from typing import List, Set

from mas.resources.registry import ResourcesRegistry


class DependencyResolver:
    """
    Resolves resources with their transitive dependencies.

    Uses post-order traversal to ensure dependencies come before dependents.
    Handles circular references by tracking visited nodes.

    Returns a list of rids in dependency order (deps first, self last).

    Used by:
    - ResourcesService.validate_resource()
    - ResourcesService.get_cards()
    """

    def __init__(self, resource_registry: ResourcesRegistry):
        self._registry = resource_registry

    def resolve_with_deps(self, rid: str) -> List[str]:
        """
        Resolve a resource and all its transitive dependencies.

        Returns rids in dependency order (deps first, self last).
        Uses post-order traversal which naturally produces topological order.
        """
        visited: Set[str] = set()
        return self._resolve_recursive(rid, visited)

    def resolve_all_with_deps(self, rids: List[str]) -> List[str]:
        """
        Resolve multiple resources and all their transitive dependencies.

        Returns all rids in dependency order (deps first), with no duplicates.
        """
        visited: Set[str] = set()
        result: List[str] = []

        for rid in rids:
            for resolved_rid in self._resolve_recursive(rid, visited):
                if resolved_rid not in [r for r in result]:
                    result.append(resolved_rid)

        return result

    def _resolve_recursive(
        self,
        rid: str,
        visited: Set[str],
    ) -> List[str]:
        """Post-order traversal for dependency resolution."""
        if rid in visited:
            return []

        visited.add(rid)

        try:
            resource = self._registry.get(rid)
        except KeyError:
            return []

        result: List[str] = []

        for dep_rid in resource.nested_refs:
            result.extend(self._resolve_recursive(dep_rid, visited))

        result.append(rid)

        return result
