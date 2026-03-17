"""
Comprehensive tests for FinalizerPathInfo model.

Tests the focused model that handles finalizer path distance information.
"""

import pytest
from mas.graph.topology.models import FinalizerPathInfo


class TestFinalizerPathInfoCreation:
    """Test creation and initialization of FinalizerPathInfo."""
    
    def test_create_empty(self):
        """Test creating empty FinalizerPathInfo."""
        path_info = FinalizerPathInfo()
        
        assert path_info.distances == {}
        assert not path_info.has_finalizer_paths()
        assert path_info.get_shortest_distance() is None
        assert path_info.get_nearest_finalizer_node() is None
        assert path_info.get_reachable_nodes() == []
    
    def test_create_with_distances(self):
        """Test creating FinalizerPathInfo with distance data."""
        distances = {
            "agent1": 2,
            "agent2": 1,
            "agent3": 4,
            "processor": 3
        }
        
        path_info = FinalizerPathInfo(distances=distances)
        
        assert path_info.distances == distances
        assert path_info.has_finalizer_paths()
        assert len(path_info.get_reachable_nodes()) == 4
    
    def test_create_with_single_distance(self):
        """Test creating FinalizerPathInfo with single distance."""
        path_info = FinalizerPathInfo(distances={"finalizer": 1})
        
        assert path_info.distances == {"finalizer": 1}
        assert path_info.has_finalizer_paths()
        assert path_info.get_shortest_distance() == 1
        assert path_info.get_nearest_finalizer_node() == "finalizer"


class TestFinalizerPathInfoQueries:
    """Test query methods of FinalizerPathInfo."""
    
    @pytest.fixture
    def sample_path_info(self):
        """Sample FinalizerPathInfo for testing."""
        return FinalizerPathInfo(distances={
            "agent1": 3,
            "agent2": 1,  # Shortest
            "agent3": 2,
            "processor": 4,  # Longest
            "validator": 1   # Also shortest (tie)
        })
    
    def test_has_finalizer_paths(self, sample_path_info):
        """Test has_finalizer_paths method."""
        assert sample_path_info.has_finalizer_paths()
        
        empty_info = FinalizerPathInfo()
        assert not empty_info.has_finalizer_paths()
    
    def test_get_shortest_distance(self, sample_path_info):
        """Test get_shortest_distance method."""
        assert sample_path_info.get_shortest_distance() == 1
        
        # Test with different distances
        path_info = FinalizerPathInfo(distances={"node1": 5, "node2": 3})
        assert path_info.get_shortest_distance() == 3
    
    def test_get_nearest_finalizer_node(self, sample_path_info):
        """Test get_nearest_finalizer_node method."""
        nearest = sample_path_info.get_nearest_finalizer_node()
        
        # Should return one of the nodes with distance 1
        assert nearest in ["agent2", "validator"]
        assert sample_path_info.get_distance(nearest) == 1
    
    def test_get_nearest_finalizer_node_deterministic(self):
        """Test that get_nearest_finalizer_node is deterministic with unique shortest."""
        path_info = FinalizerPathInfo(distances={
            "agent1": 3,
            "agent2": 1,  # Unique shortest
            "agent3": 2
        })
        
        assert path_info.get_nearest_finalizer_node() == "agent2"
    
    def test_get_reachable_nodes(self, sample_path_info):
        """Test get_reachable_nodes method."""
        reachable = sample_path_info.get_reachable_nodes()
        
        expected = ["agent1", "agent2", "agent3", "processor", "validator"]
        assert set(reachable) == set(expected)
        assert len(reachable) == 5
    
    def test_get_distance(self, sample_path_info):
        """Test get_distance method."""
        assert sample_path_info.get_distance("agent1") == 3
        assert sample_path_info.get_distance("agent2") == 1
        assert sample_path_info.get_distance("processor") == 4
        assert sample_path_info.get_distance("nonexistent") is None
    
    def test_get_distance_edge_cases(self):
        """Test get_distance with edge cases."""
        path_info = FinalizerPathInfo(distances={"node": 0})  # Edge case: distance 0
        assert path_info.get_distance("node") == 0
        
        empty_info = FinalizerPathInfo()
        assert empty_info.get_distance("any") is None


class TestFinalizerPathInfoEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_distances_queries(self):
        """Test all query methods with empty distances."""
        empty_info = FinalizerPathInfo()
        
        assert not empty_info.has_finalizer_paths()
        assert empty_info.get_shortest_distance() is None
        assert empty_info.get_nearest_finalizer_node() is None
        assert empty_info.get_reachable_nodes() == []
        assert empty_info.get_distance("any") is None
    
    def test_single_node_distances(self):
        """Test with single node distance."""
        single_info = FinalizerPathInfo(distances={"only_node": 5})
        
        assert single_info.has_finalizer_paths()
        assert single_info.get_shortest_distance() == 5
        assert single_info.get_nearest_finalizer_node() == "only_node"
        assert single_info.get_reachable_nodes() == ["only_node"]
        assert single_info.get_distance("only_node") == 5
    
    def test_zero_distance(self):
        """Test with zero distance (node is itself a finalizer)."""
        zero_info = FinalizerPathInfo(distances={"self": 0})
        
        assert zero_info.has_finalizer_paths()
        assert zero_info.get_shortest_distance() == 0
        assert zero_info.get_nearest_finalizer_node() == "self"
    
    def test_large_distances(self):
        """Test with large distance values."""
        large_info = FinalizerPathInfo(distances={
            "far_node": 1000,
            "very_far": 9999,
            "closer": 100
        })
        
        assert large_info.get_shortest_distance() == 100
        assert large_info.get_nearest_finalizer_node() == "closer"
    
    def test_identical_distances(self):
        """Test with multiple nodes having identical distances."""
        identical_info = FinalizerPathInfo(distances={
            "node1": 2,
            "node2": 2,
            "node3": 2
        })
        
        assert identical_info.get_shortest_distance() == 2
        # Should return one of them (deterministic based on dict ordering)
        nearest = identical_info.get_nearest_finalizer_node()
        assert nearest in ["node1", "node2", "node3"]
        assert identical_info.get_distance(nearest) == 2


class TestFinalizerPathInfoImmutability:
    """Test immutability and validation of FinalizerPathInfo."""
    
    def test_frozen_model(self):
        """Test that FinalizerPathInfo is immutable."""
        path_info = FinalizerPathInfo(distances={"node1": 1})
        
        # Should not be able to modify the model
        with pytest.raises(Exception):  # ValidationError or similar
            path_info.distances = {"node2": 2}
    
    def test_model_field_immutability(self):
        """Test that the model fields cannot be reassigned."""
        path_info = FinalizerPathInfo(distances={"node1": 1})
        
        # The model should be frozen, preventing field reassignment
        with pytest.raises((TypeError, AttributeError, ValueError)):
            path_info.distances = {"node2": 2}
        
        # Original distances should remain
        assert path_info.distances == {"node1": 1}
    
    def test_validation_positive_distances(self):
        """Test that negative distances are handled appropriately."""
        # The model should accept any integer (including negative for edge cases)
        # but in practice, distances should be non-negative
        path_info = FinalizerPathInfo(distances={"node": -1})
        assert path_info.get_distance("node") == -1
    
    def test_validation_string_keys(self):
        """Test that only string keys are accepted."""
        # Should work with string keys
        path_info = FinalizerPathInfo(distances={"valid_key": 1})
        assert path_info.get_distance("valid_key") == 1


class TestFinalizerPathInfoComparison:
    """Test comparison and equality of FinalizerPathInfo instances."""
    
    def test_equality(self):
        """Test equality of FinalizerPathInfo instances."""
        distances = {"agent1": 2, "agent2": 1}
        
        info1 = FinalizerPathInfo(distances=distances)
        info2 = FinalizerPathInfo(distances=distances)
        
        assert info1 == info2
    
    def test_inequality(self):
        """Test inequality of FinalizerPathInfo instances."""
        info1 = FinalizerPathInfo(distances={"agent1": 2})
        info2 = FinalizerPathInfo(distances={"agent1": 3})
        info3 = FinalizerPathInfo(distances={"agent2": 2})
        
        assert info1 != info2  # Different distances
        assert info1 != info3  # Different nodes
    
    def test_empty_equality(self):
        """Test equality of empty FinalizerPathInfo instances."""
        empty1 = FinalizerPathInfo()
        empty2 = FinalizerPathInfo()
        
        assert empty1 == empty2


class TestFinalizerPathInfoSerialization:
    """Test serialization and deserialization of FinalizerPathInfo."""
    
    def test_dict_conversion(self):
        """Test conversion to and from dict."""
        distances = {"agent1": 2, "agent2": 1, "processor": 3}
        path_info = FinalizerPathInfo(distances=distances)
        
        # Convert to dict
        data = path_info.dict()
        assert data["distances"] == distances
        
        # Create from dict
        recreated = FinalizerPathInfo(**data)
        assert recreated == path_info
    
    def test_json_serialization(self):
        """Test JSON serialization."""
        path_info = FinalizerPathInfo(distances={"agent1": 2, "agent2": 1})
        
        # Should be JSON serializable
        json_str = path_info.json()
        assert isinstance(json_str, str)
        assert "agent1" in json_str
        assert "agent2" in json_str
        
        # Should be able to parse back
        recreated = FinalizerPathInfo.parse_raw(json_str)
        assert recreated == path_info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
