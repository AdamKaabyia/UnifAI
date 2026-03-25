"""
Simple Orchestrator Monitoring and Assertions.

Clean, SOLID utilities for verifying orchestrator behavior in integration tests.
Follows Single Responsibility Principle - just monitors and verifies.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from mas.elements.nodes.common.workload import WorkPlan, WorkItem, WorkItemStatus


# =============================================================================
# SIMPLE EXECUTION VERIFICATION (Clean & Effective)
# =============================================================================

@dataclass
class SimpleExecutionRecord:
    """Simple record of orchestration execution for verification."""
    llm_calls: int = 0
    workspace_operations: int = 0
    work_plan_created: bool = False
    errors: List[str] = None
    start_time: datetime = None
    end_time: datetime = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.start_time is None:
            self.start_time = datetime.now()
    
    def finish(self):
        """Mark execution as finished."""
        self.end_time = datetime.now()
    
    def duration_seconds(self) -> float:
        """Get execution duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def is_successful(self) -> bool:
        """Check if execution was successful."""
        return len(self.errors) == 0 and self.llm_calls > 0


class SimpleOrchestrationMonitor:
    """
    Simple monitor for orchestration testing.
    
    Follows Single Responsibility Principle - just tracks key events for verification.
    Much simpler than complex monitoring that tries to do everything.
    """
    
    def __init__(self):
        self.record = SimpleExecutionRecord()
    
    def track_llm_call(self):
        """Track an LLM call."""
        self.record.llm_calls += 1
    
    def track_workspace_operation(self):
        """Track a workspace operation."""
        self.record.workspace_operations += 1
    
    def track_work_plan_creation(self):
        """Track work plan creation."""
        self.record.work_plan_created = True
    
    def track_error(self, error: str):
        """Track an error."""
        self.record.errors.append(error)
    
    def finish_and_verify(self) -> bool:
        """Finish monitoring and return success status."""
        self.record.finish()
        return self.record.is_successful()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get simple execution summary."""
        return {
            "llm_calls": self.record.llm_calls,
            "workspace_operations": self.record.workspace_operations,
            "work_plan_created": self.record.work_plan_created,
            "errors": len(self.record.errors),
            "duration_seconds": self.record.duration_seconds(),
            "successful": self.record.is_successful()
        }


# =============================================================================
# SIMPLE ASSERTIONS (Clean & Focused)
# =============================================================================

class SimpleOrchestrationAssertions:
    """
    Simple assertions for orchestration testing.
    
    Follows Interface Segregation Principle - focused on common verification needs.
    """
    
    @staticmethod
    def assert_work_plan_created(plan: WorkPlan, expected_items: int = None):
        """Assert that a work plan was created with expected properties."""
        assert plan is not None, "Work plan should be created"
        assert plan.summary is not None, "Work plan should have a summary"
        assert len(plan.items) > 0, "Work plan should have items"
        
        if expected_items:
            assert len(plan.items) == expected_items, \
                f"Expected {expected_items} items, got {len(plan.items)}"
    
    @staticmethod
    def assert_workspace_has_data(workspace, expected_facts: List[str] = None):
        """Assert workspace contains expected data."""
        assert workspace is not None, "Workspace should exist"
        
        if expected_facts:
            for expected_fact in expected_facts:
                assert any(expected_fact in str(fact) for fact in workspace.context.facts), \
                    f"Expected fact '{expected_fact}' not found in workspace"
    
    @staticmethod
    def assert_execution_successful(monitor: SimpleOrchestrationMonitor):
        """Assert execution was successful."""
        summary = monitor.get_summary()
        assert summary["successful"], f"Execution failed: {summary}"
        assert summary["errors"] == 0, f"Execution had {summary['errors']} errors"
        assert summary["llm_calls"] > 0, "LLM should have been called"
    
    @staticmethod
    def assert_performance_acceptable(monitor: SimpleOrchestrationMonitor, max_duration: float = 1.0):
        """Assert execution performance is acceptable."""
        summary = monitor.get_summary()
        duration = summary["duration_seconds"]
        assert duration <= max_duration, \
            f"Execution took {duration:.3f}s, expected <= {max_duration}s"


# =============================================================================
# PYTEST FIXTURES (Simple)
# =============================================================================

import pytest

@pytest.fixture
def simple_orchestration_monitor():
    """Simple orchestration monitor for testing."""
    return SimpleOrchestrationMonitor()

@pytest.fixture
def orchestration_assertions():
    """Simple orchestration assertions for testing."""
    return SimpleOrchestrationAssertions()


# Clean, simple monitoring fixtures - no over-engineering needed!
