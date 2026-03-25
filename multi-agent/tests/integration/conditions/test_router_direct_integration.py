"""
Integration tests for RouterDirectCondition.

Tests the condition in realistic scenarios with:
- Real IEM packet flows
- Orchestrator delegation patterns
- Multi-node communication scenarios
- Workflow routing integration
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any

from mas.elements.conditions.router_direct.router import RouterDirectCondition
from mas.elements.conditions.router_direct.config import RouterDirectConditionConfig
from mas.elements.conditions.router_direct.router_condition_factory import RouterDirectConditionFactory
from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import GraphState, Channel
from mas.graph.models import StepContext
from mas.core.iem.packets import TaskPacket, SystemPacket
from mas.core.iem.models import ElementAddress
from mas.elements.nodes.common.workload import Task
from tests.fixtures.iem_testing_tools import (
    PacketFactory, create_test_step_context, create_test_state_view,
    MockIEMNode, create_basic_iem_test_setup
)


class TestRouterDirectConditionOrchestratorIntegration:
    """Test RouterDirectCondition in orchestrator delegation scenarios."""

    @pytest.fixture
    def orchestrator_context(self):
        """Create context for orchestrator node with worker nodes."""
        return create_test_step_context(
            uid="orchestrator_001",
            adjacent_nodes=["worker_alpha", "worker_beta", "worker_gamma", "storage_service"]
        )

    @pytest.fixture
    def condition(self):
        return RouterDirectCondition()

    def test_orchestrator_delegation_routing(self, condition, orchestrator_context):
        """Test routing based on orchestrator task delegation patterns."""
        state_view = create_test_state_view()
        
        # Simulate orchestrator delegating tasks to different workers
        delegation_packets = [
            # Task delegation to worker_alpha
            PacketFactory.create_task_packet(
                src_uid="orchestrator_001",
                dst_uid="worker_alpha",
                task_content="Process user authentication",
                thread_id="auth_thread_001"
            ),
            # Task delegation to worker_beta  
            PacketFactory.create_task_packet(
                src_uid="orchestrator_001",
                dst_uid="worker_beta",
                task_content="Generate user report",
                thread_id="report_thread_002"
            ),
            # Data storage request
            PacketFactory.create_system_packet(
                src_uid="orchestrator_001",
                dst_uid="storage_service",
                system_event="store_results",
                data={"session_id": "sess_123"}
            )
        ]
        
        state_view.inter_packets = delegation_packets
        condition.set_context(orchestrator_context)
        
        result = condition.run(state_view)
        
        # Should route to all nodes that received delegated work
        expected_targets = ("storage_service", "worker_alpha", "worker_beta")
        assert result == expected_targets
        assert isinstance(result, tuple)

    def test_orchestrator_selective_delegation(self, condition, orchestrator_context):
        """Test routing when orchestrator only delegates to subset of workers."""
        state_view = create_test_state_view()
        
        # Orchestrator only delegates to specific workers based on capabilities
        selective_packets = [
            PacketFactory.create_task_packet(
                src_uid="orchestrator_001",
                dst_uid="worker_alpha",  # Only alpha gets CPU-intensive task
                task_content="Perform complex calculations",
                thread_id="calc_thread"
            )
            # worker_beta and worker_gamma get no tasks
            # storage_service gets no requests
        ]
        
        state_view.inter_packets = selective_packets
        condition.set_context(orchestrator_context)
        
        result = condition.run(state_view)
        
        # Should only route to worker_alpha
        assert result == "worker_alpha"
        assert isinstance(result, str)

    def test_orchestrator_no_delegation_scenario(self, condition, orchestrator_context):
        """Test routing when orchestrator handles everything locally."""
        state_view = create_test_state_view()
        
        # No outgoing packets - orchestrator handles everything locally
        state_view.inter_packets = []
        condition.set_context(orchestrator_context)
        
        result = condition.run(state_view)
        
        # Should return empty string (no routing needed)
        assert result == ""

    def test_orchestrator_mixed_communication_patterns(self, condition, orchestrator_context):
        """Test complex communication patterns with different packet types."""
        state_view = create_test_state_view()
        
        # Mixed communication: tasks, system events, and responses
        mixed_packets = [
            # Task delegation
            PacketFactory.create_task_packet(
                src_uid="orchestrator_001",
                dst_uid="worker_alpha",
                task_content="Primary task",
                thread_id="main_thread"
            ),
            # System coordination
            PacketFactory.create_system_packet(
                src_uid="orchestrator_001", 
                dst_uid="worker_beta",
                system_event="prepare_environment",
                data={"env": "production"}
            ),
            # Storage operation
            PacketFactory.create_system_packet(
                src_uid="orchestrator_001",
                dst_uid="storage_service",
                system_event="backup_state"
            ),
            # Debug/monitoring
            PacketFactory.create_debug_packet(
                src_uid="orchestrator_001",
                dst_uid="worker_gamma",
                debug_info={"monitor": "performance"}
            )
        ]
        
        state_view.inter_packets = mixed_packets
        condition.set_context(orchestrator_context)
        
        result = condition.run(state_view)
        
        # Should route to all nodes involved in communication
        expected_targets = ("storage_service", "worker_alpha", "worker_beta", "worker_gamma")
        assert result == expected_targets


class TestRouterDirectConditionMultiNodeScenarios:
    """Test condition in multi-node communication scenarios."""

    @pytest.fixture
    def multi_node_setup(self):
        """Create multi-node test setup."""
        return create_basic_iem_test_setup(node_count=5)

    def test_hub_node_routing(self, multi_node_setup):
        """Test routing for a hub node communicating with multiple nodes."""
        condition = RouterDirectCondition()
        
        # Set up hub node context
        hub_context = create_test_step_context(
            uid="hub_node",
            adjacent_nodes=["node_1", "node_2", "node_3", "node_4", "node_5"]
        )
        
        state_view = multi_node_setup["state"]
        
        # Hub broadcasts to multiple nodes
        broadcast_packets = [
            PacketFactory.create_system_packet(
                src_uid="hub_node",
                dst_uid=f"node_{i}",
                system_event="sync_update",
                data={"version": "2.1.0"}
            ) for i in range(1, 6)
        ]
        
        state_view.inter_packets = broadcast_packets
        condition.set_context(hub_context)
        
        result = condition.run(state_view)
        
        # Should route to all nodes
        expected_targets = tuple(f"node_{i}" for i in range(1, 6))
        assert result == expected_targets

    def test_peer_to_peer_routing(self, multi_node_setup):
        """Test routing in peer-to-peer communication scenario."""
        condition = RouterDirectCondition()
        
        # Set up peer node context
        peer_context = create_test_step_context(
            uid="node_1",
            adjacent_nodes=["node_2", "node_3"]  # Only connected to 2 peers
        )
        
        state_view = multi_node_setup["state"]
        
        # Peer communicates with subset of network
        peer_packets = [
            PacketFactory.create_task_packet(
                src_uid="node_1",
                dst_uid="node_2",
                task_content="Coordinate with peer",
                thread_id="peer_coord"
            ),
            PacketFactory.create_system_packet(
                src_uid="node_1",
                dst_uid="node_3",
                system_event="share_data"
            )
        ]
        
        state_view.inter_packets = peer_packets
        condition.set_context(peer_context)
        
        result = condition.run(state_view)
        
        assert result == ("node_2", "node_3")

    def test_isolated_node_routing(self, multi_node_setup):
        """Test routing for isolated node with no adjacent connections."""
        condition = RouterDirectCondition()
        
        # Set up isolated node context
        isolated_context = create_test_step_context(
            uid="isolated_node",
            adjacent_nodes=[]  # No connections
        )
        
        state_view = multi_node_setup["state"]
        
        # Isolated node tries to send packets (shouldn't route anywhere)
        isolation_packets = [
            PacketFactory.create_task_packet(
                src_uid="isolated_node",
                dst_uid="node_1",
                task_content="Attempt to reach network"
            )
        ]
        
        state_view.inter_packets = isolation_packets
        condition.set_context(isolated_context)
        
        result = condition.run(state_view)
        
        # Should return empty (no adjacent nodes to route to)
        assert result == ""


class TestRouterDirectConditionWorkflowIntegration:
    """Test condition integration with workflow systems."""

    def test_workflow_branching_single_path(self):
        """Test workflow branching to single execution path."""
        condition = RouterDirectCondition()
        
        # Workflow node context
        workflow_context = create_test_step_context(
            uid="workflow_orchestrator",
            adjacent_nodes=["data_processor", "notification_service", "audit_logger"]
        )
        
        state_view = create_test_state_view()
        
        # Workflow sends task to single processor
        workflow_packets = [
            PacketFactory.create_task_packet(
                src_uid="workflow_orchestrator",
                dst_uid="data_processor",
                task_content="Process user data",
                thread_id="data_processing_workflow"
            )
        ]
        
        state_view.inter_packets = workflow_packets
        condition.set_context(workflow_context)
        
        result = condition.run(state_view)
        
        # Workflow should branch to data_processor
        assert result == "data_processor"

    def test_workflow_branching_parallel_paths(self):
        """Test workflow branching to multiple parallel execution paths."""
        condition = RouterDirectCondition()
        
        workflow_context = create_test_step_context(
            uid="workflow_orchestrator",
            adjacent_nodes=["data_processor", "notification_service", "audit_logger"]
        )
        
        state_view = create_test_state_view()
        
        # Workflow triggers parallel execution
        parallel_packets = [
            PacketFactory.create_task_packet(
                src_uid="workflow_orchestrator",
                dst_uid="data_processor",
                task_content="Process data",
                thread_id="parallel_workflow"
            ),
            PacketFactory.create_task_packet(
                src_uid="workflow_orchestrator",
                dst_uid="notification_service", 
                task_content="Send notifications",
                thread_id="parallel_workflow"
            ),
            PacketFactory.create_task_packet(
                src_uid="workflow_orchestrator",
                dst_uid="audit_logger",
                task_content="Log audit trail",
                thread_id="parallel_workflow"
            )
        ]
        
        state_view.inter_packets = parallel_packets
        condition.set_context(workflow_context)
        
        result = condition.run(state_view)
        
        # Should branch to all parallel paths
        expected_paths = ("audit_logger", "data_processor", "notification_service")
        assert result == expected_paths

    def test_workflow_conditional_routing(self):
        """Test conditional routing based on workflow state."""
        condition = RouterDirectCondition()
        
        workflow_context = create_test_step_context(
            uid="conditional_workflow",
            adjacent_nodes=["success_handler", "error_handler", "retry_service"]
        )
        
        state_view = create_test_state_view()
        
        # Workflow routes to error handler based on condition
        conditional_packets = [
            PacketFactory.create_task_packet(
                src_uid="conditional_workflow",
                dst_uid="error_handler",
                task_content="Handle processing error",
                thread_id="error_workflow"
            ),
            PacketFactory.create_system_packet(
                src_uid="conditional_workflow",
                dst_uid="retry_service",
                system_event="schedule_retry",
                data={"retry_count": 1}
            )
        ]
        
        state_view.inter_packets = conditional_packets
        condition.set_context(workflow_context)
        
        result = condition.run(state_view)
        
        # Should route to error handling path
        assert result == ("error_handler", "retry_service")


class TestRouterDirectConditionRealWorldScenarios:
    """Test condition in realistic production-like scenarios."""

    def test_microservices_orchestration(self):
        """Test routing in microservices orchestration scenario."""
        condition = RouterDirectCondition()
        
        # API Gateway orchestrating microservices
        gateway_context = create_test_step_context(
            uid="api_gateway",
            adjacent_nodes=[
                "user_service", "payment_service", "inventory_service", 
                "notification_service", "analytics_service"
            ]
        )
        
        state_view = create_test_state_view()
        
        # E-commerce order processing flow
        order_packets = [
            # Validate user
            PacketFactory.create_task_packet(
                src_uid="api_gateway",
                dst_uid="user_service",
                task_content="Validate user credentials",
                thread_id="order_12345"
            ),
            # Process payment
            PacketFactory.create_task_packet(
                src_uid="api_gateway", 
                dst_uid="payment_service",
                task_content="Process payment",
                thread_id="order_12345"
            ),
            # Check inventory
            PacketFactory.create_task_packet(
                src_uid="api_gateway",
                dst_uid="inventory_service",
                task_content="Reserve inventory",
                thread_id="order_12345"
            ),
            # Send confirmation
            PacketFactory.create_task_packet(
                src_uid="api_gateway",
                dst_uid="notification_service",
                task_content="Send order confirmation",
                thread_id="order_12345"
            )
        ]
        
        state_view.inter_packets = order_packets
        condition.set_context(gateway_context)
        
        result = condition.run(state_view)
        
        # Should route to all involved services
        expected_services = (
            "inventory_service", "notification_service", 
            "payment_service", "user_service"
        )
        assert result == expected_services

    def test_data_pipeline_orchestration(self):
        """Test routing in data pipeline orchestration."""
        condition = RouterDirectCondition()
        
        # Data pipeline orchestrator
        pipeline_context = create_test_step_context(
            uid="data_orchestrator",
            adjacent_nodes=[
                "data_ingestion", "data_validation", "data_transformation",
                "data_storage", "data_analytics", "alert_service"
            ]
        )
        
        state_view = create_test_state_view()
        
        # Data processing pipeline
        pipeline_packets = [
            # Ingest data
            PacketFactory.create_task_packet(
                src_uid="data_orchestrator",
                dst_uid="data_ingestion",
                task_content="Ingest batch data",
                thread_id="batch_001"
            ),
            # Validate data quality
            PacketFactory.create_task_packet(
                src_uid="data_orchestrator",
                dst_uid="data_validation",
                task_content="Validate data quality",
                thread_id="batch_001"
            ),
            # Transform data
            PacketFactory.create_task_packet(
                src_uid="data_orchestrator",
                dst_uid="data_transformation",
                task_content="Apply transformations",
                thread_id="batch_001"
            )
        ]
        
        state_view.inter_packets = pipeline_packets
        condition.set_context(pipeline_context)
        
        result = condition.run(state_view)
        
        # Should route to active pipeline stages
        expected_stages = ("data_ingestion", "data_transformation", "data_validation")
        assert result == expected_stages

    def test_ml_training_orchestration(self):
        """Test routing in ML training orchestration scenario."""
        condition = RouterDirectCondition()
        
        # ML training orchestrator
        ml_context = create_test_step_context(
            uid="ml_orchestrator",
            adjacent_nodes=[
                "data_preprocessor", "feature_engineer", "model_trainer",
                "model_validator", "model_deployer", "monitoring_service"
            ]
        )
        
        state_view = create_test_state_view()
        
        # ML training pipeline
        ml_packets = [
            # Preprocess training data
            PacketFactory.create_task_packet(
                src_uid="ml_orchestrator",
                dst_uid="data_preprocessor",
                task_content="Preprocess training dataset",
                thread_id="training_job_001"
            ),
            # Engineer features
            PacketFactory.create_task_packet(
                src_uid="ml_orchestrator",
                dst_uid="feature_engineer",
                task_content="Generate feature vectors",
                thread_id="training_job_001"
            ),
            # Train model
            PacketFactory.create_task_packet(
                src_uid="ml_orchestrator",
                dst_uid="model_trainer",
                task_content="Train neural network",
                thread_id="training_job_001"
            ),
            # Set up monitoring
            PacketFactory.create_system_packet(
                src_uid="ml_orchestrator",
                dst_uid="monitoring_service",
                system_event="setup_training_monitoring",
                data={"job_id": "training_job_001"}
            )
        ]
        
        state_view.inter_packets = ml_packets
        condition.set_context(ml_context)
        
        result = condition.run(state_view)
        
        # Should route to all active ML pipeline components
        expected_components = (
            "data_preprocessor", "feature_engineer", 
            "model_trainer", "monitoring_service"
        )
        assert result == expected_components


class TestRouterDirectConditionErrorRecovery:
    """Test condition behavior during error and recovery scenarios."""

    def test_partial_network_failure(self):
        """Test routing when some nodes are unreachable."""
        condition = RouterDirectCondition()
        
        # Network with some failed nodes
        network_context = create_test_step_context(
            uid="resilient_orchestrator",
            adjacent_nodes=["healthy_node_1", "healthy_node_2", "failed_node", "recovering_node"]
        )
        
        state_view = create_test_state_view()
        
        # Only send to healthy and recovering nodes
        recovery_packets = [
            PacketFactory.create_task_packet(
                src_uid="resilient_orchestrator",
                dst_uid="healthy_node_1",
                task_content="Primary task"
            ),
            PacketFactory.create_task_packet(
                src_uid="resilient_orchestrator",
                dst_uid="recovering_node",
                task_content="Recovery task"
            )
            # No packets to failed_node
        ]
        
        state_view.inter_packets = recovery_packets
        condition.set_context(network_context)
        
        result = condition.run(state_view)
        
        # Should only route to nodes that received packets
        assert result == ("healthy_node_1", "recovering_node")

    def test_retry_mechanism_routing(self):
        """Test routing during retry scenarios."""
        condition = RouterDirectCondition()
        
        retry_context = create_test_step_context(
            uid="retry_orchestrator",
            adjacent_nodes=["primary_service", "backup_service", "fallback_service"]
        )
        
        state_view = create_test_state_view()
        
        # Retry pattern: try backup after primary failure
        retry_packets = [
            PacketFactory.create_task_packet(
                src_uid="retry_orchestrator",
                dst_uid="backup_service",
                task_content="Retry failed operation",
                thread_id="retry_attempt_2"
            )
            # Primary service failed, so no packet to it
        ]
        
        state_view.inter_packets = retry_packets
        condition.set_context(retry_context)
        
        result = condition.run(state_view)
        
        # Should route to backup service
        assert result == "backup_service"
