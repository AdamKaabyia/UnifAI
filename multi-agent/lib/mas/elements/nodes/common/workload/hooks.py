"""
WorkPlan lifecycle hooks.

SOLID Design: Following tool execution hook pattern.
Hooks allow extension without modifying WorkPlanService.
"""

from typing import Optional
from abc import ABC, abstractmethod
from enum import Enum
from .models import WorkPlan


class WorkPlanHookPoint(str, Enum):
    """Lifecycle points where hooks are triggered."""
    POST_SAVE = "on_post_save"
    POST_LOAD = "on_post_load"
    POST_DELETE = "on_post_delete"


class WorkPlanHook(ABC):
    """Base interface for workplan hooks."""
    
    @abstractmethod
    def on_post_save(self, plan: WorkPlan, context: dict) -> None:
        """Called after plan is saved successfully."""
        pass
    
    @abstractmethod
    def on_post_load(self, plan: Optional[WorkPlan], context: dict) -> None:
        """Called after plan is loaded (None if not found)."""
        pass
    
    @abstractmethod
    def on_post_delete(self, context: dict) -> None:
        """Called after plan is deleted."""
        pass


class BaseWorkPlanHook(WorkPlanHook):
    """Base implementation with no-op methods. Inherit and override what you need."""
    
    def on_post_save(self, plan: WorkPlan, context: dict) -> None:
        pass
    
    def on_post_load(self, plan: Optional[WorkPlan], context: dict) -> None:
        pass
    
    def on_post_delete(self, context: dict) -> None:
        pass

