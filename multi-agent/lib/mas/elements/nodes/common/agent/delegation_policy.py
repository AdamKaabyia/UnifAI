"""
Delegation policies for agent nodes.

Agent nodes use delegation policies to determine which adjacent nodes
can receive delegated work. Different agent types may have different
delegation rules based on their responsibilities.

This follows the Strategy Pattern, where the delegation policy is the strategy
that can be swapped at runtime to change behavior.
"""

from abc import ABC, abstractmethod
from typing import Set
from mas.graph.models import AdjacentNodes


class DelegationPolicy(ABC):
    """
    Abstract base class for agent delegation policies.
    
    Defines the interface for determining which adjacent nodes can receive
    delegated work items. Different agent types implement different policies
    based on their business requirements.
    
    SOLID Principles:
    - Single Responsibility: Only concerned with delegation eligibility
    - Open/Closed: New policies can be added without modifying existing code
    - Liskov Substitution: All subclasses can be used interchangeably
    - Interface Segregation: Minimal, focused interface
    - Dependency Inversion: Clients depend on abstraction, not concrete classes
    
    Examples:
        - OrchestratorDelegationPolicy: Excludes finalization paths
        - SecurityAwareDelegationPolicy: Filters by security clearance
        - PermissiveDelegationPolicy: Allows all adjacent nodes
    """
    
    def __init__(self, adjacent_nodes: AdjacentNodes):
        """
        Initialize delegation policy.
        
        Args:
            adjacent_nodes: All adjacent nodes from graph topology
        """
        self._adjacent_nodes = adjacent_nodes
    
    @abstractmethod
    def is_delegable(self, node_uid: str) -> bool:
        """
        Check if a specific node can receive delegated work.
        
        This is the core decision method that each policy must implement
        based on its specific business rules.
        
        Args:
            node_uid: UID of the node to check
            
        Returns:
            True if node can receive work, False otherwise
        """
        pass
    
    def filter_delegable_nodes(self, adjacent_nodes: AdjacentNodes) -> AdjacentNodes:
        """
        Filter adjacent nodes to only those that can receive delegated work.
        
        This is a template method that uses is_delegable() to filter nodes.
        Subclasses typically don't need to override this unless they need
        custom filtering logic.
        
        Args:
            adjacent_nodes: All adjacent nodes from topology
            
        Returns:
            Filtered AdjacentNodes containing only delegable nodes
        """
        delegable_dict = {
            uid: card 
            for uid, card in adjacent_nodes.items()
            if self.is_delegable(uid)
        }
        
        return AdjacentNodes.from_dict(delegable_dict)
    
    def get_delegable_node_uids(self) -> Set[str]:
        """
        Get set of all delegable node UIDs.
        
        Convenience method for checking membership or getting counts.
        
        Returns:
            Set of UIDs that are delegable
        """
        return {
            uid for uid in self._adjacent_nodes.keys()
            if self.is_delegable(uid)
        }
    
    def get_non_delegable_node_uids(self) -> Set[str]:
        """
        Get set of all non-delegable node UIDs.
        
        Useful for debugging or logging filtered nodes.
        
        Returns:
            Set of UIDs that are not delegable
        """
        return {
            uid for uid in self._adjacent_nodes.keys()
            if not self.is_delegable(uid)
        }
    
    def count_delegable_nodes(self) -> int:
        """
        Count how many nodes are delegable.
        
        Returns:
            Number of delegable nodes
        """
        return len(self.get_delegable_node_uids())


class PermissiveDelegationPolicy(DelegationPolicy):
    """
    Permissive delegation policy - allows delegation to all adjacent nodes.
    
    This is the default policy for agents that don't have special
    delegation restrictions. All adjacent nodes are considered valid
    delegation targets.
    
    Use Cases:
        - Standard agent nodes
        - Custom agent nodes
        - Any agent without specific delegation rules
    
    Example:
        >>> adjacent = AdjacentNodes.from_dict({...})
        >>> policy = PermissiveDelegationPolicy(adjacent)
        >>> policy.is_delegable("any_node")  # True if node is adjacent
    """
    
    def is_delegable(self, node_uid: str) -> bool:
        """
        All adjacent nodes are delegable.
        
        Args:
            node_uid: UID of the node to check
            
        Returns:
            True if node is in adjacent nodes, False otherwise
        """
        return node_uid in self._adjacent_nodes

