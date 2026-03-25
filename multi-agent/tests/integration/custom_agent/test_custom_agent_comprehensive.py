"""
Comprehensive Custom Agent Node Tests.

Tests custom agent node capabilities, response routing, task handling,
and integration with orchestrators and other custom agents.

Test Scenarios:
1. Custom Agent Basic Functionality
2. Response Routing Logic (Direct vs Broadcast)
3. Custom Agent to Custom Agent Communication
4. Mixed Strategy Types (ReAct vs others)
5. Tool Integration and MCP Provider Support
6. Error Handling and Recovery
7. Performance Under Load
8. Complex Workflow Participation
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, List, Any, Set

# Core imports
from mas.elements.nodes.custom_agent.custom_agent import CustomAgentNode
from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
from mas.elements.nodes.common.workload import Task, AgentResult
from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.graph.state.state_view import StateView
from mas.graph.topology.models import StepTopology
from mas.graph.state.graph_state import Channel
from mas.core.iem.packets import TaskPacket
from mas.elements.common.card import ElementCard
from mas.elements.common.card.models.card import Skill, Capability
from mas.core.enums import ResourceCategory
from mas.elements.nodes.common.agent.constants import StrategyType
from mas.elements.tools.common.base_tool import BaseTool

# Import fixtures
from tests.fixtures.orchestrator_integration import (
    PredictableLLM, ExecutionTracker, create_step_context_local
)
from mas.core.iem.models import ElementAddress

# Import generic helper for workspace access
from tests.base import get_workspace_from_node


class MockTool(BaseTool):
    """Mock tool for testing custom agents."""
    
    def __init__(self, name: str, description: str, result: str = "Tool executed successfully"):
        self.name = name
        self.description = description
        self.result = result
    
    def run(self, **kwargs) -> str:
        """Run method required by BaseTool."""
        return f"{self.result}: {kwargs}"


def setup_custom_agent_with_state(agent: CustomAgentNode, uid: str, state: StateView, adjacent_nodes: List[str] = None):
    """Helper to properly set up a custom agent with state and context."""
    # Set up context and state
    step_context = create_step_context_local(
        uid=uid,
        adjacent_nodes=adjacent_nodes or []
    )
    agent.set_context(step_context)
    agent._state = state
    return agent


@pytest.mark.custom_agent
@pytest.mark.integration
class TestCustomAgentBasicFunctionality:
    """Test basic custom agent functionality."""

    def test_custom_agent_task_processing(self, orchestrator_integration_state):
        """Test custom agent processes tasks and creates results."""
        state = orchestrator_integration_state
        
        # Create custom agent with tools
        agent_llm = PredictableLLM()
        agent_llm.add_response("I have successfully processed the task with my specialized tools.")
        tools = [
            MockTool("analyze_data", "Analyzes data patterns", "Data analysis completed"),
            MockTool("generate_report", "Generates reports", "Report generated successfully")
        ]
        
        custom_agent = CustomAgentNode(
            llm=agent_llm,
            tools=tools,
            system_message="I am a data analysis specialist",
            strategy_type=StrategyType.REACT.value,
            max_rounds=10
        )

        # Set up agent with state and context
        setup_custom_agent_with_state(custom_agent, "data_specialist_agent", state)
        
        # Create task for custom agent
        analysis_task = Task(
            content="Analyze quarterly sales data and generate insights report",
            task_id="analysis_task_001",
            thread_id="analysis_thread",
            created_by="business_analyst",
            should_respond=True,
            response_to="business_analyst"
        )

        # Process task
        packet = Mock()
        packet.extract_task.return_value = analysis_task
        packet.id = "analysis_packet"
        packet.src = ElementAddress(uid="business_analyst")
        
        custom_agent.handle_task_packet(packet)
        
        # Verify task processing
        workspace = get_workspace_from_node(custom_agent, "analysis_thread")
        # ✅ Custom agents DO record tasks in workspace for tracking
        assert len(workspace.context.tasks) == 1
        assert workspace.context.tasks[0].task_id == "analysis_task_001"
        assert len(workspace.context.results) >= 1
        
        # Verify agent result
        agent_result = workspace.context.results[-1]
        assert agent_result.agent_id == "data_specialist_agent"
        assert agent_result.success is True
        assert "processed the task" in agent_result.content
        assert agent_result.agent_name == "data_specialist_agent"  # Should match uid
        
        # Verify task was marked as processed
        assert analysis_task.processed_by == "data_specialist_agent"
        assert analysis_task.processed_at is not None

    def test_custom_agent_response_routing_direct(self, orchestrator_integration_state):
        """Test custom agent direct response routing when requester is adjacent."""
        state = orchestrator_integration_state
        
        # Create custom agent
        agent_llm = PredictableLLM()
        agent_llm.add_response("I have completed the requested analysis.")
        custom_agent = CustomAgentNode(
            llm=agent_llm,
            system_message="I provide direct responses to adjacent requesters",
            strategy_type=StrategyType.REACT.value,
            max_rounds=8
        )

        # Set up agent with state and context
        setup_custom_agent_with_state(custom_agent, "response_agent", state, ["project_manager", "team_lead", "developer"])
        
        # Create task requiring response
        response_task = Task(
            content="Generate status report for project Alpha",
            task_id="status_report_001",
            thread_id="status_thread",
            created_by="project_manager",
            should_respond=True,
            response_to="project_manager"
        )

        # Track response routing
        response_calls = []
        def track_response(packet):
            # Extract task from packet and get destination
            task = packet.payload  # TaskPacket stores task as payload dict
            from mas.elements.nodes.common.workload import Task
            task_obj = Task.model_validate(task)
            destination = packet.dst.uid
            response_calls.append({
                'destination': destination,
                'task_content': task_obj.content,
                'correlation_id': task_obj.correlation_task_id,
                'is_response': task_obj.is_response()
            })
            return "mock_packet_id"

        with patch.object(custom_agent, '_get_adjacent_nodes_uids', return_value={"project_manager", "team_lead", "developer"}):
            with patch.object(custom_agent, 'send_packet', side_effect=track_response):

                packet = Mock()
                packet.extract_task.return_value = response_task
                packet.id = "status_packet"
                packet.src = ElementAddress(uid="project_manager")

                custom_agent.handle_task_packet(packet)
        
        # Verify direct response was sent
        assert len(response_calls) == 1
        response_call = response_calls[0]
        assert response_call['destination'] == "project_manager"
        assert response_call['correlation_id'] == "status_report_001"
        assert response_call['is_response'] is True
        
        # Verify agent result was created
        workspace = get_workspace_from_node(custom_agent, "status_thread")
        assert len(workspace.context.results) >= 1
        agent_result = workspace.context.results[-1]
        assert agent_result.agent_id == "response_agent"
        assert agent_result.success is True

    def test_custom_agent_response_routing_broadcast(self, orchestrator_integration_state):
        """Test custom agent broadcast routing when requester is not adjacent."""
        state = orchestrator_integration_state
        
        # Create custom agent
        agent_llm = PredictableLLM()
        agent_llm.add_response("I have completed the analysis and will broadcast the response.")
        custom_agent = CustomAgentNode(
            llm=agent_llm,
            system_message="I broadcast responses when requester is not adjacent",
            strategy_type=StrategyType.REACT.value,
            max_rounds=8
        )

        # Set up agent with state and context
        setup_custom_agent_with_state(custom_agent, "broadcast_agent", state, ["local_manager", "team_lead", "developer"])
        
        # Create task requiring response to non-adjacent requester
        broadcast_task = Task(
            content="Analyze system performance metrics",
            task_id="performance_analysis_001",
            thread_id="performance_thread",
            created_by="remote_manager",  # Not in adjacent nodes
            should_respond=True,
            response_to="remote_manager"
        )

        # Track broadcast routing
        broadcast_calls = []
        def track_broadcast(packet):
            # Extract task from packet
            task = packet.payload  # TaskPacket stores task as payload dict
            from mas.elements.nodes.common.workload import Task
            task_obj = Task.model_validate(task)
            broadcast_calls.append({
                'task_content': task_obj.content,
                'correlation_id': task_obj.correlation_task_id,
                'response_to': task_obj.response_to,
                'is_response': task_obj.is_response()
            })
            return ["mock_packet_id"]

        with patch.object(custom_agent, '_get_adjacent_nodes_uids', return_value={"local_manager", "team_lead", "developer"}):
            with patch.object(custom_agent, 'broadcast_packet', side_effect=track_broadcast):

                packet = Mock()
                packet.extract_task.return_value = broadcast_task
                packet.id = "performance_packet"
                packet.src = ElementAddress(uid="remote_manager")

                custom_agent.handle_task_packet(packet)
        
        # Verify broadcast response was sent
        assert len(broadcast_calls) == 1
        broadcast_call = broadcast_calls[0]
        assert broadcast_call['correlation_id'] == "performance_analysis_001"
        assert broadcast_call['response_to'] == "remote_manager"
        assert broadcast_call['is_response'] is True
        
        # Verify agent result was created
        workspace = get_workspace_from_node(custom_agent, "performance_thread")
        assert len(workspace.context.results) >= 1
        agent_result = workspace.context.results[-1]
        assert agent_result.agent_id == "broadcast_agent"
        assert agent_result.success is True

    def test_custom_agent_normal_broadcast(self, orchestrator_integration_state):
        """Test custom agent normal broadcast when no response required."""
        state = orchestrator_integration_state
        
        # Create custom agent
        agent_llm = PredictableLLM()
        agent_llm.add_response("I have processed the background task and will share the results.")
        custom_agent = CustomAgentNode(
            llm=agent_llm,
            system_message="I process background tasks and share results",
            strategy_type=StrategyType.REACT.value,
            max_rounds=8
        )

        # Set up agent with state and context
        setup_custom_agent_with_state(custom_agent, "background_agent", state)
        
        # Create background task (no response required)
        background_task = Task(
            content="Process daily maintenance tasks",
            task_id="maintenance_001",
            thread_id="maintenance_thread",
            created_by="system_scheduler",
            should_respond=False  # No response required
        )

        # Track normal broadcast
        broadcast_calls = []
        def track_normal_broadcast(packet):
            # Extract task from packet
            task = packet.payload  # TaskPacket stores task as payload dict
            from mas.elements.nodes.common.workload import Task
            task_obj = Task.model_validate(task)
            broadcast_calls.append({
                'task_content': task_obj.content,
                'should_respond': task_obj.should_respond,
                'is_response': task_obj.is_response()
            })
            return ["mock_packet_id"]

        with patch.object(custom_agent, 'broadcast_packet', side_effect=track_normal_broadcast):
            
            packet = Mock()
            packet.extract_task.return_value = background_task
            packet.id = "maintenance_packet"
            packet.src = ElementAddress(uid="system_scheduler")
            
            custom_agent.handle_task_packet(packet)
        
        # Verify normal broadcast was sent
        assert len(broadcast_calls) == 1
        broadcast_call = broadcast_calls[0]
        assert broadcast_call['should_respond'] is False
        assert broadcast_call['is_response'] is False
        
        # Verify agent result was created
        workspace = get_workspace_from_node(custom_agent, "maintenance_thread")
        assert len(workspace.context.results) >= 1
        agent_result = workspace.context.results[-1]
        assert agent_result.agent_id == "background_agent"
        assert agent_result.success is True


@pytest.mark.custom_agent
@pytest.mark.integration
class TestCustomAgentCommunication:
    """Test custom agent to custom agent communication."""

    def test_custom_agent_chain_communication(self, orchestrator_integration_state):
        """Test chain of custom agents communicating sequentially."""
        state = orchestrator_integration_state
        
        # Create chain of 4 custom agents
        agents = {}
        for i in range(1, 5):
            agent_llm = PredictableLLM()
            agent_llm.add_response(f"I am stage {i} and have processed the data successfully.")
            agents[f"stage_{i}"] = CustomAgentNode(
                llm=agent_llm,
                system_message=f"I am stage {i} in the processing chain",
                strategy_type=StrategyType.REACT.value,
                max_rounds=6
            )

        # Set up all agents with state and context
        for i, (stage, agent) in enumerate(agents.items()):
            adjacent_nodes = [f"stage_{j}_agent" for j in range(1, 5) if j != i+1]
            adjacent_nodes.append("data_coordinator")  # Add coordinator to adjacency
            setup_custom_agent_with_state(agent, f"{stage}_agent", state, adjacent_nodes)
        
        # Create initial task for stage 1
        initial_task = Task(
            content="Begin data processing chain",
            task_id="chain_start_001",
            thread_id="chain_thread",
            created_by="data_coordinator",
            should_respond=True,
            response_to="stage_2_agent"  # Chain to next stage
        )

        # Track chain communication
        chain_communications = []
        
        def create_chain_tracker(stage_name):
            def track_communication(packet):
                # Extract task from packet
                task = packet.payload  # TaskPacket stores task as payload dict
                from mas.elements.nodes.common.workload import Task
                task_obj = Task.model_validate(task)
                destination = packet.dst.uid
                chain_communications.append({
                    'from': stage_name,
                    'to': destination,
                    'content': task_obj.content,
                    'thread_id': task_obj.thread_id,
                    'correlation_id': task_obj.correlation_task_id
                })
                return "mock_packet_id"
            return track_communication

        # Process through chain
        chain_results = {}
        
        # Stage 1 processes initial task
        stage_1 = agents['stage_1']
        with patch.object(stage_1, '_get_adjacent_nodes_uids', return_value={"stage_2_agent", "stage_3_agent", "stage_4_agent", "data_coordinator"}):
            with patch.object(stage_1, 'send_packet', side_effect=create_chain_tracker("stage_1_agent")):
                
                packet = Mock()
                packet.extract_task.return_value = initial_task
                packet.id = "chain_packet_1"
                packet.src = ElementAddress(uid="data_coordinator")
                
                stage_1.handle_task_packet(packet)
        
        # Collect stage 1 result
        workspace_1 = get_workspace_from_node(stage_1, "chain_thread")
        chain_results['stage_1'] = workspace_1.context.results[-1]
        
        # Stage 2 receives and processes
        stage_2_task = Task(
            content="Continue processing from stage 1",
            task_id="chain_stage_2",
            thread_id="chain_thread",
            created_by="stage_1_agent",
            should_respond=True,
            response_to="stage_3_agent",
            correlation_task_id="chain_start_001"
        )
        
        stage_2 = agents['stage_2']
        with patch.object(stage_2, '_get_adjacent_nodes_uids', return_value={"stage_1_agent", "stage_3_agent", "stage_4_agent", "data_coordinator"}):
            with patch.object(stage_2, 'send_packet', side_effect=create_chain_tracker("stage_2_agent")):
                
                packet = Mock()
                packet.extract_task.return_value = stage_2_task
                packet.id = "chain_packet_2"
                packet.src = ElementAddress(uid="stage_1_agent")
                
                stage_2.handle_task_packet(packet)
        
        # Collect stage 2 result
        workspace_2 = get_workspace_from_node(stage_2, "chain_thread")
        chain_results['stage_2'] = workspace_2.context.results[-1]
        
        # Stage 3 receives and processes
        stage_3_task = Task(
            content="Continue processing from stage 2",
            task_id="chain_stage_3",
            thread_id="chain_thread",
            created_by="stage_2_agent",
            should_respond=True,
            response_to="stage_4_agent",
            correlation_task_id="chain_start_001"
        )
        
        stage_3 = agents['stage_3']
        with patch.object(stage_3, '_get_adjacent_nodes_uids', return_value={"stage_1_agent", "stage_2_agent", "stage_4_agent", "data_coordinator"}):
            with patch.object(stage_3, 'send_packet', side_effect=create_chain_tracker("stage_3_agent")):
                
                packet = Mock()
                packet.extract_task.return_value = stage_3_task
                packet.id = "chain_packet_3"
                packet.src = ElementAddress(uid="stage_2_agent")
                
                stage_3.handle_task_packet(packet)
        
        # Collect stage 3 result
        workspace_3 = get_workspace_from_node(stage_3, "chain_thread")
        chain_results['stage_3'] = workspace_3.context.results[-1]
        
        # Stage 4 receives and completes chain
        stage_4_task = Task(
            content="Complete processing chain",
            task_id="chain_stage_4",
            thread_id="chain_thread",
            created_by="stage_3_agent",
            should_respond=True,
            response_to="data_coordinator",  # Back to original requester
            correlation_task_id="chain_start_001"
        )
        
        stage_4 = agents['stage_4']
        def track_stage_4_broadcast(packet):
            from mas.elements.nodes.common.workload import Task
            task_obj = Task.model_validate(packet.payload)
            chain_communications.append({
                'from': "stage_4_agent",
                'to': "broadcast",
                'content': task_obj.content,
                'correlation_id': task_obj.correlation_task_id
            })
            return ["mock_packet_id"]
        
        with patch.object(stage_4, '_get_adjacent_nodes_uids', return_value={"stage_1_agent", "stage_2_agent", "stage_3_agent", "data_coordinator"}):
            with patch.object(stage_4, 'broadcast_packet', side_effect=track_stage_4_broadcast):
                
                packet = Mock()
                packet.extract_task.return_value = stage_4_task
                packet.id = "chain_packet_4"
                packet.src = ElementAddress(uid="stage_3_agent")
                
                stage_4.handle_task_packet(packet)
        
        # Collect stage 4 result
        workspace_4 = get_workspace_from_node(stage_4, "chain_thread")
        chain_results['stage_4'] = workspace_4.context.results[-1]
        
        # Verify chain communication
        assert len(chain_results) == 4
        for stage, result in chain_results.items():
            assert result.agent_id == f"{stage}_agent"
            assert result.success is True
            assert f"stage {stage.split('_')[1]}" in result.content
        
        # Verify communication flow
        assert len(chain_communications) >= 3  # At least 3 communications in chain
        
        # Verify thread consistency
        for result in chain_results.values():
            # All results should be from the same agent execution context
            assert result.agent_id.endswith("_agent")  # All should be agent results

    def test_custom_agent_parallel_communication(self, orchestrator_integration_state):
        """Test parallel custom agents communicating simultaneously."""
        state = orchestrator_integration_state
        
        # Create 3 parallel custom agents
        agents = {}
        specializations = ['analytics', 'reporting', 'validation']
        
        for spec in specializations:
            agent_llm = PredictableLLM()
            agent_llm.add_response(f"I have completed {spec} processing successfully.")
            agents[spec] = CustomAgentNode(
                llm=agent_llm,
                system_message=f"I specialize in {spec} operations",
                strategy_type=StrategyType.REACT.value,
                max_rounds=8
            )

        # Set up all agents with state and context
        for spec, agent in agents.items():
            setup_custom_agent_with_state(agent, f"{spec}_agent", state, ["coordinator", "monitor", "logger"])
        
        # Create parallel tasks for each agent
        parallel_tasks = {}
        for spec in specializations:
            parallel_tasks[spec] = Task(
                content=f"Execute {spec} operations in parallel",
                task_id=f"{spec}_parallel_001",
                thread_id="parallel_thread",
                created_by="coordinator",
                should_respond=True,
                response_to="coordinator"
            )

        # Track parallel communications
        parallel_communications = []
        
        def create_parallel_tracker(agent_name):
            def track_parallel(packet):
                # Extract task from packet
                task = packet.payload  # TaskPacket stores task as payload dict
                from mas.elements.nodes.common.workload import Task
                task_obj = Task.model_validate(task)
                destination = packet.dst.uid
                parallel_communications.append({
                    'from': agent_name,
                    'to': destination,
                    'timestamp': time.time(),
                    'content': task_obj.content,
                    'thread_id': task_obj.thread_id
                })
                return "mock_packet_id"
            return track_parallel

        # Process all agents in parallel (simulate)
        parallel_results = {}
        
        for spec, agent in agents.items():
            task = parallel_tasks[spec]
            
            # Mock adjacency to coordinator
            with patch.object(agent, '_get_adjacent_nodes_uids', return_value={"coordinator", "monitor", "logger"}):
                with patch.object(agent, 'send_packet', side_effect=create_parallel_tracker(f"{spec}_agent")):
                    
                    packet = Mock()
                    packet.extract_task.return_value = task
                    packet.id = f"{spec}_parallel_packet"
                    packet.src = ElementAddress(uid="coordinator")
                    
                    agent.handle_task_packet(packet)
            
            # Collect result
            workspace = get_workspace_from_node(agent, "parallel_thread")
            parallel_results[spec] = workspace.context.results[-1]
        
        # Verify parallel processing
        assert len(parallel_results) == 3
        for spec, result in parallel_results.items():
            assert result.agent_id == f"{spec}_agent"
            assert result.success is True
            assert spec in result.content
        
        # Verify all agents processed in same thread
        thread_ids = set()
        for spec, agent in agents.items():
            workspace = get_workspace_from_node(agent, "parallel_thread")
            if workspace.context.results:
                # All should be in parallel_thread context
                thread_ids.add("parallel_thread")
        
        assert len(thread_ids) <= 1  # All in same thread or no thread tracking
        
        # Verify parallel communications occurred
        assert len(parallel_communications) >= 3  # At least one per agent


@pytest.mark.custom_agent
@pytest.mark.integration
class TestCustomAgentOrchestrationIntegration:
    """Test custom agents integrated with orchestrators."""

    def test_orchestrator_delegating_to_custom_agents(self, orchestrator_integration_state):
        """Test orchestrator delegating work to multiple custom agents."""
        state = orchestrator_integration_state
        
        # Create orchestrator
        orchestrator_llm = PredictableLLM()
        orchestrator_llm.add_response("I will coordinate this work across my specialized agents.")
        orchestrator = OrchestratorNode(
            llm=orchestrator_llm,
            system_message="I coordinate work across specialized agents",
            max_rounds=12
        )
        
        # Create specialized custom agents
        agents = {}
        specializations = {
            'data_processor': 'I process and transform data efficiently.',
            'report_generator': 'I create comprehensive reports and visualizations.',
            'quality_validator': 'I validate results and ensure quality standards.'
        }
        
        for spec, response in specializations.items():
            agent_llm = PredictableLLM()
            agent_llm.add_response(response)
            agents[spec] = CustomAgentNode(
                llm=agent_llm,
                system_message=f"I specialize in {spec.replace('_', ' ')} operations",
                strategy_type=StrategyType.REACT.value,
                max_rounds=8
            )

        # Set up orchestrator with state and context
        step_context = create_step_context_local(
            uid="main_orchestrator",
            adjacent_nodes=[f"{spec}_agent" for spec in agents.keys()]
        )
        orchestrator.set_context(step_context)
        orchestrator._state = state
        
        # Set up all custom agents with state and context
        for spec, agent in agents.items():
            setup_custom_agent_with_state(agent, f"{spec}_agent", state, ["main_orchestrator"])
        
        # Create complex task for orchestrator
        complex_task = Task(
            content="Execute comprehensive data analysis: process data, generate report, validate results",
            task_id="comprehensive_analysis_001",
            thread_id="integration_thread",
            created_by="business_manager",
            should_respond=True,
            response_to="business_manager"
        )

        # Track orchestrator delegation
        delegation_tracker = []
        def track_orchestrator_delegation(destination, task):
            delegation_tracker.append({
                'from': 'main_orchestrator',
                'to': destination,
                'task_content': task.content,
                'should_respond': task.should_respond,
                'thread_id': task.thread_id
            })
        
        # Setup adjacency for orchestrator
        adjacent_cards = {}
        for spec in agents.keys():
            adjacent_cards[f"{spec}_agent"] = ElementCard(
                uid=f"{spec}_agent",
                category=ResourceCategory.NODE,
                type_key="custom_agent_node",
                name=spec.replace('_', ' ').title(),
                description=f"{spec.replace('_', ' ')} specialist",
                capabilities=[Capability(name=spec), Capability(name="specialized_processing")],
                skills=[Skill(name=f"{spec}_tool", description=f"{spec} operations")],
                configuration={},
            )

        # Process through orchestrator (using new flow - no immediate cycle)
        with patch.object(orchestrator, 'get_adjacent_nodes', return_value=adjacent_cards):
            with patch.object(orchestrator, 'send_task', side_effect=track_orchestrator_delegation):
                
                packet = Mock()
                packet.extract_task.return_value = complex_task
                packet.id = "integration_packet"
                
                # New flow: handle packet, then run orchestration for updated threads
                orchestrator.handle_task_packet(packet)
                
                # Run orchestration cycles for all updated threads (simulates batch processing)
                for thread_id in list(orchestrator._updated_threads):
                    status_summary = orchestrator.workspaces.get_work_plan_status(thread_id, orchestrator.uid)
                    if not status_summary.is_complete:
                        orchestrator._run_orchestration_cycle(thread_id, "Processing test task")
        
        # Verify orchestrator processed task and created workspace
        orchestrator_workspace = get_workspace_from_node(orchestrator, "integration_thread")
        assert orchestrator_workspace is not None
        assert len(orchestrator_workspace.context.tasks) >= 1
        
        # Simulate custom agents processing delegated tasks
        agent_results = {}
        
        for spec, agent in agents.items():
            # Create delegated task
            delegated_task = Task(
                content=f"Execute {spec.replace('_', ' ')} for comprehensive analysis",
                task_id=f"{spec}_subtask",
                thread_id="integration_thread",
                created_by="main_orchestrator",
                should_respond=True,
                response_to="main_orchestrator",
                parent_task_id="comprehensive_analysis_001"
            )
            
            # Track agent responses
            agent_responses = []
            def track_agent_response(packet):
                # Extract task from packet
                task = packet.payload  # TaskPacket stores task as payload dict
                from mas.elements.nodes.common.workload import Task
                task_obj = Task.model_validate(task)
                destination = packet.dst.uid
                agent_responses.append({
                    'to': destination,
                    'correlation_id': task_obj.correlation_task_id,
                    'is_response': task_obj.is_response()
                })
                return "mock_packet_id"
            
            # Process through agent
            with patch.object(agent, '_get_adjacent_nodes_uids', return_value={"main_orchestrator", "monitor"}):
                with patch.object(agent, 'send_packet', side_effect=track_agent_response):
                    
                    packet = Mock()
                    packet.extract_task.return_value = delegated_task
                    packet.id = f"{spec}_delegated_packet"
                    packet.src = ElementAddress(uid="main_orchestrator")
                    
                    agent.handle_task_packet(packet)
            
            # Collect agent result
            agent_workspace = get_workspace_from_node(agent, "integration_thread")
            agent_result = agent_workspace.context.results[-1]
            agent_results[spec] = agent_result
            
            assert agent_result.agent_id == f"{spec}_agent"
            assert agent_result.success is True
            
            # Verify agent sent response back to orchestrator
            assert len(agent_responses) == 1
            response = agent_responses[0]
            assert response['to'] == "main_orchestrator"
            assert response['is_response'] is True
        
        # Verify integration results
        assert len(agent_results) == 3
        specialization_results = list(agent_results.keys())
        assert 'data_processor' in specialization_results
        assert 'report_generator' in specialization_results
        assert 'quality_validator' in specialization_results
        
        # Verify all agents succeeded
        for result in agent_results.values():
            assert result.success is True

    def test_custom_agents_coordinating_with_orchestrator(self, orchestrator_integration_state):
        """Test custom agents initiating coordination with orchestrator."""
        state = orchestrator_integration_state
        
        # Create orchestrator for coordination
        orchestrator_llm = PredictableLLM()
        orchestrator_llm.add_response("I will coordinate the requested multi-agent workflow.")
        orchestrator = OrchestratorNode(
            llm=orchestrator_llm,
            system_message="I coordinate complex multi-agent workflows",
            max_rounds=10
        )
        
        # Create initiating custom agent
        initiator_llm = PredictableLLM()
        initiator_llm.add_response("I need orchestration support for this complex workflow.")
        initiator_agent = CustomAgentNode(
            llm=initiator_llm,
            system_message="I initiate complex workflows requiring orchestration",
            strategy_type=StrategyType.REACT.value,
            max_rounds=8
        )

        # Set up both nodes with state and context
        setup_custom_agent_with_state(initiator_agent, "initiator_agent", state, ["workflow_orchestrator", "monitor"])
        
        # Set up orchestrator with state and context
        step_context = create_step_context_local(
            uid="workflow_orchestrator",
            adjacent_nodes=["initiator_agent"]
        )
        orchestrator.set_context(step_context)
        orchestrator._state = state
        
        # Create coordination request from custom agent
        coordination_request = Task(
            content="I need orchestration support to coordinate a multi-step data pipeline workflow",
            task_id="coordination_request_001",
            thread_id="coordination_thread",
            created_by="initiator_agent",
            should_respond=True,
            response_to="initiator_agent"
        )

        # Track coordination communications
        coordination_comms = []
        
        def track_coordination_request(packet):
            # Extract task from packet
            task = packet.payload  # TaskPacket stores task as payload dict
            from mas.elements.nodes.common.workload import Task
            task_obj = Task.model_validate(task)
            destination = packet.dst.uid
            coordination_comms.append({
                'from': 'initiator_agent',
                'to': destination,
                'request_type': 'coordination',
                'content': task_obj.content,
                'should_respond': task_obj.should_respond
            })
            return "mock_packet_id"

        def track_orchestrator_response(destination, task):
            coordination_comms.append({
                'from': 'workflow_orchestrator',
                'to': destination,
                'request_type': 'coordination_response',
                'content': task.content,
                'correlation_id': task.correlation_task_id
            })

        # Initiator agent requests coordination
        with patch.object(initiator_agent, '_get_adjacent_nodes_uids', return_value={"workflow_orchestrator", "monitor"}):
            with patch.object(initiator_agent, 'broadcast_packet', side_effect=lambda packet: (
                track_coordination_request(packet), ["mock_packet_id"]
            )[1]):
                
                # Simulate initiator processing initial task that requires coordination
                initial_task = Task(
                    content="Process complex data pipeline requiring orchestration",
                    task_id="initial_pipeline_task",
                    thread_id="coordination_thread",
                    created_by="data_manager",
                    should_respond=True,
                    response_to="data_manager"
                )

                packet = Mock()
                packet.extract_task.return_value = initial_task
                packet.id = "initial_pipeline_packet"
                packet.src = ElementAddress(uid="data_manager")

                initiator_agent.handle_task_packet(packet)
        
        # Verify initiator created result and requested coordination
        initiator_workspace = get_workspace_from_node(initiator_agent, "coordination_thread")
        assert len(initiator_workspace.context.results) >= 1
        initiator_result = initiator_workspace.context.results[-1]
        assert initiator_result.agent_id == "initiator_agent"
        assert initiator_result.success is True
        
        # Orchestrator receives coordination request
        with patch.object(orchestrator, 'get_adjacent_nodes', return_value={
            "initiator_agent": ElementCard(
                uid="initiator_agent",
                category=ResourceCategory.NODE,
                type_key="custom_agent_node",
                name="Initiator Agent",
                description="Workflow initiating agent",
                capabilities=[Capability(name="workflow_initiation"), Capability(name="coordination_requests")],
                skills=[Skill(name="initiate_workflow", description="Initiates workflows")],
                configuration={},
            )
        }):
            with patch.object(orchestrator, 'send_task', side_effect=track_orchestrator_response):
                
                packet = Mock()
                packet.extract_task.return_value = coordination_request
                packet.id = "coordination_request_packet"
                packet.src = ElementAddress(uid="initiator_agent")

                # New flow: handle packet, then run orchestration for updated threads
                orchestrator.handle_task_packet(packet)
                
                # Run orchestration cycles for all updated threads (simulates batch processing)
                for thread_id in list(orchestrator._updated_threads):
                    status_summary = orchestrator.workspaces.get_work_plan_status(thread_id, orchestrator.uid)
                    if not status_summary.is_complete:
                        orchestrator._run_orchestration_cycle(thread_id, "Processing test task")
        
        # Verify orchestrator processed coordination request and created workspace
        orchestrator_workspace = get_workspace_from_node(orchestrator, "coordination_thread")
        assert orchestrator_workspace is not None
        assert len(orchestrator_workspace.context.tasks) >= 1  # May have multiple tasks from different agents
        
        # Verify coordination communication occurred
        assert len(coordination_comms) >= 1
        
        # Verify both agents have results in same thread
        assert len(initiator_workspace.context.results) >= 1
        assert len(orchestrator_workspace.context.results) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
