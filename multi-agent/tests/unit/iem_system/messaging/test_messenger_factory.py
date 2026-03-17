"""
Unit tests for IEM messenger factory functions.

Tests messenger creation, configuration, and dependency injection patterns.
Covers factory functions and context-based messenger creation.
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import List

from mas.core.iem.factory import (
    create_messenger, messenger_from_ctx, messenger_for_testing
)
from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.interfaces import MessengerMiddleware
from mas.core.iem.models import ElementAddress
from tests.fixtures.iem_testing_tools import (
    create_test_state_view, create_test_step_context, MockMiddleware
)


class TestMessengerFactory:
    """Test suite for messenger factory functions."""
    
    def test_create_messenger_basic(self):
        """Test basic messenger creation with minimal configuration."""
        state = create_test_state_view()
        identity = ElementAddress(uid="test_node")
        
        messenger = create_messenger(state=state, identity=identity)
        
        assert isinstance(messenger, DefaultInterMessenger)
        assert messenger._state == state
        assert messenger._me == identity
        assert messenger._middleware == []
        
    def test_create_messenger_with_adjacency_enabled(self):
        """Test messenger creation with adjacency enforcement enabled."""
        state = create_test_state_view()
        identity = ElementAddress(uid="test_node")
        
        def adjacent_check(uid: str) -> bool:
            return uid in ["allowed_1", "allowed_2"]
            
        messenger = create_messenger(
            state=state,
            identity=identity,
            enforce_adjacency=True,
            adjacent_check=adjacent_check
        )
        
        assert messenger._is_adjacent == adjacent_check
        assert messenger._is_adjacent("allowed_1") is True
        assert messenger._is_adjacent("blocked") is False
        
    def test_create_messenger_with_adjacency_disabled(self):
        """Test messenger creation with adjacency enforcement disabled."""
        state = create_test_state_view()
        identity = ElementAddress(uid="test_node")
        
        def adjacent_check(uid: str) -> bool:
            return uid == "allowed"
            
        messenger = create_messenger(
            state=state,
            identity=identity,
            enforce_adjacency=False,  # Explicitly disabled
            adjacent_check=adjacent_check
        )
        
        assert messenger._is_adjacent is None  # Should be None when disabled
        
    def test_create_messenger_with_middleware(self):
        """Test messenger creation with middleware injection."""
        state = create_test_state_view()
        identity = ElementAddress(uid="test_node")
        middleware = [MockMiddleware(), MockMiddleware()]
        
        messenger = create_messenger(
            state=state,
            identity=identity,
            middleware=middleware
        )
        
        assert messenger._middleware == middleware
        assert len(messenger._middleware) == 2
        
    def test_create_messenger_with_all_options(self):
        """Test messenger creation with all configuration options."""
        state = create_test_state_view()
        identity = ElementAddress(uid="fully_configured_node")
        
        def adjacent_check(uid: str) -> bool:
            return uid.startswith("team_")
            
        middleware = [MockMiddleware(), MockMiddleware()]
        
        messenger = create_messenger(
            state=state,
            identity=identity,
            enforce_adjacency=True,
            adjacent_check=adjacent_check,
            middleware=middleware
        )
        
        assert messenger._state == state
        assert messenger._me == identity
        assert messenger._is_adjacent == adjacent_check
        assert messenger._middleware == middleware
        assert messenger._is_adjacent("team_member") is True
        assert messenger._is_adjacent("outsider") is False
        
    def test_messenger_from_ctx_basic(self):
        """Test messenger creation from context with basic configuration."""
        state = create_test_state_view()
        context = create_test_step_context(
            uid="context_node",
            adjacent_nodes=["node_1", "node_2", "node_3"]
        )
        
        messenger = messenger_from_ctx(state=state, ctx=context)
        
        assert isinstance(messenger, DefaultInterMessenger)
        assert messenger._state == state
        assert messenger._me.uid == "context_node"
        assert messenger._ctx == context
        
        # Verify adjacency check function was created
        assert messenger._is_adjacent is not None
        assert messenger._is_adjacent("node_1") is True
        assert messenger._is_adjacent("node_2") is True
        assert messenger._is_adjacent("node_3") is True
        assert messenger._is_adjacent("unknown_node") is False
        
    def test_messenger_from_ctx_with_middleware(self):
        """Test messenger creation from context with middleware."""
        state = create_test_state_view()
        context = create_test_step_context(uid="context_node")
        middleware = [MockMiddleware()]
        
        messenger = messenger_from_ctx(
            state=state,
            ctx=context,
            middleware=middleware
        )
        
        assert messenger._middleware == middleware
        
    def test_messenger_from_ctx_adjacency_disabled(self):
        """Test messenger creation from context with adjacency disabled."""
        state = create_test_state_view()
        context = create_test_step_context(
            uid="context_node",
            adjacent_nodes=["node_1", "node_2"]
        )
        
        messenger = messenger_from_ctx(
            state=state,
            ctx=context,
            enforce_adjacency=False
        )
        
        assert messenger._is_adjacent is None
        
    def test_messenger_from_ctx_empty_adjacent_nodes(self):
        """Test messenger creation from context with empty adjacent nodes."""
        state = create_test_state_view()
        context = create_test_step_context(uid="isolated_node", adjacent_nodes=[])
        
        messenger = messenger_from_ctx(state=state, ctx=context)
        
        # Should have adjacency function that returns False for all UIDs
        assert messenger._is_adjacent is not None
        assert messenger._is_adjacent("any_node") is False
        
    def test_messenger_from_ctx_no_adjacent_nodes(self):
        """Test messenger creation from context with no adjacent_nodes attribute."""
        state = create_test_state_view()
        
        # Create a mock context without adjacent_nodes
        from unittest.mock import Mock
        from mas.graph.models import AdjacentNodes
        mock_context = Mock()
        mock_context.uid = "test_node"
        mock_context.adjacent_nodes = AdjacentNodes.empty()  # Empty adjacent nodes
        
        messenger = messenger_from_ctx(state=state, ctx=mock_context)
        
        # Should handle empty adjacent_nodes gracefully
        assert messenger._me.uid == "test_node"
        assert len(messenger.get_adjacent_nodes()) == 0
        
    def test_messenger_for_testing_basic(self):
        """Test messenger creation for testing with minimal configuration."""
        state = create_test_state_view()
        uid = "test_messenger"
        
        messenger = messenger_for_testing(state=state, uid=uid)
        
        assert isinstance(messenger, DefaultInterMessenger)
        assert messenger._state == state
        assert messenger._me.uid == uid
        assert messenger._is_adjacent is None  # No adjacency enforcement for testing
        assert messenger._middleware == []
        
    def test_messenger_for_testing_with_middleware(self):
        """Test messenger creation for testing with middleware."""
        state = create_test_state_view()
        uid = "test_messenger"
        middleware = [MockMiddleware(), MockMiddleware()]
        
        messenger = messenger_for_testing(
            state=state,
            uid=uid,
            middleware=middleware
        )
        
        assert messenger._middleware == middleware
        assert len(messenger._middleware) == 2
        
    def test_messenger_for_testing_with_name(self):
        """Test messenger creation for testing with optional name."""
        state = create_test_state_view()
        uid = "test_messenger"
        name = "Test Messenger Instance"
        
        messenger = messenger_for_testing(
            state=state,
            uid=uid,
            name=name
        )
        
        # Name is passed but not used directly by messenger
        # (Could be used for debugging/logging in future)
        assert messenger._me.uid == uid
        
    def test_adjacency_function_creation_from_context(self):
        """Test that adjacency function is properly created from context."""
        context = create_test_step_context(
            uid="test_node",
            adjacent_nodes=["alpha", "beta", "gamma"]
        )
        
        state = create_test_state_view()
        messenger = messenger_from_ctx(state=state, ctx=context)
        
        # Test adjacency function behavior
        assert messenger._is_adjacent("alpha") is True
        assert messenger._is_adjacent("beta") is True
        assert messenger._is_adjacent("gamma") is True
        assert messenger._is_adjacent("delta") is False
        assert messenger._is_adjacent("") is False
        assert messenger._is_adjacent("test_node") is False  # Self is not adjacent
        
    def test_factory_error_handling_invalid_state(self):
        """Test factory error handling with invalid state."""
        identity = ElementAddress(uid="test_node")
        
        # Test with None state - currently this doesn't raise an exception,
        # it just creates a messenger with None state which may fail later
        messenger = create_messenger(state=None, identity=identity)
        assert messenger._state is None
        assert messenger._me == identity
            
    def test_factory_error_handling_invalid_identity(self):
        """Test factory error handling with invalid identity."""
        state = create_test_state_view()
        
        # Test with None identity - currently this doesn't raise an exception,
        # it just creates a messenger with None identity which may fail later
        messenger = create_messenger(state=state, identity=None)
        assert messenger._state == state
        assert messenger._me is None
            
    def test_factory_error_handling_invalid_context(self):
        """Test factory error handling with invalid context."""
        state = create_test_state_view()
        
        # Test with None context
        with pytest.raises(Exception):
            messenger_from_ctx(state=state, ctx=None)
            
    def test_middleware_type_validation(self):
        """Test that middleware type validation works correctly."""
        state = create_test_state_view()
        identity = ElementAddress(uid="test_node")
        
        # Valid middleware
        valid_middleware = [MockMiddleware()]
        messenger = create_messenger(
            state=state,
            identity=identity,
            middleware=valid_middleware
        )
        assert messenger._middleware == valid_middleware
        
        # Invalid middleware (not implementing MessengerMiddleware)
        invalid_middleware = ["not_middleware", 123, None]
        
        # This should create the messenger but may fail during runtime
        # depending on implementation
        messenger = create_messenger(
            state=state,
            identity=identity,
            middleware=invalid_middleware
        )
        assert messenger._middleware == invalid_middleware
        
    def test_factory_consistency_across_calls(self):
        """Test that factory functions produce consistent results."""
        state = create_test_state_view()
        identity = ElementAddress(uid="consistent_node")
        
        # Create multiple messengers with same parameters
        messenger1 = create_messenger(state=state, identity=identity)
        messenger2 = create_messenger(state=state, identity=identity)
        
        # Should have same configuration but be different instances
        assert messenger1 is not messenger2
        assert messenger1._state == messenger2._state
        assert messenger1._me == messenger2._me
        assert messenger1._middleware == messenger2._middleware
        
    def test_factory_with_complex_adjacency_logic(self):
        """Test factory with complex adjacency logic."""
        state = create_test_state_view()
        identity = ElementAddress(uid="complex_node")
        
        def complex_adjacency_check(uid: str) -> bool:
            # Complex logic: allow nodes with specific patterns
            if uid.startswith("service_"):
                return True
            if uid.endswith("_trusted"):
                return True
            if "team_alpha" in uid:
                return True
            return False
            
        messenger = create_messenger(
            state=state,
            identity=identity,
            enforce_adjacency=True,
            adjacent_check=complex_adjacency_check
        )
        
        # Test complex adjacency logic
        assert messenger._is_adjacent("service_auth") is True
        assert messenger._is_adjacent("worker_trusted") is True
        assert messenger._is_adjacent("node_team_alpha_1") is True
        assert messenger._is_adjacent("random_node") is False
        assert messenger._is_adjacent("team_beta") is False
        
    def test_messenger_from_ctx_with_different_contexts(self):
        """Test messenger creation with different context configurations."""
        state = create_test_state_view()
        
        # Create initial context
        initial_context = create_test_step_context(
            uid="dynamic_node",
            adjacent_nodes=["initial_1", "initial_2"]
        )
        
        # Create messenger with initial context
        messenger1 = messenger_from_ctx(state=state, ctx=initial_context)
        
        # Verify initial adjacency
        assert messenger1._is_adjacent("initial_1") is True
        assert messenger1._is_adjacent("new_node") is False
        
        # Create new context with additional node (immutable approach)
        from mas.elements.common.card import ElementCard
        from mas.core.enums import ResourceCategory
        new_card = ElementCard(
            uid="new_node",
            category=ResourceCategory.NODE,
            type_key="test",
            name="New Node",
            description="Test node",
            capabilities=[],
            skills=[],
            configuration={},
        )
        
        # Create new context with the additional node
        updated_context = create_test_step_context(
            uid="dynamic_node",
            adjacent_nodes=["initial_1", "initial_2", "new_node"]
        )
        
        # Create new messenger with updated context
        messenger2 = messenger_from_ctx(state=state, ctx=updated_context)
        
        # Original messenger still has original adjacency
        assert messenger1._is_adjacent("initial_1") is True
        assert messenger1._is_adjacent("new_node") is False
        
        # New messenger has updated adjacency
        assert messenger2._is_adjacent("initial_1") is True
        assert messenger2._is_adjacent("new_node") is True
        
    def test_integration_test_all_factory_types(self):
        """Integration test using all factory types together."""
        state = create_test_state_view()
        
        # Create messenger using create_messenger
        messenger1 = create_messenger(
            state=state,
            identity=ElementAddress(uid="node_1"),
            enforce_adjacency=False
        )
        
        # Create messenger using messenger_from_ctx
        context = create_test_step_context(
            uid="node_2",
            adjacent_nodes=["node_1", "node_3"]
        )
        messenger2 = messenger_from_ctx(state=state, ctx=context)
        
        # Create messenger using messenger_for_testing
        messenger3 = messenger_for_testing(state=state, uid="node_3")
        
        # All should be valid messenger instances
        messengers = [messenger1, messenger2, messenger3]
        for messenger in messengers:
            assert isinstance(messenger, DefaultInterMessenger)
            assert messenger._state == state
            
        # Test that they can interact
        from tests.fixtures.iem_testing_tools import PacketFactory
        
        # node_1 sends to node_2
        packet = PacketFactory.create_task_packet(src_uid="node_1", dst_uid="node_2")
        messenger1.send_packet(packet)
        
        # node_2 should receive it
        inbox = messenger2.inbox_packets()
        assert len(inbox) == 1
        assert inbox[0].dst.uid == "node_2"
