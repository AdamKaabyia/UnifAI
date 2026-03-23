"""
Tests for the new composition-based topology system.

Ensures that the new StepTopology with FinalizerPathInfo composition
works correctly and provides clean, extensible architecture.
"""

import pytest
from unittest.mock import Mock
from mas.graph.topology.models import StepTopology, FinalizerPathInfo
from mas.graph.models.step_context import StepContext
from mas.graph.topology.finalizer_analyzer import FinalizerAnalyzer
from mas.graph.models import Step
from mas.graph.graph_plan import GraphPlan
from mas.core.enums import ResourceCategory


class TestNewCompositionDesign:
    """Test the new composition-based topology design."""
    
    def test_step_topology_composition_structure(self):
        """Test that StepTopology properly composes FinalizerPathInfo."""
        finalizer_paths = FinalizerPathInfo(distances={"node1": 1, "node2": 2})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # Should compose the FinalizerPathInfo
        assert topology.finalizer_paths is finalizer_paths
        assert topology.finalizer_paths.distances == {"node1": 1, "node2": 2}
        
        # Should be able to access composed model directly
        assert topology.finalizer_paths.get_distance("node1") == 1
        assert topology.finalizer_paths.has_finalizer_paths() == True
    
    def test_step_topology_delegation_methods(self):
        """Test that StepTopology delegates correctly to FinalizerPathInfo."""
        finalizer_paths = FinalizerPathInfo(distances={"node1": 1, "node2": 2})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # Delegation should work correctly
        assert topology.has_finalizer_path() == finalizer_paths.has_finalizer_paths()
        assert topology.get_nearest_finalizer_node() == finalizer_paths.get_nearest_finalizer_node()
        assert topology.get_shortest_finalizer_distance() == finalizer_paths.get_shortest_distance()
        assert topology.get_finalizer_reachable_nodes() == finalizer_paths.get_reachable_nodes()
        assert topology.get_distance_to_finalizer("node1") == finalizer_paths.get_distance("node1")
    
    def test_step_topology_without_finalizer_paths(self):
        """Test StepTopology behavior when no finalizer paths exist."""
        topology = StepTopology()  # No finalizer_paths
        
        # Should handle None gracefully
        assert topology.finalizer_paths is None
        assert topology.has_finalizer_path() == False
        assert topology.get_nearest_finalizer_node() is None
        assert topology.get_shortest_finalizer_distance() is None
        assert topology.get_finalizer_reachable_nodes() == []
        assert topology.get_distance_to_finalizer("any") is None
    
    def test_step_topology_extensibility_ready(self):
        """Test that StepTopology is ready for future extensions."""
        topology = StepTopology(finalizer_paths=FinalizerPathInfo(distances={"node1": 1}))
        
        # Should have the composition structure ready for extension
        assert hasattr(topology, 'finalizer_paths')
        assert topology.finalizer_paths is not None
        
        # The model structure allows for future composition fields
        # like cycle_info, centrality, etc.
        # Check if model is properly configured (Pydantic v2 uses model_config)
        if hasattr(topology, 'model_config'):
            assert topology.model_config.get('frozen', False) == True  # Immutable
            assert topology.model_config.get('extra', None) == "forbid"  # Strict schema
        elif hasattr(topology, '__config__'):
            assert topology.__config__.frozen == True  # Immutable (Pydantic v1)
            assert topology.__config__.extra == "forbid"  # Strict schema


class TestStepTopologyInStepContext:
    """Test StepTopology integration with StepContext."""
    
    def test_step_context_with_new_topology(self):
        """Test that StepContext works with new topology composition."""
        finalizer_paths = FinalizerPathInfo(distances={"agent1": 2, "agent2": 1})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        context = StepContext(uid="test_node", topology=topology)
        
        # Should integrate properly
        assert context.topology is topology
        assert context.topology.has_finalizer_path()
        assert context.topology.get_nearest_finalizer_node() == "agent2"
        
        # Should be able to access composed model through context
        assert context.topology.finalizer_paths.distances == {"agent1": 2, "agent2": 1}
    
    def test_step_context_with_empty_topology(self):
        """Test StepContext with empty topology."""
        context = StepContext(uid="test_node")  # Uses default empty topology
        
        assert isinstance(context.topology, StepTopology)
        assert context.topology.finalizer_paths is None
        assert not context.topology.has_finalizer_path()
    
    def test_step_context_immutability_with_topology(self):
        """Test that StepContext with topology remains immutable."""
        topology = StepTopology(finalizer_paths=FinalizerPathInfo(distances={"node1": 1}))
        context = StepContext(uid="test_node", topology=topology)
        
        # Should not be able to modify
        with pytest.raises(Exception):  # dataclass frozen
            context.topology = StepTopology()


class TestFinalizerAnalyzerWithNewModels:
    """Test FinalizerAnalyzer creates correct new model structure."""
    
    def test_analyzer_creates_step_topology_with_finalizer_paths(self):
        """Test that FinalizerAnalyzer creates proper StepTopology structure."""
        analyzer = FinalizerAnalyzer()
        
        # Create test graph
        source = Step(uid="source", category=ResourceCategory.NODE, rid="source_rid", type_key="source", writes={"data"})
        finalizer = Step(uid="finalizer", category=ResourceCategory.NODE, rid="finalizer_rid", type_key="finalizer", reads={"data"}, writes={"output"}, after=["source"])
        
        plan = GraphPlan()
        plan.add_step(source)
        plan.add_step(finalizer)
        
        result = analyzer.analyze_node_topology(plan, "source", ["finalizer"])
        
        # Should create proper structure
        assert isinstance(result, StepTopology)
        assert result.finalizer_paths is not None
        assert isinstance(result.finalizer_paths, FinalizerPathInfo)
        assert result.has_finalizer_path()
        assert "finalizer" in result.finalizer_paths.distances
        assert result.get_distance_to_finalizer("finalizer") == 1
    
    def test_analyzer_creates_empty_topology_when_no_finalizers(self):
        """Test analyzer creates empty topology when no finalizers exist."""
        analyzer = FinalizerAnalyzer()
        
        # Create graph with no finalizers
        node1 = Step(uid="node1", category=ResourceCategory.NODE, rid="node1_rid", type_key="node1", writes={"data"})
        node2 = Step(uid="node2", category=ResourceCategory.NODE, rid="node2_rid", type_key="node2", reads={"data"}, writes={"processed"}, after=["node1"])
        
        plan = GraphPlan()
        plan.add_step(node1)
        plan.add_step(node2)
        
        result = analyzer.analyze_node_topology(plan, "node1", ["node2"])
        
        # Should create topology with no finalizer paths
        assert isinstance(result, StepTopology)
        assert result.finalizer_paths is None
        assert not result.has_finalizer_path()


class TestNodeUsagePatterns:
    """Test common patterns for how nodes would use the new topology."""
    
    def test_node_decision_making_with_composition(self):
        """Test typical node decision-making patterns with new composition."""
        # Create topology with multiple paths
        finalizer_paths = FinalizerPathInfo(distances={
            "fast_path": 1,
            "slow_path": 3,
            "medium_path": 2
        })
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # Pattern 1: Check if any finalizer path exists
        if topology.has_finalizer_path():
            # Pattern 2: Get best path
            best_node = topology.get_nearest_finalizer_node()
            assert best_node == "fast_path"
            
            # Pattern 3: Get distance for decision making
            distance = topology.get_distance_to_finalizer(best_node)
            assert distance == 1
            
            # Pattern 4: Access composed model directly for detailed analysis
            all_distances = topology.finalizer_paths.distances
            assert all_distances == {"fast_path": 1, "slow_path": 3, "medium_path": 2}
    
    def test_conditional_routing_logic(self):
        """Test conditional routing logic with new topology."""
        def make_routing_decision(topology: StepTopology) -> str:
            if not topology.has_finalizer_path():
                return "no_path_available"
            
            shortest = topology.get_shortest_finalizer_distance()
            if shortest == 1:
                return "direct_to_finalizer"
            elif shortest <= 3:
                return "short_path_to_finalizer"
            else:
                return "long_path_to_finalizer"
        
        # Test different scenarios
        no_path = StepTopology()
        assert make_routing_decision(no_path) == "no_path_available"
        
        direct_path = StepTopology(finalizer_paths=FinalizerPathInfo(distances={"direct": 1}))
        assert make_routing_decision(direct_path) == "direct_to_finalizer"
        
        short_path = StepTopology(finalizer_paths=FinalizerPathInfo(distances={"short": 3}))
        assert make_routing_decision(short_path) == "short_path_to_finalizer"
        
        long_path = StepTopology(finalizer_paths=FinalizerPathInfo(distances={"long": 5}))
        assert make_routing_decision(long_path) == "long_path_to_finalizer"
    
    def test_detailed_path_analysis(self):
        """Test detailed path analysis using composed models."""
        finalizer_paths = FinalizerPathInfo(distances={
            "agent1": 2,
            "agent2": 1,
            "processor": 4
        })
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # Analyze each path individually
        path_analysis = {}
        if topology.finalizer_paths:
            for node_uid, distance in topology.finalizer_paths.distances.items():
                path_analysis[node_uid] = {
                    "distance": distance,
                    "is_shortest": distance == topology.get_shortest_finalizer_distance(),
                    "efficiency_score": 1.0 / distance  # Higher score = more efficient
                }
        
        expected = {
            "agent1": {"distance": 2, "is_shortest": False, "efficiency_score": 0.5},
            "agent2": {"distance": 1, "is_shortest": True, "efficiency_score": 1.0},
            "processor": {"distance": 4, "is_shortest": False, "efficiency_score": 0.25}
        }
        
        assert path_analysis == expected


class TestSerializationWithNewDesign:
    """Test serialization works correctly with new composition design."""
    
    def test_step_topology_serialization(self):
        """Test StepTopology serializes correctly with composed models."""
        finalizer_paths = FinalizerPathInfo(distances={"node1": 1, "node2": 2})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # Should serialize to dict
        data = topology.dict()
        assert "finalizer_paths" in data
        assert data["finalizer_paths"]["distances"] == {"node1": 1, "node2": 2}
        
        # Should deserialize correctly
        recreated = StepTopology(**data)
        assert recreated == topology
        assert recreated.has_finalizer_path()
        assert recreated.get_distance_to_finalizer("node1") == 1
    
    def test_json_serialization_with_composition(self):
        """Test JSON serialization with composition structure."""
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"node1": 1})
        )
        
        # Should serialize to JSON
        json_str = topology.json()
        assert "finalizer_paths" in json_str
        assert "node1" in json_str
        
        # Should deserialize correctly
        recreated = StepTopology.parse_raw(json_str)
        assert recreated == topology
        assert recreated.has_finalizer_path()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
