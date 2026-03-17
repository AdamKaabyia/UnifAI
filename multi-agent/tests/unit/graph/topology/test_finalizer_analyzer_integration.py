"""
Comprehensive tests for FinalizerAnalyzer with the new composition-based models.

Tests that FinalizerAnalyzer correctly creates StepTopology with FinalizerPathInfo
and handles various graph scenarios including cycles, multiple paths, and edge cases.
"""

import pytest
from unittest.mock import Mock
from mas.graph.topology.finalizer_analyzer import FinalizerAnalyzer
from mas.graph.topology.models import StepTopology, FinalizerPathInfo
from mas.graph.models import Step
from mas.graph.graph_plan import GraphPlan
from mas.core.enums import ResourceCategory
from mas.blueprints.models.blueprint import StepMeta


class TestFinalizerAnalyzerBasicFunctionality:
    """Test basic functionality of FinalizerAnalyzer with new models."""
    
    def test_analyzer_initialization(self):
        """Test FinalizerAnalyzer initialization."""
        # Default initialization
        analyzer = FinalizerAnalyzer()
        assert analyzer._output_channel == "output"
        
        # Custom output channel
        custom_analyzer = FinalizerAnalyzer(output_channel="custom_output")
        assert custom_analyzer._output_channel == "custom_output"
    
    def test_analyze_node_topology_returns_step_topology(self):
        """Test that analyze_node_topology returns StepTopology."""
        analyzer = FinalizerAnalyzer()
        
        # Create minimal graph
        step = Step(
            uid="test_step",
            category=ResourceCategory.NODE,
            rid="test_rid",
            type_key="test",
            writes={"output"}  # Finalizer
        )
        
        plan = GraphPlan()
        plan.add_step(step)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="test_step",
            adjacent_node_uids=[]
        )
        
        assert isinstance(result, StepTopology)
        assert result.finalizer_paths is None  # No adjacent nodes
    
    def test_analyze_with_finalizer_adjacent_node(self):
        """Test analysis with adjacent node that is a finalizer."""
        analyzer = FinalizerAnalyzer()
        
        # Create graph: source -> finalizer
        source = Step(
            uid="source",
            category=ResourceCategory.NODE,
            rid="source_rid",
            type_key="source",
            writes={"intermediate"}
        )
        
        finalizer = Step(
            uid="finalizer",
            category=ResourceCategory.NODE,
            rid="finalizer_rid",
            type_key="finalizer",
            reads={"intermediate"},
            writes={"output"},  # This makes it a finalizer
            after=["source"]
        )
        
        plan = GraphPlan()
        plan.add_step(source)
        plan.add_step(finalizer)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="source",
            adjacent_node_uids=["finalizer"]
        )
        
        assert isinstance(result, StepTopology)
        assert result.finalizer_paths is not None
        assert isinstance(result.finalizer_paths, FinalizerPathInfo)
        assert result.has_finalizer_path()
        assert result.get_distance_to_finalizer("finalizer") == 1  # Direct finalizer


class TestFinalizerAnalyzerPathCalculation:
    """Test path distance calculation with various graph structures."""
    
    def test_simple_chain_to_finalizer(self):
        """Test simple chain: source -> intermediate -> finalizer."""
        analyzer = FinalizerAnalyzer()
        
        source = Step(
            uid="source",
            category=ResourceCategory.NODE,
            rid="source_rid",
            type_key="source",
            writes={"data1"}
        )
        
        intermediate = Step(
            uid="intermediate",
            category=ResourceCategory.NODE,
            rid="intermediate_rid",
            type_key="intermediate",
            reads={"data1"},
            writes={"data2"},
            after=["source"]
        )
        
        finalizer = Step(
            uid="finalizer",
            category=ResourceCategory.NODE,
            rid="finalizer_rid",
            type_key="finalizer",
            reads={"data2"},
            writes={"output"},
            after=["intermediate"]
        )
        
        plan = GraphPlan()
        plan.add_step(source)
        plan.add_step(intermediate)
        plan.add_step(finalizer)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="source",
            adjacent_node_uids=["intermediate"]
        )
        
        assert result.has_finalizer_path()
        # Distance should be 2: intermediate -> finalizer (1) + source -> intermediate (1)
        assert result.get_distance_to_finalizer("intermediate") == 2
    
    def test_multiple_paths_different_distances(self):
        """Test multiple adjacent nodes with different distances to finalizer."""
        analyzer = FinalizerAnalyzer()
        
        # Create graph:
        # source -> [short_path, long_path]
        # short_path -> finalizer (distance 2)
        # long_path -> intermediate -> finalizer (distance 3)
        
        source = Step(uid="source", category=ResourceCategory.NODE, rid="source_rid", type_key="source", writes={"data"})
        
        short_path = Step(
            uid="short_path",
            category=ResourceCategory.NODE,
            rid="short_rid",
            type_key="short",
            reads={"data"},
            writes={"short_data"},
            after=["source"]
        )
        
        long_path = Step(
            uid="long_path",
            category=ResourceCategory.NODE,
            rid="long_rid",
            type_key="long",
            reads={"data"},
            writes={"long_data"},
            after=["source"]
        )
        
        intermediate = Step(
            uid="intermediate",
            category=ResourceCategory.NODE,
            rid="intermediate_rid",
            type_key="intermediate",
            reads={"long_data"},
            writes={"processed_data"},
            after=["long_path"]
        )
        
        finalizer = Step(
            uid="finalizer",
            category=ResourceCategory.NODE,
            rid="finalizer_rid",
            type_key="finalizer",
            reads={"short_data", "processed_data"},
            writes={"output"},
            after=["short_path", "intermediate"]
        )
        
        plan = GraphPlan()
        for step in [source, short_path, long_path, intermediate, finalizer]:
            plan.add_step(step)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="source",
            adjacent_node_uids=["short_path", "long_path"]
        )
        
        assert result.has_finalizer_path()
        assert result.get_distance_to_finalizer("short_path") == 2  # short_path -> finalizer + 1
        assert result.get_distance_to_finalizer("long_path") == 3   # long_path -> intermediate -> finalizer + 1
        assert result.get_shortest_finalizer_distance() == 2
        assert result.get_nearest_finalizer_node() == "short_path"
    
    def test_direct_finalizer_vs_indirect_path(self):
        """Test mix of direct finalizer and indirect path."""
        analyzer = FinalizerAnalyzer()
        
        source = Step(uid="source", category=ResourceCategory.NODE, rid="source_rid", type_key="source", writes={"data"})
        
        # Direct finalizer
        direct_finalizer = Step(
            uid="direct_finalizer",
            category=ResourceCategory.NODE,
            rid="direct_rid",
            type_key="direct",
            reads={"data"},
            writes={"output"},  # Direct finalizer
            after=["source"]
        )
        
        # Indirect path
        indirect = Step(
            uid="indirect",
            category=ResourceCategory.NODE,
            rid="indirect_rid",
            type_key="indirect",
            reads={"data"},
            writes={"processed"},
            after=["source"]
        )
        
        final_processor = Step(
            uid="final_processor",
            category=ResourceCategory.NODE,
            rid="final_rid",
            type_key="final",
            reads={"processed"},
            writes={"output"},  # Also a finalizer
            after=["indirect"]
        )
        
        plan = GraphPlan()
        for step in [source, direct_finalizer, indirect, final_processor]:
            plan.add_step(step)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="source",
            adjacent_node_uids=["direct_finalizer", "indirect"]
        )
        
        assert result.has_finalizer_path()
        assert result.get_distance_to_finalizer("direct_finalizer") == 1  # Direct finalizer
        assert result.get_distance_to_finalizer("indirect") == 2  # indirect -> final_processor + 1
        assert result.get_shortest_finalizer_distance() == 1
        assert result.get_nearest_finalizer_node() == "direct_finalizer"


class TestFinalizerAnalyzerCyclePrevention:
    """Test cycle prevention in path analysis."""
    
    def test_simple_cycle_exclusion(self):
        """Test that simple cycles are excluded from path analysis."""
        analyzer = FinalizerAnalyzer()
        
        # Create cycle: A -> B -> A, plus A -> C -> finalizer
        node_a = Step(uid="A", category=ResourceCategory.NODE, rid="A_rid", type_key="A", writes={"data_a"})
        
        node_b = Step(
            uid="B",
            category=ResourceCategory.NODE,
            rid="B_rid",
            type_key="B",
            reads={"data_a"},
            writes={"data_a"},  # Cycles back to A
            after=["A"]
        )
        
        node_c = Step(
            uid="C",
            category=ResourceCategory.NODE,
            rid="C_rid",
            type_key="C",
            reads={"data_a"},
            writes={"data_c"},
            after=["A"]
        )
        
        finalizer = Step(
            uid="finalizer",
            category=ResourceCategory.NODE,
            rid="finalizer_rid",
            type_key="finalizer",
            reads={"data_c"},
            writes={"output"},
            after=["C"]
        )
        
        plan = GraphPlan()
        for step in [node_a, node_b, node_c, finalizer]:
            plan.add_step(step)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="A",
            adjacent_node_uids=["B", "C"]
        )
        
        assert result.has_finalizer_path()
        # B should be excluded because it cycles back through A
        # C should be included because it leads to finalizer
        assert result.get_distance_to_finalizer("C") == 2  # C -> finalizer + 1
        # B might or might not be included depending on cycle detection implementation
        # The key is that we have at least one valid path
        assert result.get_shortest_finalizer_distance() == 2
    
    def test_complex_cycle_with_multiple_exits(self):
        """Test complex cycle with multiple exit points."""
        analyzer = FinalizerAnalyzer()
        
        # Create: source -> [cycle_entry] -> cycle -> [exit1, exit2] -> finalizers
        source = Step(uid="source", category=ResourceCategory.NODE, rid="source_rid", type_key="source", writes={"data"})
        
        cycle_entry = Step(
            uid="cycle_entry",
            category=ResourceCategory.NODE,
            rid="entry_rid",
            type_key="entry",
            reads={"data"},
            writes={"cycle_data"},
            after=["source"]
        )
        
        cycle_node = Step(
            uid="cycle_node",
            category=ResourceCategory.NODE,
            rid="cycle_rid",
            type_key="cycle",
            reads={"cycle_data"},
            writes={"cycle_data"},  # Maintains cycle
            after=["cycle_entry"]
        )
        
        exit1 = Step(
            uid="exit1",
            category=ResourceCategory.NODE,
            rid="exit1_rid",
            type_key="exit1",
            reads={"cycle_data"},
            writes={"output"},  # Direct finalizer
            after=["cycle_entry"]  # Exit from cycle
        )
        
        exit2 = Step(
            uid="exit2",
            category=ResourceCategory.NODE,
            rid="exit2_rid",
            type_key="exit2",
            reads={"cycle_data"},
            writes={"processed"},
            after=["cycle_node"]  # Exit from deeper in cycle
        )
        
        final_finalizer = Step(
            uid="final_finalizer",
            category=ResourceCategory.NODE,
            rid="final_finalizer_rid",
            type_key="final_finalizer",
            reads={"processed"},
            writes={"output"},
            after=["exit2"]
        )
        
        plan = GraphPlan()
        for step in [source, cycle_entry, cycle_node, exit1, exit2, final_finalizer]:
            plan.add_step(step)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="source",
            adjacent_node_uids=["cycle_entry"]
        )
        
        # Should find path through cycle_entry to finalizers
        assert result.has_finalizer_path()
        assert result.get_distance_to_finalizer("cycle_entry") is not None
        assert result.get_distance_to_finalizer("cycle_entry") >= 2  # At least 2 hops


class TestFinalizerAnalyzerEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_no_adjacent_nodes(self):
        """Test analysis with no adjacent nodes."""
        analyzer = FinalizerAnalyzer()
        
        isolated_node = Step(
            uid="isolated",
            category=ResourceCategory.NODE,
            rid="isolated_rid",
            type_key="isolated",
            writes={"output"}  # Is a finalizer but has no adjacent nodes
        )
        
        plan = GraphPlan()
        plan.add_step(isolated_node)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="isolated",
            adjacent_node_uids=[]  # No adjacent nodes
        )
        
        assert isinstance(result, StepTopology)
        assert result.finalizer_paths is None  # No adjacent nodes = no finalizer paths
        assert not result.has_finalizer_path()
    
    def test_no_finalizers_in_graph(self):
        """Test analysis when no nodes write to output channel."""
        analyzer = FinalizerAnalyzer()
        
        node1 = Step(uid="node1", category=ResourceCategory.NODE, rid="node1_rid", type_key="node1", writes={"data1"})
        node2 = Step(uid="node2", category=ResourceCategory.NODE, rid="node2_rid", type_key="node2", reads={"data1"}, writes={"data2"}, after=["node1"])
        
        plan = GraphPlan()
        plan.add_step(node1)
        plan.add_step(node2)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="node1",
            adjacent_node_uids=["node2"]
        )
        
        assert isinstance(result, StepTopology)
        assert result.finalizer_paths is None  # No finalizers found
        assert not result.has_finalizer_path()
    
    def test_adjacent_node_not_in_graph(self):
        """Test analysis with adjacent node that doesn't exist in graph."""
        analyzer = FinalizerAnalyzer()
        
        existing_node = Step(
            uid="existing",
            category=ResourceCategory.NODE,
            rid="existing_rid",
            type_key="existing",
            writes={"data"}
        )
        
        plan = GraphPlan()
        plan.add_step(existing_node)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="existing",
            adjacent_node_uids=["nonexistent"]  # This node doesn't exist
        )
        
        # Should handle gracefully
        assert isinstance(result, StepTopology)
        assert result.finalizer_paths is None  # No valid adjacent nodes
        assert not result.has_finalizer_path()
    
    def test_from_node_not_in_graph(self):
        """Test analysis with from_node that doesn't exist in graph."""
        analyzer = FinalizerAnalyzer()
        
        existing_node = Step(
            uid="existing",
            category=ResourceCategory.NODE,
            rid="existing_rid",
            type_key="existing",
            writes={"output"}
        )
        
        plan = GraphPlan()
        plan.add_step(existing_node)
        
        # This should work - from_node is used for cycle prevention but doesn't need to exist
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="nonexistent",  # This node doesn't exist
            adjacent_node_uids=["existing"]
        )
        
        assert isinstance(result, StepTopology)
        # Should still analyze the adjacent node
        assert result.finalizer_paths is not None
        assert result.has_finalizer_path()
        assert result.get_distance_to_finalizer("existing") == 1


class TestFinalizerAnalyzerCustomOutputChannel:
    """Test FinalizerAnalyzer with custom output channels."""
    
    def test_custom_output_channel(self):
        """Test analyzer with custom output channel."""
        analyzer = FinalizerAnalyzer(output_channel="custom_output")
        
        # Node that writes to custom channel
        custom_finalizer = Step(
            uid="custom_finalizer",
            category=ResourceCategory.NODE,
            rid="custom_rid",
            type_key="custom",
            writes={"custom_output"}  # Custom output channel
        )
        
        # Node that writes to standard output (should be ignored)
        standard_finalizer = Step(
            uid="standard_finalizer",
            category=ResourceCategory.NODE,
            rid="standard_rid",
            type_key="standard",
            writes={"output"}  # Standard output channel
        )
        
        source = Step(uid="source", category=ResourceCategory.NODE, rid="source_rid", type_key="source", writes={"data"})
        
        plan = GraphPlan()
        for step in [source, custom_finalizer, standard_finalizer]:
            plan.add_step(step)
        
        result = analyzer.analyze_node_topology(
            plan=plan,
            from_node_uid="source",
            adjacent_node_uids=["custom_finalizer", "standard_finalizer"]
        )
        
        # Should only find the custom finalizer
        assert result.has_finalizer_path()
        assert result.get_distance_to_finalizer("custom_finalizer") == 1
        assert result.get_distance_to_finalizer("standard_finalizer") is None  # Not a finalizer for custom channel
    
    def test_find_all_finalizers_custom_channel(self):
        """Test find_all_finalizers with custom output channel."""
        analyzer = FinalizerAnalyzer(output_channel="custom_output")
        
        custom_finalizer1 = Step(uid="custom1", category=ResourceCategory.NODE, rid="custom1_rid", type_key="custom1", writes={"custom_output"})
        custom_finalizer2 = Step(uid="custom2", category=ResourceCategory.NODE, rid="custom2_rid", type_key="custom2", writes={"custom_output", "other"})
        standard_finalizer = Step(uid="standard", category=ResourceCategory.NODE, rid="standard_rid", type_key="standard", writes={"output"})
        
        plan = GraphPlan()
        for step in [custom_finalizer1, custom_finalizer2, standard_finalizer]:
            plan.add_step(step)
        
        finalizers = analyzer.find_all_finalizers(plan)
        
        assert finalizers == {"custom1", "custom2"}  # Only custom finalizers
        assert "standard" not in finalizers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
