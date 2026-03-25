"""
SOLID Workload Management Usage Examples

Demonstrates the properly designed SOLID workload management system.
Shows clean separation of concerns between Thread hierarchy management
and WorkloadService persistence.
"""

from typing import Optional
from .unified_service import IWorkloadService
from .thread import Thread
from .workspace import Workspace


class SOLIDWorkloadExamples:
    """
    Examples demonstrating SOLID principles in workload management.
    
    Key SOLID Improvements:
    1. SRP: Thread manages hierarchy, Service manages persistence
    2. OCP: Easy to extend Thread behavior without changing service
    3. LSP: All threads behave consistently
    4. ISP: Focused interfaces
    5. DIP: Service depends on Thread abstraction
    """
    
    def __init__(self, service: IWorkloadService):
        self.service = service
    
    def example_1_proper_hierarchy_creation(self) -> None:
        """
        Example 1: Proper SOLID hierarchy creation.
        
        BEFORE (Violated SRP):
        service.create_thread("Parent", "obj", "user")
        service.create_thread("Child", "obj", "user", parent_id)  # Service doing hierarchy
        
        AFTER (Follows SRP):
        Thread manages hierarchy, Service manages persistence
        """
        print("=== Example 1: SOLID Hierarchy Creation ===")
        
        # ✅ SOLID Way: Service creates root threads only
        parent = self.service.create_root_thread(
            title="Research Project",
            objective="Coordinate multi-agent research",
            initiator="orchestrator_node"
        )
        print(f"Created root thread: {parent.thread_id}")
        
        # ✅ SOLID Way: Thread creates its own children  
        research_child = parent.create_child(
            title="Data Collection",
            objective="Collect research data",
            initiator="researcher_node"
        )
        
        analysis_child = parent.create_child(
            title="Data Analysis", 
            objective="Analyze collected data",
            initiator="analyst_node"
        )
        
        # ✅ SOLID Way: Service only handles persistence
        self.service.save_thread(research_child)
        self.service.save_thread(analysis_child)
        
        # Alternatively, bulk save
        # self.service.save_threads([research_child, analysis_child])
        
        print(f"Parent has {parent.get_child_count()} children")
        print(f"Research child parent: {research_child.parent_thread_id}")
        print(f"Analysis child parent: {analysis_child.parent_thread_id}")
    
    def example_2_thread_lifecycle_management(self) -> None:
        """
        Example 2: Thread manages its own lifecycle.
        
        BEFORE (Violated SRP):
        service.complete_thread(thread_id)  # Service doing lifecycle
        
        AFTER (Follows SRP):
        Thread manages lifecycle, Service persists changes
        """
        print("\n=== Example 2: SOLID Lifecycle Management ===")
        
        # Create a thread
        thread = self.service.create_root_thread(
            title="Task Processing",
            objective="Process user task",
            initiator="processor_node"
        )
        
        # ✅ SOLID Way: Thread manages its own lifecycle
        thread.add_participant("helper_node")
        print(f"Thread status: {thread.status}")
        print(f"Participants: {thread.participants}")
        
        # Process some work...
        print("Processing work...")
        
        # Thread completes itself
        thread.complete()
        print(f"Thread status after completion: {thread.status}")
        
        # ✅ SOLID Way: Service only persists the changes
        self.service.save_thread(thread)
        print("Changes persisted to storage")
    
    def example_3_hierarchy_validation(self) -> None:
        """
        Example 3: Thread validates its own hierarchy.
        
        Demonstrates built-in validation preventing:
        - Self-adoption
        - Circular dependencies  
        - Double adoption
        """
        print("\n=== Example 3: SOLID Hierarchy Validation ===")
        
        # Create threads
        parent = self.service.create_root_thread("Parent", "Parent task", "user1")
        independent = self.service.create_root_thread("Independent", "Independent task", "user2")
        
        # ✅ SOLID Way: Thread validates adoption
        try:
            # This should work fine
            child = parent.create_child("Valid Child", "Child task", "user3")
            print(f"✅ Valid child creation: {child.thread_id}")
            
            # This should fail - self adoption
            parent.adopt_child(parent)
            
        except ValueError as e:
            print(f"✅ Validation caught invalid operation: {e}")
        
        try:
            # Try to adopt a thread that's already someone's child
            existing_child = parent.create_child("Existing Child", "Task", "user")
            independent.adopt_child(existing_child)  # Should fail
            
        except ValueError as e:
            print(f"✅ Validation caught double adoption: {e}")
    
    def example_4_workspace_integration(self) -> None:
        """
        Example 4: Clean workspace integration.
        
        Shows how workspace management integrates cleanly
        with the SOLID thread design.
        """
        print("\n=== Example 4: SOLID Workspace Integration ===")
        
        # Create thread hierarchy
        main_thread = self.service.create_root_thread(
            "Data Pipeline",
            "Process data through multiple stages", 
            "pipeline_orchestrator"
        )
        
        extract_thread = main_thread.create_child(
            "Data Extraction", 
            "Extract data from sources",
            "extractor_node"
        )
        
        transform_thread = main_thread.create_child(
            "Data Transformation",
            "Transform extracted data", 
            "transformer_node"
        )
        
        # Save the hierarchy
        self.service.save_threads([extract_thread, transform_thread])
        
        # Get workspaces for each thread
        main_workspace = self.service.get_workspace(main_thread.thread_id)
        extract_workspace = self.service.get_workspace(extract_thread.thread_id)
        
        # Each thread has its own workspace context
        self.service.add_fact(main_thread.thread_id, "Pipeline started")
        self.service.add_fact(extract_thread.thread_id, "Extraction in progress")
        
        # Workspaces are isolated but can be coordinated
        main_context = self.service.get_context(main_thread.thread_id)
        extract_context = self.service.get_context(extract_thread.thread_id)
        
        print(f"Main thread workspace facts: {len(main_context['workspace']['facts'])}")
        print(f"Extract thread workspace facts: {len(extract_context['workspace']['facts'])}")
    
    def example_5_advanced_hierarchy_patterns(self) -> None:
        """
        Example 5: Advanced hierarchy patterns.
        
        Shows complex but clean hierarchy management patterns
        that are easy to implement with SOLID design.
        """
        print("\n=== Example 5: Advanced SOLID Hierarchy Patterns ===")
        
        # Create a complex project hierarchy
        project = self.service.create_root_thread(
            "ML Model Development",
            "Develop and deploy ML model",
            "project_manager"
        )
        
        # Phase 1: Research
        research_phase = project.create_child(
            "Research Phase",
            "Research problem and solutions", 
            "researcher"
        )
        
        literature_review = research_phase.create_child(
            "Literature Review",
            "Review existing solutions",
            "researcher"
        )
        
        problem_analysis = research_phase.create_child(
            "Problem Analysis", 
            "Analyze problem requirements",
            "analyst"
        )
        
        # Phase 2: Development  
        dev_phase = project.create_child(
            "Development Phase",
            "Implement the solution",
            "developer"
        )
        
        model_training = dev_phase.create_child(
            "Model Training",
            "Train ML models",
            "ml_engineer"
        )
        
        # ✅ SOLID Way: Bulk save entire hierarchy
        all_threads = [
            research_phase, literature_review, problem_analysis,
            dev_phase, model_training
        ]
        self.service.save_threads(all_threads)
        
        # Demonstrate hierarchy traversal
        print(f"Project has {project.get_child_count()} main phases")
        print(f"Research phase has {research_phase.get_child_count()} sub-tasks")
        print(f"Development phase has {dev_phase.get_child_count()} sub-tasks")
        
        # Demonstrate hierarchy queries
        research_threads = self.service.get_threads_by_parent(research_phase.thread_id)
        print(f"Research sub-threads: {[t.title for t in research_threads]}")
        
        root_threads = self.service.get_threads_by_parent(None)
        print(f"Root threads: {[t.title for t in root_threads]}")
    
    def example_6_service_abstraction_benefits(self) -> None:
        """
        Example 6: Service abstraction benefits.
        
        Shows how the IWorkloadService abstraction enables
        dependency injection, testing, and multiple implementations.
        """
        print("\n=== Example 6: Service Abstraction Benefits ===")
        
        # ✅ SOLID Way: Code depends on abstraction (IWorkloadService)
        # This same code works with ANY implementation:
        # - InMemoryWorkloadService  
        # - StateBoundWorkloadService
        # - DatabaseWorkloadService (future)
        # - RedisWorkloadService (future)
        
        thread = self.service.create_root_thread(
            "Service Agnostic Task",
            "This works with any service implementation",
            "agnostic_node"
        )
        
        # Create hierarchy
        subtask1 = thread.create_child("Subtask 1", "First subtask", "worker1")
        subtask2 = thread.create_child("Subtask 2", "Second subtask", "worker2")
        
        # Save using abstraction
        self.service.save_threads([subtask1, subtask2])
        
        # Lifecycle management
        subtask1.complete()
        subtask2.fail()
        
        # Persist changes
        self.service.save_threads([subtask1, subtask2])
        
        # Query using abstraction
        completed_threads = [
            t for t in self.service.list_threads()
            if t.is_completed()
        ]
        
        failed_threads = [
            t for t in self.service.list_threads() 
            if t.status.value == "failed"
        ]
        
        print(f"Completed threads: {len(completed_threads)}")
        print(f"Failed threads: {len(failed_threads)}")
        print("✅ Same code works with ANY service implementation!")
    
    def example_7_convenience_methods(self) -> None:
        """
        Example 7: Convenience methods for common patterns.
        
        Shows how convenience methods can simplify common operations
        while maintaining SOLID principles.
        """
        print("\n=== Example 7: Convenience Methods ===")
        
        # Create a thread
        thread = self.service.create_root_thread(
            "Convenience Example",
            "Demonstrate convenience methods",
            "user"
        )
        
        # ✅ SOLID Way: Use convenience method for common pattern
        # This is equivalent to: get_thread() -> modify -> save_thread()
        modified_thread = self.service.modify_thread(
            thread.thread_id,
            lambda t: t.add_participant("helper_node")
        )
        
        if modified_thread:
            print(f"Added participant via convenience method")
            print(f"Participants: {modified_thread.participants}")
        
        # Another convenience example
        completed_thread = self.service.modify_thread(
            thread.thread_id,
            lambda t: t.complete()
        )
        
        if completed_thread:
            print(f"Thread completed via convenience method: {completed_thread.status}")


def demonstrate_solid_benefits():
    """
    Show the key benefits of the SOLID redesign.
    """
    print("🎯 SOLID Workload Management Benefits:")
    print("=" * 50)
    print("✅ Single Responsibility Principle:")
    print("   - Thread: Manages hierarchy and lifecycle")
    print("   - WorkloadService: Manages persistence only")
    print()
    print("✅ Open/Closed Principle:")
    print("   - Easy to extend Thread behavior")
    print("   - Easy to add new service implementations")
    print()
    print("✅ Liskov Substitution Principle:")
    print("   - All threads behave consistently")
    print("   - All services are interchangeable")
    print()
    print("✅ Interface Segregation Principle:")
    print("   - Focused IWorkloadService interface")
    print("   - No forced dependencies")
    print()
    print("✅ Dependency Inversion Principle:")
    print("   - Code depends on IWorkloadService abstraction")
    print("   - Easy dependency injection and testing")
    print()
    print("🚀 Result: Clean, maintainable, extensible code!")


if __name__ == "__main__":
    # This would work with any IWorkloadService implementation
    print("This example would work with any IWorkloadService implementation")
    print("(InMemoryWorkloadService, StateBoundWorkloadService, etc.)")
    demonstrate_solid_benefits()