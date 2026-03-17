"""
Fixtures for GraphState and StateView.

Provides fixtures for creating and configuring state objects for testing.
"""

import pytest
from mas.graph.state.graph_state import GraphState, Channel
from mas.graph.state.state_view import StateView


@pytest.fixture
def graph_state():
    """
    Create a basic GraphState for testing.
    
    Returns:
        GraphState instance with standard channels initialized
    """
    state = GraphState()
    
    # Initialize all standard channels
    state.user_prompt = ''
    state.nodes_output = {}
    state.messages = []
    state.output = ''
    state.target_branch = ''
    state.inter_packets = []
    state.task_threads = {}
    state.threads = {}
    state.workspaces = {}
    
    return state


@pytest.fixture
def state_view(graph_state):
    """
    Create a StateView with comprehensive channel access for testing.
    
    Args:
        graph_state: GraphState fixture
        
    Returns:
        StateView instance with full read/write access
    """
    # Provide access to all standard channels for maximum test flexibility
    reads = {
        Channel.USER_PROMPT,     # User input
        Channel.MESSAGES,        # Public conversation
        Channel.NODES_OUTPUT,    # Node outputs
        Channel.OUTPUT,          # Final output
        Channel.TARGET_BRANCH,   # Branch targeting
        Channel.INTER_PACKETS,   # IEM packets
        Channel.TASK_THREADS,    # Task conversation threads
        Channel.THREADS,         # Thread metadata
        Channel.WORKSPACES       # Workspace data
    }
    writes = {
        Channel.USER_PROMPT,     # User input
        Channel.MESSAGES,        # Public conversation
        Channel.NODES_OUTPUT,    # Node outputs
        Channel.OUTPUT,          # Final output
        Channel.TARGET_BRANCH,   # Branch targeting
        Channel.INTER_PACKETS,   # IEM packets
        Channel.TASK_THREADS,    # Task conversation threads
        Channel.THREADS,         # Thread metadata
        Channel.WORKSPACES       # Workspace data
    }
    
    return StateView(graph_state, reads=reads, writes=writes)


@pytest.fixture
def readonly_state_view(graph_state):
    """
    Create a read-only StateView for testing read-only operations.
    
    Args:
        graph_state: GraphState fixture
        
    Returns:
        StateView instance with read-only access
    """
    reads = {
        Channel.USER_PROMPT,
        Channel.MESSAGES,
        Channel.NODES_OUTPUT,
        Channel.OUTPUT,
        Channel.INTER_PACKETS,
        Channel.TASK_THREADS,
        Channel.THREADS,
        Channel.WORKSPACES
    }
    
    return StateView(graph_state, reads=reads, writes=set())
