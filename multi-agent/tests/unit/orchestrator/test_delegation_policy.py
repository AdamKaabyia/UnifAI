"""
Tests for orchestrator delegation policy.

Tests the SOLID implementation of delegation policies that filter
which adjacent nodes can receive delegated work.
"""

import pytest
from unittest.mock import Mock
from mas.graph.models import AdjacentNodes
from mas.elements.common.card import ElementCard
from mas.graph.topology.models import StepTopology, FinalizerPathInfo
from mas.elements.nodes.common.agent.delegation_policy import (
    DelegationPolicy,
    PermissiveDelegationPolicy
)
from mas.elements.nodes.orchestrator.delegation_policy import OrchestratorDelegationPolicy


class TestPermissiveDelegationPolicy:
    """Test the permissive delegation policy (default behavior)."""
    
    def test_all_adjacent_nodes_are_delegable(self):
        """Permissive policy allows all adjacent nodes."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard),
            "worker2": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        
        policy = PermissiveDelegationPolicy(adjacent)
        
        # Execute & Verify
        assert policy.is_delegable("worker1") is True
        assert policy.is_delegable("worker2") is True
        assert policy.is_delegable("finalize") is True  # No filtering
    
    def test_non_adjacent_nodes_not_delegable(self):
        """Non-adjacent nodes are not delegable."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard)
        })
        
        policy = PermissiveDelegationPolicy(adjacent)
        
        # Execute & Verify
        assert policy.is_delegable("worker1") is True
        assert policy.is_delegable("non_existent") is False
    
    def test_filter_returns_all_nodes(self):
        """Filter method returns all adjacent nodes unchanged."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        
        policy = PermissiveDelegationPolicy(adjacent)
        
        # Execute
        delegable = policy.filter_delegable_nodes(adjacent)
        
        # Verify - all nodes still present
        assert len(delegable) == 2
        assert "worker1" in delegable
        assert "finalize" in delegable
    
    def test_get_delegable_node_uids(self):
        """Can get set of all delegable node UIDs."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard),
            "worker2": Mock(spec=ElementCard)
        })
        
        policy = PermissiveDelegationPolicy(adjacent)
        
        # Execute
        delegable_uids = policy.get_delegable_node_uids()
        
        # Verify
        assert delegable_uids == {"worker1", "worker2"}
    
    def test_count_delegable_nodes(self):
        """Can count delegable nodes."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard),
            "worker2": Mock(spec=ElementCard),
            "worker3": Mock(spec=ElementCard)
        })
        
        policy = PermissiveDelegationPolicy(adjacent)
        
        # Execute
        count = policy.count_delegable_nodes()
        
        # Verify
        assert count == 3


class TestOrchestratorDelegationPolicy:
    """Test orchestrator-specific delegation policy."""
    
    def test_filters_direct_finalizer(self):
        """Direct finalizers (distance=1) should be filtered out."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"finalize": 1})
        )
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute & Verify
        assert policy.is_delegable("worker") is True
        assert policy.is_delegable("finalize") is False  # Filtered out!
    
    def test_filters_intermediate_finalization_nodes(self):
        """Nodes on path to finalizer should be filtered (any distance)."""
        # Setup: orchestrator → aggregator → finalize
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard),
            "worker2": Mock(spec=ElementCard),
            "aggregator": Mock(spec=ElementCard),  # Leads to finalize
        })
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={
                "aggregator": 2,  # Path to finalize exists (distance=2)
            })
        )
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute & Verify
        assert policy.is_delegable("worker1") is True  # Can delegate
        assert policy.is_delegable("worker2") is True  # Can delegate
        assert policy.is_delegable("aggregator") is False  # On finalization path!
    
    def test_filters_multiple_finalization_path_nodes(self):
        """Multiple nodes on finalization paths should all be filtered."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker": Mock(spec=ElementCard),
            "aggregator": Mock(spec=ElementCard),
            "formatter": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={
                "aggregator": 3,  # aggregator → formatter → finalize
                "formatter": 2,   # formatter → finalize
                "finalize": 1     # direct finalizer
            })
        )
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute & Verify
        assert policy.is_delegable("worker") is True
        assert policy.is_delegable("aggregator") is False  # Filtered
        assert policy.is_delegable("formatter") is False   # Filtered
        assert policy.is_delegable("finalize") is False    # Filtered
    
    def test_no_topology_allows_all_nodes(self):
        """If no topology info, all nodes are delegable (safe fallback)."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        topology = None  # No topology information
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute & Verify - safe fallback includes all nodes
        assert policy.is_delegable("worker1") is True
        assert policy.is_delegable("finalize") is True
    
    def test_no_finalizer_paths_allows_all_nodes(self):
        """If no finalizer paths in topology, all nodes are delegable."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        topology = StepTopology(finalizer_paths=None)
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute & Verify
        assert policy.is_delegable("worker1") is True
        assert policy.is_delegable("finalize") is True
    
    def test_filter_delegable_nodes(self):
        """filter_delegable_nodes returns only delegable nodes."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard, name="Worker 1"),
            "worker2": Mock(spec=ElementCard, name="Worker 2"),
            "aggregator": Mock(spec=ElementCard, name="Aggregator"),
            "finalize": Mock(spec=ElementCard, name="Finalize")
        })
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={
                "aggregator": 2,
                "finalize": 1
            })
        )
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute
        delegable = policy.filter_delegable_nodes(adjacent)
        
        # Verify
        assert len(delegable) == 2
        assert "worker1" in delegable
        assert "worker2" in delegable
        assert "aggregator" not in delegable
        assert "finalize" not in delegable
    
    def test_get_finalization_path_uids(self):
        """Can retrieve finalization path UIDs."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker": Mock(spec=ElementCard),
            "aggregator": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={
                "aggregator": 2,
                "finalize": 1
            })
        )
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute
        finalization_uids = policy.get_finalization_path_uids()
        
        # Verify
        assert finalization_uids == {"aggregator", "finalize"}
    
    def test_get_non_delegable_node_uids(self):
        """Can get set of non-delegable node UIDs."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"finalize": 1})
        )
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute
        non_delegable = policy.get_non_delegable_node_uids()
        
        # Verify
        assert non_delegable == {"finalize"}
    
    def test_count_delegable_nodes(self):
        """Can count delegable nodes."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker1": Mock(spec=ElementCard),
            "worker2": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"finalize": 1})
        )
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Execute
        count = policy.count_delegable_nodes()
        
        # Verify - 2 workers delegable, finalize filtered
        assert count == 2


class TestDelegationPolicyIntegration:
    """Integration tests for delegation policies."""
    
    def test_policy_can_be_swapped(self):
        """Different policies can be used interchangeably (LSP)."""
        # Setup
        adjacent = AdjacentNodes.from_dict({
            "worker": Mock(spec=ElementCard),
            "finalize": Mock(spec=ElementCard)
        })
        
        # Test with permissive policy
        permissive_policy = PermissiveDelegationPolicy(adjacent)
        assert permissive_policy.is_delegable("finalize") is True
        
        # Test with orchestrator policy
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"finalize": 1})
        )
        orchestrator_policy = OrchestratorDelegationPolicy(topology, adjacent)
        assert orchestrator_policy.is_delegable("finalize") is False
        
        # Both implement same interface
        policies: list[DelegationPolicy] = [permissive_policy, orchestrator_policy]
        for policy in policies:
            assert hasattr(policy, 'is_delegable')
            assert hasattr(policy, 'filter_delegable_nodes')
    
    def test_real_world_scenario(self):
        """Test realistic orchestrator scenario with mixed nodes."""
        # Setup: Realistic graph structure
        adjacent = AdjacentNodes.from_dict({
            "jira_agent": Mock(spec=ElementCard, name="Jira Agent"),
            "confluence_agent": Mock(spec=ElementCard, name="Confluence Agent"),
            "slack_agent": Mock(spec=ElementCard, name="Slack Agent"),
            "aggregator": Mock(spec=ElementCard, name="Result Aggregator"),
            "finalize": Mock(spec=ElementCard, name="Final Answer")
        })
        
        # Topology: aggregator and finalize are on completion path
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={
                "aggregator": 2,  # aggregator → finalize
                "finalize": 1     # direct finalizer
            })
        )
        
        policy = OrchestratorDelegationPolicy(topology, adjacent)
        
        # Verify: Can delegate to workers
        assert policy.is_delegable("jira_agent") is True
        assert policy.is_delegable("confluence_agent") is True
        assert policy.is_delegable("slack_agent") is True
        
        # Verify: Cannot delegate to completion path
        assert policy.is_delegable("aggregator") is False
        assert policy.is_delegable("finalize") is False
        
        # Verify: Filter produces correct set
        delegable = policy.filter_delegable_nodes(adjacent)
        assert len(delegable) == 3
        assert "jira_agent" in delegable
        assert "confluence_agent" in delegable
        assert "slack_agent" in delegable

