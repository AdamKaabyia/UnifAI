"""
Clean Workload Management Usage Examples

Shows the simplified, elegant SOLID patterns for real-world usage.
Demonstrates how the system is actually used in practice.
"""

from mas.elements.nodes.common.base_node import BaseNode
from mas.elements.nodes.common.capabilities.iem_capable import IEMCapableMixin
from mas.elements.nodes.common.capabilities.workload_capable import WorkloadCapableMixin
from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import Channel
from typing import ClassVar
from .unified_service import IWorkloadService
from .storage import InMemoryStorage
from .task import Task


class SimpleWorkloadExample(WorkloadCapableMixin, IEMCapableMixin, BaseNode):
    """
    Real-world example: How nodes actually use workload management.
    
    Clean, simple patterns that developers will actually use.
    """
    
    READS: ClassVar[set[str]] = {Channel.USER_PROMPT}
    WRITES: ClassVar[set[str]] = {Channel.MESSAGES}
    
    def run(self, state: StateView) -> StateView:
        """Show real usage patterns."""
        prompt = state.get(Channel.USER_PROMPT, "")
        if not prompt.strip():
            return state
        
        # Example 1: Simple thread creation
        self._simple_thread_example()
        
        # Example 2: Hierarchical workflow
        self._hierarchical_workflow_example()
        
        # Example 3: Collaborative workspace
        self._collaborative_workspace_example()
        
        return state
    
    def _simple_thread_example(self) -> None:
        """How to create and use a simple thread."""
        print("=== Simple Thread Usage ===")
        
        # ✅ Clean: Create thread
        thread = self.create_thread("Data Processing", "Process user data")
        print(f"Created: {thread.title}")
        
        # ✅ Clean: Add some context
        self.add_fact_to_workspace(thread.thread_id, "Processing started")
        self.set_workspace_variable(thread.thread_id, "status", "active")
        
        # ✅ Clean: Add result  
        self.add_result_to_workspace(thread.thread_id, "Data processed successfully")
        
        # ✅ Clean: Thread manages itself
        thread.add_participant("helper_agent")
        thread.complete()
        self.save_thread(thread)
        
        print(f"Status: {thread.status}, Participants: {thread.participants}")
    
    def _hierarchical_workflow_example(self) -> None:
        """How to create hierarchical workflows."""
        print("\n=== Hierarchical Workflow ===")
        
        # ✅ Clean: Create main thread
        project = self.create_thread("ML Pipeline", "Build ML model pipeline")
        
        # ✅ Clean: Create child threads  
        data_prep = self.create_child_thread(project, "Data Prep", "Prepare training data")
        training = self.create_child_thread(project, "Model Training", "Train the model")
        deployment = self.create_child_thread(project, "Deployment", "Deploy to production")
        
        print(f"Project: {project.title}")
        print(f"  Child 1: {data_prep.title}")
        print(f"  Child 2: {training.title}")  
        print(f"  Child 3: {deployment.title}")
        print(f"Project has {project.get_child_count()} children")
        
        # ✅ Clean: Work with workspaces
        self.add_fact_to_workspace(data_prep.thread_id, "Data cleaned and validated")
        self.add_fact_to_workspace(training.thread_id, "Model trained with 95% accuracy")
        self.add_artifact_to_workspace(
            deployment.thread_id, 
            "model.pkl", 
            "model_file", 
            "/models/model.pkl"
        )
        
        # ✅ Clean: Lifecycle management
        data_prep.complete()
        training.complete()
        deployment.complete()
        
        # Save all changes
        self.save_thread(data_prep)
        self.save_thread(training)
        self.save_thread(deployment)
        
        print("All phases completed!")
    
    def _collaborative_workspace_example(self) -> None:
        """How multiple agents collaborate through workspace."""
        print("\n=== Collaborative Workspace ===")
        
        # ✅ Clean: Create shared thread
        collaboration = self.create_thread("Team Project", "Multi-agent collaboration")
        
        # ✅ Clean: Multiple agents join
        collaboration.add_participant("researcher_agent")
        collaboration.add_participant("analyst_agent") 
        collaboration.add_participant("writer_agent")
        
        # ✅ Clean: Each agent adds their context
        self.add_fact_to_workspace(collaboration.thread_id, "Research completed by researcher_agent")
        self.add_fact_to_workspace(collaboration.thread_id, "Analysis done by analyst_agent")
        self.add_fact_to_workspace(collaboration.thread_id, "Report written by writer_agent")
        
        # ✅ Clean: Shared variables
        self.set_workspace_variable(collaboration.thread_id, "project_status", "in_progress")
        self.set_workspace_variable(collaboration.thread_id, "deadline", "2024-02-01")
        self.set_workspace_variable(collaboration.thread_id, "budget", 10000)
        
        # ✅ Clean: Shared artifacts
        artifacts = [
            ("research_data.json", "data", "/data/research.json"),
            ("analysis_report.pdf", "report", "/reports/analysis.pdf"),
            ("final_document.docx", "document", "/docs/final.docx")
        ]
        
        for name, type_, location in artifacts:
            self.add_artifact_to_workspace(collaboration.thread_id, name, type_, location)
        
        self.save_thread(collaboration)
        
        # ✅ Clean: Get full context
        context = self.get_thread_context(collaboration.thread_id)
        workspace_data = context.get('workspace', {})
        print(f"Participants: {len(collaboration.participants)}")
        print(f"Facts: {len(workspace_data.get('facts', []))}")
        print(f"Variables: {len(workspace_data.get('variables', {}))}")
        print(f"Artifacts: {len(workspace_data.get('artifacts', {}))}")


class TaskIntegrationExample(WorkloadCapableMixin, IEMCapableMixin, BaseNode):
    """
    Real-world example: How workload integrates with existing Task system.
    """
    
    READS: ClassVar[set[str]] = {Channel.TASK_THREADS}
    WRITES: ClassVar[set[str]] = {Channel.TASK_THREADS, Channel.MESSAGES}
    
    def run(self, state: StateView) -> StateView:
        """Process task packets with workload integration."""
        self.process_packets(state)
        return state
    
    def handle_task_packet(self, packet) -> None:
        """Enhanced task handling with workload management."""
        task = packet.extract_task()
        
        # ✅ Clean: Get or create thread for this task
        if task.thread_id:
            thread = self.get_thread(task.thread_id)
            if not thread:
                # Create thread if it doesn't exist
                thread = self.create_thread(f"Task {task.task_id[:8]}", "Process task")
                task.thread_id = thread.thread_id
        else:
            # Create new thread for orphaned task
            thread = self.create_thread(f"Task {task.task_id[:8]}", "Process task")
            task.thread_id = thread.thread_id
        
        # ✅ Clean: Join thread as participant
        thread.add_participant(self.uid)
        
        # ✅ Clean: Add task context to workspace
        self.add_fact_to_workspace(thread.thread_id, f"Processing task: {task.content}")
        self.set_workspace_variable(thread.thread_id, "task_id", task.task_id)
        self.set_workspace_variable(thread.thread_id, "processor", self.uid)
        
        # ✅ Clean: Process the task (simplified)
        result_content = f"Processed: {task.content}"
        
        # ✅ Clean: Add result to workspace
        self.add_result_to_workspace(
            thread.thread_id,
            content=result_content,
            metrics={"processing_time": 0.1}
        )
        
        # ✅ Clean: Save changes
        self.save_thread(thread)
        
        # ✅ Clean: Handle response based on task pattern
        if task.should_respond:
            response_task = Task.respond_success(
                original_task=task,
                result={"content": result_content, "thread_id": thread.thread_id},
                processed_by=self.uid
            )
            self.reply_task(packet, response_task)
        else:
            forked_task = task.fork(
                content=result_content,
                processed_by=self.uid,
                data={"thread_id": thread.thread_id}
            )
            self.broadcast_task(forked_task)


class DirectServiceExample:
    """
    Example using service directly (for testing, special cases, etc.)
    """
    
    def __init__(self, service: IWorkloadService):
        self.service = service
    
    def example_direct_usage(self) -> None:
        """How to use service directly when needed."""
        print("=== Direct Service Usage ===")
        
        # ✅ Clean: Create thread
        thread = self.service.create_thread("Direct Task", "Direct service usage", "test_node")
        
        # ✅ Clean: Create hierarchy
        subtask1 = thread.create_child("Subtask 1", "First part", "worker1")
        subtask2 = thread.create_child("Subtask 2", "Second part", "worker2")
        
        # ✅ Clean: Save hierarchy
        self.service.save_thread(subtask1)
        self.service.save_thread(subtask2)
        
        # ✅ Clean: Work with threads
        subtask1.add_participant("helper")
        subtask1.complete()
        
        subtask2.add_participant("reviewer")
        subtask2.fail()
        
        # ✅ Clean: Save changes
        self.service.save_thread(subtask1)
        self.service.save_thread(subtask2)
        
        # ✅ Clean: Query threads
        all_threads = self.service.list_threads()
        active_threads = self.service.list_active_threads()
        child_threads = self.service.get_threads_by_parent(thread.thread_id)
        
        print(f"Total threads: {len(all_threads)}")
        print(f"Active threads: {len(active_threads)}")
        print(f"Child threads: {len(child_threads)}")
        
        # ✅ Clean: Get statistics
        stats = self.service.get_statistics()
        print(f"Statistics: {stats}")


def practical_usage_patterns():
    """
    Show practical patterns developers will actually use.
    """
    print("🎯 Practical Workload Management Patterns")
    print("=" * 50)
    
    # Pattern 1: Simple thread creation
    print("✅ Pattern 1: Simple Thread")
    print("thread = self.create_thread('Title', 'Objective')")
    print("self.add_fact_to_workspace(thread.thread_id, 'Fact')")
    print("thread.complete()")
    print("self.save_thread(thread)")
    print()
    
    # Pattern 2: Hierarchical workflow
    print("✅ Pattern 2: Hierarchical Workflow")
    print("parent = self.create_thread('Project', 'Main objective')")
    print("child = self.create_child_thread(parent, 'Phase 1', 'Sub-objective')")
    print("child.complete()")
    print("self.save_thread(child)")
    print()
    
    # Pattern 3: Collaborative workspace
    print("✅ Pattern 3: Collaborative Workspace")
    print("thread = self.create_thread('Team Work', 'Collaborate')")
    print("thread.add_participant('agent_2')")
    print("self.add_fact_to_workspace(thread.thread_id, 'Shared fact')")
    print("self.save_thread(thread)")
    print()
    
    # Pattern 4: Task integration
    print("✅ Pattern 4: Task Integration")
    print("# In handle_task_packet():")
    print("thread = self.create_thread(f'Task {task.task_id}', 'Process task')")
    print("task.thread_id = thread.thread_id")
    print("self.add_result_to_workspace(thread.thread_id, result)")
    print()
    
    # Pattern 5: Service abstraction
    print("✅ Pattern 5: Service Abstraction")
    print("service: IWorkloadService = InMemoryWorkloadService()")
    print("thread = service.create_thread('Title', 'Objective', 'initiator')")
    print("child = thread.create_child('Child', 'Sub-objective', 'worker')")
    print("service.save_thread(child)")
    print()
    
    print("🚀 Result: Clean, intuitive, SOLID patterns!")


if __name__ == "__main__":
    practical_usage_patterns()
    
    # Example with direct service
    service = InMemoryWorkloadService()
    example = DirectServiceExample(service)
    example.example_direct_usage()