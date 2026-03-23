"""
Comprehensive tests for StepTopology composition design.

Tests the generic StepTopology model that composes different topology aspects
like FinalizerPathInfo, and its extensibility for future topology information.
"""

import pytest
from typing import Optional, List
from pydantic import BaseModel, Field
from mas.graph.topology.models import StepTopology, FinalizerPathInfo


# Mock future topology models for extensibility testing
class MockCycleInfo(BaseModel):
    """Mock cycle information for testing extensibility."""
    participating_nodes: List[str] = Field(default_factory=list)
    cycle_length: Optional[int] = None
    is_in_cycle: bool = False
    
    class Config:
        frozen = True


class MockCentralityInfo(BaseModel):
    """Mock centrality information for testing extensibility."""
    betweenness_centrality: Optional[float] = None
    degree_centrality: Optional[float] = None
    
    class Config:
        frozen = True


class TestStepTopologyCreation:
    """Test creation and initialization of StepTopology."""
    
    def test_create_empty(self):
        """Test creating empty StepTopology."""
        topology = StepTopology()
        
        assert topology.finalizer_paths is None
        assert not topology.has_finalizer_path()
        assert topology.get_shortest_finalizer_distance() is None
        assert topology.get_nearest_finalizer_node() is None
        assert topology.get_finalizer_reachable_nodes() == []
    
    def test_create_with_finalizer_paths(self):
        """Test creating StepTopology with FinalizerPathInfo."""
        finalizer_paths = FinalizerPathInfo(distances={"agent1": 2, "agent2": 1})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        assert topology.finalizer_paths is finalizer_paths
        assert topology.has_finalizer_path()
        assert topology.get_shortest_finalizer_distance() == 1
        assert topology.get_nearest_finalizer_node() == "agent2"
        assert set(topology.get_finalizer_reachable_nodes()) == {"agent1", "agent2"}
    
    def test_create_with_empty_finalizer_paths(self):
        """Test creating StepTopology with empty FinalizerPathInfo."""
        empty_paths = FinalizerPathInfo()  # No distances
        topology = StepTopology(finalizer_paths=empty_paths)
        
        assert topology.finalizer_paths is empty_paths
        assert not topology.has_finalizer_path()  # Empty paths = no finalizer path
        assert topology.get_shortest_finalizer_distance() is None
        assert topology.get_nearest_finalizer_node() is None
        assert topology.get_finalizer_reachable_nodes() == []


class TestStepTopologyDelegation:
    """Test that StepTopology properly delegates to composed models."""
    
    @pytest.fixture
    def sample_topology(self):
        """Sample StepTopology for testing."""
        finalizer_paths = FinalizerPathInfo(distances={
            "agent1": 3,
            "agent2": 1,
            "processor": 2,
            "validator": 4
        })
        return StepTopology(finalizer_paths=finalizer_paths)
    
    def test_has_finalizer_path_delegation(self, sample_topology):
        """Test has_finalizer_path delegates correctly."""
        assert sample_topology.has_finalizer_path()
        
        # Test with None finalizer_paths
        empty_topology = StepTopology()
        assert not empty_topology.has_finalizer_path()
        
        # Test with empty finalizer_paths
        empty_paths_topology = StepTopology(finalizer_paths=FinalizerPathInfo())
        assert not empty_paths_topology.has_finalizer_path()
    
    def test_get_shortest_finalizer_distance_delegation(self, sample_topology):
        """Test get_shortest_finalizer_distance delegates correctly."""
        assert sample_topology.get_shortest_finalizer_distance() == 1
        
        # Test with None finalizer_paths
        empty_topology = StepTopology()
        assert empty_topology.get_shortest_finalizer_distance() is None
    
    def test_get_nearest_finalizer_node_delegation(self, sample_topology):
        """Test get_nearest_finalizer_node delegates correctly."""
        assert sample_topology.get_nearest_finalizer_node() == "agent2"
        
        # Test with None finalizer_paths
        empty_topology = StepTopology()
        assert empty_topology.get_nearest_finalizer_node() is None
    
    def test_get_finalizer_reachable_nodes_delegation(self, sample_topology):
        """Test get_finalizer_reachable_nodes delegates correctly."""
        reachable = sample_topology.get_finalizer_reachable_nodes()
        expected = ["agent1", "agent2", "processor", "validator"]
        assert set(reachable) == set(expected)
        
        # Test with None finalizer_paths
        empty_topology = StepTopology()
        assert empty_topology.get_finalizer_reachable_nodes() == []
    
    def test_get_distance_to_finalizer_delegation(self, sample_topology):
        """Test get_distance_to_finalizer delegates correctly."""
        assert sample_topology.get_distance_to_finalizer("agent1") == 3
        assert sample_topology.get_distance_to_finalizer("agent2") == 1
        assert sample_topology.get_distance_to_finalizer("nonexistent") is None
        
        # Test with None finalizer_paths
        empty_topology = StepTopology()
        assert empty_topology.get_distance_to_finalizer("any") is None


class TestStepTopologyComposition:
    """Test the composition aspects of StepTopology."""
    
    def test_direct_access_to_composed_models(self):
        """Test direct access to composed models."""
        finalizer_paths = FinalizerPathInfo(distances={"agent1": 2})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # Should be able to access composed model directly
        assert topology.finalizer_paths is finalizer_paths
        assert topology.finalizer_paths.distances == {"agent1": 2}
        assert topology.finalizer_paths.get_distance("agent1") == 2
    
    def test_composition_vs_delegation(self):
        """Test that composition and delegation work together."""
        finalizer_paths = FinalizerPathInfo(distances={"agent1": 2, "agent2": 1})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # Delegation methods should match direct access
        assert topology.has_finalizer_path() == finalizer_paths.has_finalizer_paths()
        assert topology.get_shortest_finalizer_distance() == finalizer_paths.get_shortest_distance()
        assert topology.get_nearest_finalizer_node() == finalizer_paths.get_nearest_finalizer_node()
        assert topology.get_finalizer_reachable_nodes() == finalizer_paths.get_reachable_nodes()
    
    def test_none_handling_in_delegation(self):
        """Test that delegation methods handle None composed models gracefully."""
        topology = StepTopology()  # No finalizer_paths
        
        # All delegation methods should handle None gracefully
        assert not topology.has_finalizer_path()
        assert topology.get_shortest_finalizer_distance() is None
        assert topology.get_nearest_finalizer_node() is None
        assert topology.get_finalizer_reachable_nodes() == []
        assert topology.get_distance_to_finalizer("any") is None


class TestStepTopologyExtensibility:
    """Test the extensibility design of StepTopology."""
    
    def test_current_structure_ready_for_extension(self):
        """Test that current structure is ready for future extensions."""
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"agent1": 1})
        )
        
        # Current structure should have the finalizer_paths field
        assert hasattr(topology, 'finalizer_paths')
        assert topology.finalizer_paths is not None
        
        # The model should be extensible (frozen but allows new fields in subclasses)
        # Check model configuration (Pydantic v2 uses model_config)
        if hasattr(topology, 'model_config'):
            assert topology.model_config.get('frozen', False) is True
            assert topology.model_config.get('extra', None) == "forbid"  # Strict schema
        elif hasattr(topology, '__config__'):
            assert topology.__config__.frozen is True
            assert topology.__config__.extra == "forbid"  # Strict schema
    
    def test_extensibility_pattern_simulation(self):
        """Simulate how the model could be extended in the future."""
        
        # This simulates what an extended StepTopology might look like
        class ExtendedStepTopology(BaseModel):
            """Simulated extended topology with multiple aspects."""
            finalizer_paths: Optional[FinalizerPathInfo] = None
            cycle_info: Optional[MockCycleInfo] = None
            centrality: Optional[MockCentralityInfo] = None
            
            class Config:
                frozen = True
                extra = "forbid"
            
            # Convenience methods for each aspect
            def has_finalizer_path(self) -> bool:
                return self.finalizer_paths is not None and self.finalizer_paths.has_finalizer_paths()
            
            def is_in_cycle(self) -> bool:
                return self.cycle_info is not None and self.cycle_info.is_in_cycle
            
            def get_centrality_score(self) -> Optional[float]:
                if self.centrality is None:
                    return None
                return self.centrality.betweenness_centrality
        
        # Test the extended model
        finalizer_paths = FinalizerPathInfo(distances={"agent1": 1})
        cycle_info = MockCycleInfo(participating_nodes=["node1", "node2"], is_in_cycle=True)
        centrality = MockCentralityInfo(betweenness_centrality=0.75)
        
        extended = ExtendedStepTopology(
            finalizer_paths=finalizer_paths,
            cycle_info=cycle_info,
            centrality=centrality
        )
        
        # Should work with all aspects
        assert extended.has_finalizer_path()
        assert extended.is_in_cycle()
        assert extended.get_centrality_score() == 0.75
        
        # Direct access should work
        assert extended.finalizer_paths is finalizer_paths
        assert extended.cycle_info is cycle_info
        assert extended.centrality is centrality
    
    def test_partial_extension_simulation(self):
        """Test that extended model works with partial information."""
        class ExtendedStepTopology(BaseModel):
            finalizer_paths: Optional[FinalizerPathInfo] = None
            cycle_info: Optional[MockCycleInfo] = None
            
            class Config:
                frozen = True
            
            def has_finalizer_path(self) -> bool:
                return self.finalizer_paths is not None and self.finalizer_paths.has_finalizer_paths()
            
            def is_in_cycle(self) -> bool:
                return self.cycle_info is not None and self.cycle_info.is_in_cycle
        
        # Test with only finalizer paths
        extended = ExtendedStepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"agent1": 1})
        )
        
        assert extended.has_finalizer_path()
        assert not extended.is_in_cycle()  # No cycle info = not in cycle
        assert extended.cycle_info is None


class TestStepTopologyImmutability:
    """Test immutability and validation of StepTopology."""
    
    def test_frozen_model(self):
        """Test that StepTopology is immutable."""
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"agent1": 1})
        )
        
        # Should not be able to modify the model
        with pytest.raises(Exception):  # ValidationError or similar
            topology.finalizer_paths = FinalizerPathInfo(distances={"agent2": 2})
    
    def test_composed_model_field_immutability(self):
        """Test that composed model fields cannot be reassigned."""
        finalizer_paths = FinalizerPathInfo(distances={"agent1": 1})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # The composed model field should not be reassignable
        with pytest.raises((TypeError, AttributeError, ValueError)):
            topology.finalizer_paths = FinalizerPathInfo(distances={"agent2": 2})
        
        # Original composed model should remain
        assert topology.finalizer_paths is finalizer_paths
        assert topology.finalizer_paths.distances == {"agent1": 1}
    
    def test_strict_schema_validation(self):
        """Test that the model has strict schema validation."""
        # The model should forbid extra fields
        with pytest.raises(Exception):  # ValidationError
            StepTopology(
                finalizer_paths=FinalizerPathInfo(distances={"agent1": 1}),
                invalid_field="should_not_be_allowed"
            )


class TestStepTopologyComparison:
    """Test comparison and equality of StepTopology instances."""
    
    def test_equality_with_same_finalizer_paths(self):
        """Test equality of StepTopology instances with same finalizer paths."""
        finalizer_paths = FinalizerPathInfo(distances={"agent1": 1})
        
        topology1 = StepTopology(finalizer_paths=finalizer_paths)
        topology2 = StepTopology(finalizer_paths=finalizer_paths)
        
        assert topology1 == topology2
    
    def test_equality_with_equivalent_finalizer_paths(self):
        """Test equality with equivalent but different FinalizerPathInfo instances."""
        distances = {"agent1": 1, "agent2": 2}
        
        topology1 = StepTopology(finalizer_paths=FinalizerPathInfo(distances=distances))
        topology2 = StepTopology(finalizer_paths=FinalizerPathInfo(distances=distances))
        
        assert topology1 == topology2
    
    def test_inequality_with_different_finalizer_paths(self):
        """Test inequality with different finalizer paths."""
        topology1 = StepTopology(finalizer_paths=FinalizerPathInfo(distances={"agent1": 1}))
        topology2 = StepTopology(finalizer_paths=FinalizerPathInfo(distances={"agent1": 2}))
        
        assert topology1 != topology2
    
    def test_inequality_none_vs_empty(self):
        """Test inequality between None and empty finalizer paths."""
        topology1 = StepTopology()  # None finalizer_paths
        topology2 = StepTopology(finalizer_paths=FinalizerPathInfo())  # Empty finalizer_paths
        
        assert topology1 != topology2
    
    def test_empty_topology_equality(self):
        """Test equality of empty StepTopology instances."""
        topology1 = StepTopology()
        topology2 = StepTopology()
        
        assert topology1 == topology2


class TestStepTopologySerialization:
    """Test serialization and deserialization of StepTopology."""
    
    def test_dict_conversion_with_finalizer_paths(self):
        """Test conversion to and from dict with finalizer paths."""
        finalizer_paths = FinalizerPathInfo(distances={"agent1": 1, "agent2": 2})
        topology = StepTopology(finalizer_paths=finalizer_paths)
        
        # Convert to dict
        data = topology.dict()
        assert "finalizer_paths" in data
        assert data["finalizer_paths"]["distances"] == {"agent1": 1, "agent2": 2}
        
        # Create from dict
        recreated = StepTopology(**data)
        assert recreated == topology
    
    def test_dict_conversion_empty(self):
        """Test conversion to and from dict with empty topology."""
        topology = StepTopology()
        
        # Convert to dict
        data = topology.dict()
        assert data["finalizer_paths"] is None
        
        # Create from dict
        recreated = StepTopology(**data)
        assert recreated == topology
    
    def test_json_serialization(self):
        """Test JSON serialization."""
        topology = StepTopology(
            finalizer_paths=FinalizerPathInfo(distances={"agent1": 1})
        )
        
        # Should be JSON serializable
        json_str = topology.json()
        assert isinstance(json_str, str)
        assert "finalizer_paths" in json_str
        assert "agent1" in json_str
        
        # Should be able to parse back
        recreated = StepTopology.parse_raw(json_str)
        assert recreated == topology
    
    def test_json_serialization_with_none(self):
        """Test JSON serialization with None values."""
        topology = StepTopology()
        
        json_str = topology.json()
        assert "null" in json_str or "None" in json_str  # None should be serialized
        
        recreated = StepTopology.parse_raw(json_str)
        assert recreated == topology


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
