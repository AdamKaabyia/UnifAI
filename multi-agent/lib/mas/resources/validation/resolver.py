"""
Backwards-compatibility re-export.
The resolver has moved to mas.resources.resolver.
"""

from mas.resources.resolver import DependencyResolver

__all__ = ["DependencyResolver"]
