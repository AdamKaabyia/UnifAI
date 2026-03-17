"""
Conversation History Usage Examples

Shows how to use the new conversation_history feature in workspaces
for managing and sharing conversation context between agents.
"""

from mas.elements.nodes.common.base_node import BaseNode
from mas.elements.nodes.common.capabilities.iem_capable import IEMCapableMixin
from mas.elements.nodes.common.capabilities.workload_capable import WorkloadCapableMixin
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import Channel
from typing import ClassVar


class ConversationHistoryExample(WorkloadCapableMixin, IEMCapableMixin, BaseNode):
    """
    Example showing conversation history management in workspaces.
    
    Demonstrates:
    1. Adding messages to workspace conversation history
    2. Copying messages from GraphState
    3. Syncing incremental updates
    4. Querying conversation data
    """
    
    READS: ClassVar[set[str]] = {Channel.USER_PROMPT, Channel.MESSAGES}
    WRITES: ClassVar[set[str]] = {Channel.MESSAGES}
    
    def run(self, state: StateView) -> StateView:
        """Show conversation history usage patterns."""
        prompt = state.get(Channel.USER_PROMPT, "")
        if not prompt.strip():
            return state
        
        # Example 1: Basic conversation history usage
        self._basic_conversation_example()
        
        # Example 2: Copying from GraphState
        self._graphstate_copy_example(state)
        
        # Example 3: Multi-agent conversation sharing
        self._multi_agent_sharing_example()
        
        # Example 4: Conversation analysis
        self._conversation_analysis_example()
        
        return state
    
    def _basic_conversation_example(self) -> None:
        """Example 1: Basic conversation history management."""
        print("=== Basic Conversation History ===")
        
        # Create thread
        thread = self.create_thread("Customer Support", "Handle customer inquiry")
        
        # Add conversation messages manually
        messages = [
            ChatMessage(role=Role.USER, content="I need help with my order"),
            ChatMessage(role=Role.ASSISTANT, content="I'd be happy to help! What's your order number?"),
            ChatMessage(role=Role.USER, content="Order #12345"),
            ChatMessage(role=Role.ASSISTANT, content="Let me look that up for you...")
        ]
        
        # ✅ Add messages to workspace conversation history
        self.add_messages_to_workspace(thread.thread_id, messages)
        
        # Get conversation summary
        summary = self.get_workspace_conversation_summary(thread.thread_id)
        print(f"Conversation: {summary['message_count']} messages")
        print(f"Participants: {summary['participants']}")
        print(f"Latest: {summary['latest_message']['content_preview']}")
    
    def _graphstate_copy_example(self, state: StateView) -> None:
        """Example 2: Copying messages from GraphState."""
        print("\n=== GraphState Message Copying ===")
        
        # Add some messages to GraphState for demo
        demo_messages = [
            ChatMessage(role=Role.USER, content="Hello, I need assistance"),
            ChatMessage(role=Role.ASSISTANT, content="Hello! How can I help you today?"),
            ChatMessage(role=Role.USER, content="I'm having trouble with my account")
        ]
        
        # Add to GraphState
        current_messages = list(state.get(Channel.MESSAGES, []))
        current_messages.extend(demo_messages)
        state[Channel.MESSAGES] = current_messages
        
        # Create thread for this conversation
        thread = self.create_thread("Account Support", "Help with account issues")
        
        # ✅ Copy all messages from GraphState to workspace using NEW SOLID API
        self.copy_graphstate_messages_to_workspace(thread.thread_id)
        
        # Verify the copy
        workspace_summary = self.get_workspace_conversation_summary(thread.thread_id)
        print(f"Copied {workspace_summary['message_count']} messages from GraphState")
        
        # Add more messages to GraphState (simulating ongoing conversation)
        new_messages = [
            ChatMessage(role=Role.ASSISTANT, content="I can help with account issues. What specifically is the problem?"),
            ChatMessage(role=Role.USER, content="I can't log in to my account")
        ]
        current_messages.extend(new_messages)
        state[Channel.MESSAGES] = current_messages
        
        # ✅ Sync only new messages (example - could use "conversation" strategy)
        self.copy_graphstate_messages_to_workspace(thread.thread_id, strategy="conversation")
        
        # Check updated summary
        updated_summary = self.get_workspace_conversation_summary(thread.thread_id)
        print(f"After sync: {updated_summary['message_count']} total messages")
        print(f"Latest: {updated_summary['latest_message']['content_preview']}")
    
    def _multi_agent_sharing_example(self) -> None:
        """Example 3: Multi-agent conversation sharing."""
        print("\n=== Multi-Agent Conversation Sharing ===")
        
        # Create shared thread for team collaboration
        team_thread = self.create_thread("Team Collaboration", "Multi-agent problem solving")
        
        # Agent 1 (this agent) starts conversation
        agent1_messages = [
            ChatMessage(role=Role.USER, content="We need to analyze this customer issue"),
            ChatMessage(role=Role.ASSISTANT, content="I'll start by gathering the basic information")
        ]
        self.add_messages_to_workspace(team_thread.thread_id, agent1_messages)
        
        # Simulate Agent 2 joining and adding their perspective
        agent2_messages = [
            ChatMessage(role=Role.ASSISTANT, content="I can provide technical analysis of the issue"),
            ChatMessage(role=Role.ASSISTANT, content="Looking at the logs, I see the problem occurred at 14:30 UTC")
        ]
        self.add_messages_to_workspace(team_thread.thread_id, agent2_messages)
        
        # Simulate Agent 3 adding resolution
        agent3_messages = [
            ChatMessage(role=Role.ASSISTANT, content="Based on the analysis, I recommend the following solution..."),
            ChatMessage(role=Role.ASSISTANT, content="I've implemented the fix and tested it successfully")
        ]
        self.add_messages_to_workspace(team_thread.thread_id, agent3_messages)
        
        # ✅ Any agent can now access the full conversation context
        full_conversation = self.get_recent_workspace_messages(team_thread.thread_id, 20)
        conversation_summary = self.get_workspace_conversation_summary(team_thread.thread_id)
        
        print(f"Team conversation: {len(full_conversation)} messages")
        print(f"Summary: {conversation_summary}")
        
        # ✅ Add this shared context as facts for easy reference
        self.add_fact_to_workspace(team_thread.thread_id, "Multi-agent collaboration completed")
        self.add_fact_to_workspace(team_thread.thread_id, f"Conversation included {len(full_conversation)} exchanges")
    
    def _conversation_analysis_example(self) -> None:
        """Example 4: Conversation analysis and insights."""
        print("\n=== Conversation Analysis ===")
        
        # Create thread with complex conversation
        analysis_thread = self.create_thread("Conversation Analysis", "Analyze customer interaction")
        
        # Create a realistic customer service conversation
        conversation = [
            ChatMessage(role=Role.USER, content="Hi, I'm having issues with my recent order"),
            ChatMessage(role=Role.ASSISTANT, content="I'm sorry to hear that. Can you tell me more about the issue?"),
            ChatMessage(role=Role.USER, content="The item I received is damaged"),
            ChatMessage(role=Role.ASSISTANT, content="I understand how frustrating that must be. Let me help you with a replacement."),
            ChatMessage(role=Role.USER, content="How long will the replacement take?"),
            ChatMessage(role=Role.ASSISTANT, content="We can expedite a replacement within 2-3 business days."),
            ChatMessage(role=Role.USER, content="That sounds good, thank you"),
            ChatMessage(role=Role.ASSISTANT, content="You're welcome! I've initiated the replacement order.")
        ]
        
        self.add_messages_to_workspace(analysis_thread.thread_id, conversation)
        
        # ✅ Analyze the conversation
        workspace = self.get_workspace(analysis_thread.thread_id)
        
        # Get conversation insights
        summary = workspace.get_conversation_summary()
        user_messages = workspace.get_messages_by_role(Role.USER)
        assistant_messages = workspace.get_messages_by_role(Role.ASSISTANT)
        recent_messages = workspace.get_recent_messages(3)
        
        print(f"Conversation Analysis:")
        print(f"  Total messages: {summary['message_count']}")
        print(f"  User messages: {len(user_messages)}")
        print(f"  Assistant messages: {len(assistant_messages)}")
        print(f"  Participants: {summary['participants']}")
        
        # Analyze conversation sentiment/outcome
        user_concerns = [msg.content for msg in user_messages]
        resolution_provided = any("replacement" in msg.content.lower() for msg in assistant_messages)
        
        print(f"  User concerns: {user_concerns}")
        print(f"  Resolution provided: {resolution_provided}")
        
        # ✅ Store analysis results
        self.add_fact_to_workspace(analysis_thread.thread_id, "Customer issue: damaged item")
        self.add_fact_to_workspace(analysis_thread.thread_id, "Resolution: replacement offered")
        self.add_fact_to_workspace(analysis_thread.thread_id, "Customer satisfaction: positive outcome")
        
        self.set_workspace_variable(analysis_thread.thread_id, "conversation_length", len(conversation))
        self.set_workspace_variable(analysis_thread.thread_id, "resolution_time", "immediate")
        self.set_workspace_variable(analysis_thread.thread_id, "customer_sentiment", "satisfied")


class ConversationMigrationExample(WorkloadCapableMixin, IEMCapableMixin, BaseNode):
    """
    Example showing how to migrate from task_threads to workspace conversation_history.
    
    Shows backward compatibility and migration patterns.
    """
    
    READS: ClassVar[set[str]] = {Channel.TASK_THREADS, Channel.MESSAGES}
    WRITES: ClassVar[set[str]] = {Channel.MESSAGES}
    
    def migrate_task_threads_to_workspace(self, thread_id: str) -> None:
        """
        Migrate existing task_threads data to workspace conversation_history.
        
        This helps transition from the old task_threads system to the new
        workspace conversation_history system.
        """
        print("=== Migrating task_threads to workspace ===")
        
        state = self.get_state()
        task_threads = state.get(Channel.TASK_THREADS, {})
        
        if thread_id in task_threads:
            # Get messages from task_threads
            task_messages = task_threads[thread_id]
            
            # ✅ Copy to workspace conversation history
            if task_messages:
                self.add_messages_to_workspace(thread_id, task_messages)
                print(f"Migrated {len(task_messages)} messages from task_threads to workspace")
            
            # Optional: Clear old task_threads data
            # del task_threads[thread_id]
            # state[Channel.TASK_THREADS] = task_threads
        
        # Verify migration
        summary = self.get_workspace_conversation_summary(thread_id)
        print(f"Workspace now contains: {summary['message_count']} messages")


def practical_conversation_patterns():
    """
    Show practical patterns for conversation history management.
    """
    print("🎯 Practical Conversation History Patterns")
    print("=" * 50)
    
    # Pattern 1: Copy from GraphState (NEW SOLID API)
    print("✅ Pattern 1: Copy GraphState Messages")
    print("self.copy_graphstate_messages_to_workspace(thread_id)")
    print("# Uses NEW SOLID WorkspaceService - clean, testable, SOLID")
    print()
    
    # Pattern 2: Strategy-based sync
    print("✅ Pattern 2: Strategy-based Sync")
    print("self.copy_graphstate_messages_to_workspace(thread_id)  # Default: 'conversation'")
    print("self.copy_graphstate_messages_to_workspace(thread_id, strategy='facts')  # For LLM context")
    print("# NEW: 'conversation' default, 'facts' for LLM context, 'both' for flexibility")
    print()
    
    # Pattern 3: Manual message addition
    print("✅ Pattern 3: Manual Message Addition")
    print("message = ChatMessage(role=Role.USER, content='Hello')")
    print("self.add_message_to_workspace(thread_id, message)")
    print()
    
    # Pattern 4: Batch addition
    print("✅ Pattern 4: Batch Message Addition")
    print("messages = [msg1, msg2, msg3]")
    print("self.add_messages_to_workspace(thread_id, messages)")
    print()
    
    # Pattern 5: Conversation analysis
    print("✅ Pattern 5: Conversation Analysis")
    print("summary = self.get_workspace_conversation_summary(thread_id)")
    print("recent = self.get_recent_workspace_messages(thread_id, 5)")
    print("workspace = self.get_workspace(thread_id)")
    print("user_msgs = workspace.get_messages_by_role(Role.USER)")
    print()
    
    print("🚀 Result: Rich conversation context management!")


if __name__ == "__main__":
    practical_conversation_patterns()