"""
Streaming hook implementation for WorkPlan.

Emits workplan snapshots via callback when operations occur.
"""

from typing import Callable, Optional
from .hooks import BaseWorkPlanHook
from .models import WorkPlan


class WorkPlanStreamingHook(BaseWorkPlanHook):
    """Hook that streams workplan snapshots using model_dump()."""
    
    def __init__(self, stream_callback: Callable[[dict], None]):
        """
        Initialize with streaming callback.
        
        Args:
            stream_callback: Function to call with streaming data
        """
        self._stream_callback = stream_callback
    
    def on_post_save(self, plan: WorkPlan, context: dict) -> None:
        """Stream workplan snapshot after successful save."""
        try:
            self._emit_snapshot(plan, action="saved")
        except Exception as e:
            print(f"⚠️ [WORKPLAN-STREAM] Error in post_save hook: {e}")
    
    def on_post_load(self, plan: Optional[WorkPlan], context: dict) -> None:
        """Stream workplan snapshot after load (if plan exists)."""
        if plan:
            try:
                self._emit_snapshot(plan, action="loaded")
            except Exception as e:
                print(f"⚠️ [WORKPLAN-STREAM] Error in post_load hook: {e}")
    
    def on_post_delete(self, context: dict) -> None:
        """Stream deletion event."""
        try:
            self._stream_callback({
                "type": "workplan_deleted",
                "plan_id": f"{context['thread_id']}:{context['owner_uid']}",
                "thread_id": context['thread_id'],
                "owner_uid": context['owner_uid'],
                "action": "deleted"
            })
        except Exception as e:
            print(f"⚠️ [WORKPLAN-STREAM] Error in post_delete hook: {e}")
    
    def _emit_snapshot(self, plan: WorkPlan, action: str = "updated") -> None:
        """Emit complete workplan snapshot using model_dump()."""
        self._stream_callback({
            "type": "workplan_snapshot",
            "action": action,
            "plan_id": f"{plan.thread_id}:{plan.owner_uid}",
            "thread_id": plan.thread_id,
            "owner_uid": plan.owner_uid,
            "workplan": plan.model_dump()
        })

