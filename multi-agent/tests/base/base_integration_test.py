"""
Base test class for integration tests.

Provides common setup/teardown and utilities specific to integration testing,
including multi-component setup, scenario builders, and end-to-end workflows.
"""

import pytest
from typing import List, Dict, Any, Optional
from unittest.mock import patch

from tests.base.base_node_test import BaseNodeTest


class BaseIntegrationTest(BaseNodeTest):
    """
    Base class for integration tests.
    
    Extends BaseNodeTest with integration-specific utilities like multi-node
    setup, workflow execution, and end-to-end verification.
    
    Integration tests verify that multiple components work together correctly,
    using real implementations with minimal mocking.
    """
    
    def setup_multi_node_scenario(
        self,
        orchestrator_config: Dict[str, Any] = None,
        agent_configs: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Set up a multi-node scenario with orchestrator and agents.
        
        Args:
            orchestrator_config: Configuration for orchestrator node
            agent_configs: List of configurations for agent nodes
            
        Returns:
            Dict containing all created nodes and configuration
        """
        from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
        from mas.elements.nodes.custom_agent.custom_agent import CustomAgentNode
        
        orchestrator_config = orchestrator_config or {}
        agent_configs = agent_configs or []
        
        # Create orchestrator
        orchestrator_uid = orchestrator_config.get('uid', 'test_orchestrator')
        agent_uids = [cfg.get('uid', f'agent_{i}') for i, cfg in enumerate(agent_configs)]
        
        orchestrator = self.create_node_with_state(
            OrchestratorNode,
            uid=orchestrator_uid,
            adjacent_nodes=agent_uids,
            **{k: v for k, v in orchestrator_config.items() if k != 'uid'}
        )
        
        # Create agents
        agents = []
        for i, agent_config in enumerate(agent_configs):
            agent_uid = agent_config.get('uid', f'agent_{i}')
            
            agent = self.create_node_with_state(
                CustomAgentNode,
                uid=agent_uid,
                adjacent_nodes=[orchestrator_uid],
                **{k: v for k, v in agent_config.items() if k != 'uid'}
            )
            agents.append(agent)
        
        return {
            'orchestrator': orchestrator,
            'agents': agents,
            'orchestrator_uid': orchestrator_uid,
            'agent_uids': agent_uids
        }
    
    def execute_full_workflow(
        self,
        orchestrator,
        initial_task_content: str,
        thread_id: str = "test_thread",
        mock_send_task: bool = True,
        mock_adjacent_nodes: bool = True
    ):
        """
        Execute a full workflow from task to completion.
        
        Args:
            orchestrator: The orchestrator node
            initial_task_content: Content for the initial task
            thread_id: Thread ID for the workflow
            mock_send_task: Whether to mock send_task method
            mock_adjacent_nodes: Whether to mock get_adjacent_nodes
            
        Returns:
            Workflow execution result
        """
        from mas.elements.nodes.common.workload import Task
        from mas.core.iem.packets import TaskPacket
        from mas.core.iem.models import ElementAddress
        
        # Create initial task
        task = Task(
            content=initial_task_content,
            thread_id=thread_id,
            created_by="user",
            should_respond=True,
            response_to="user"
        )
        
        # Create packet
        packet = TaskPacket.create(
            src=ElementAddress(uid="user"),
            dst=ElementAddress(uid=orchestrator.uid),
            task=task
        )
        
        # Add to state
        self.state.inter_packets.append(packet)
        
        # Set up mocks if requested
        patches = []
        
        if mock_send_task:
            send_task_patch = patch.object(
                orchestrator, 
                'send_task', 
                return_value=f"sent_task_{thread_id}"
            )
            patches.append(send_task_patch)
        
        if mock_adjacent_nodes:
            adjacent_nodes_patch = patch.object(
                orchestrator,
                'get_adjacent_nodes',
                return_value=self.create_mock_adjacent_nodes()
            )
            patches.append(adjacent_nodes_patch)
        
        # Execute with patches
        with patch.multiple('', **{f'patch_{i}': p for i, p in enumerate(patches)}):
            for p in patches:
                p.start()
            
            try:
                # Execute the workflow
                result = orchestrator.run(self.state)
                return result
            finally:
                for p in patches:
                    p.stop()
    
    def simulate_agent_response(
        self,
        orchestrator,
        correlation_task_id: str,
        response_content: str,
        thread_id: str,
        agent_uid: str = "test_agent",
        success: bool = True
    ):
        """
        Simulate an agent response to the orchestrator.
        
        Args:
            orchestrator: The orchestrator node
            correlation_task_id: ID of the task being responded to
            response_content: Content of the response
            thread_id: Thread ID
            agent_uid: UID of the responding agent
            success: Whether the response indicates success
        """
        from mas.elements.nodes.common.workload import Task
        from mas.core.iem.packets import TaskPacket
        from mas.core.iem.models import ElementAddress
        
        # Create response task
        response_task = Task(
            content=response_content,
            thread_id=thread_id,
            created_by=agent_uid,
            correlation_task_id=correlation_task_id,
            result={"success": success, "content": response_content}
        )
        
        # Create response packet
        packet = TaskPacket.create(
            src=ElementAddress(uid=agent_uid),
            dst=ElementAddress(uid=orchestrator.uid),
            task=response_task
        )
        
        # Add to state and process
        self.state.inter_packets.append(packet)
        orchestrator.handle_task_packet(packet)
    
    def verify_workflow_completion(
        self,
        orchestrator_uid: str,
        thread_id: str,
        expected_completed_items: int = None
    ):
        """
        Verify workflow completed successfully.
        
        Args:
            orchestrator_uid: Orchestrator UID
            thread_id: Thread ID
            expected_completed_items: Expected number of completed work items
        """
        from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
        
        storage = StateBoundStorage(self.state)
        service = UnifiedWorkloadService(storage)
        
        # Use current API: workspaces.load_work_plan()
        work_plan = service.get_workspace_service().load_work_plan(thread_id, orchestrator_uid)
        assert work_plan is not None, "WorkPlan should exist"
        
        if expected_completed_items is not None:
            from mas.elements.nodes.common.workload import WorkItemStatus
            completed_items = [
                item for item in work_plan.items.values()
                if item.status == WorkItemStatus.DONE
            ]
            assert len(completed_items) == expected_completed_items, \
                f"Expected {expected_completed_items} completed items, got {len(completed_items)}"
    
    def assert_no_errors_in_workflow(self):
        """Assert no error packets or failed states in workflow."""
        # Check for error packets in state
        packets = self.state.inter_packets
        error_packets = [p for p in packets if hasattr(p, 'is_error') and p.is_error]
        
        assert len(error_packets) == 0, \
            f"Found {len(error_packets)} error packets in workflow"
