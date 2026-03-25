"""
Retry policy service for work items.

Handles retry logic enforcement and validation following SOLID principles.
"""

from typing import Optional
from .models import WorkItem


class RetryPolicyService:
    """
    Service for managing retry policies on work items.
    
    Follows SRP: Single responsibility for retry logic enforcement.
    Keeps retry rules centralized and testable.
    """
    
    DEFAULT_MAX_RETRIES = 3
    
    @classmethod
    def can_retry(cls, item: WorkItem) -> bool:
        """
        Check if a work item can be retried.
        
        Args:
            item: Work item to check
            
        Returns:
            True if item can be retried, False otherwise
        """
        return item.retry_count < item.max_retries
    
    @classmethod
    def increment_retry(cls, item: WorkItem) -> bool:
        """
        Increment retry count for a work item.
        
        Args:
            item: Work item to increment
            
        Returns:
            True if increment was successful, False if max retries exceeded
        """
        if not cls.can_retry(item):
            return False
            
        item.retry_count += 1
        item.mark_updated()
        return True
    
    @classmethod
    def get_retry_status(cls, item: WorkItem) -> str:
        """
        Get human-readable retry status for a work item.
        
        Args:
            item: Work item to check
            
        Returns:
            Retry status string for display/logging
        """
        if item.retry_count == 0:
            return f"No retries (max: {item.max_retries})"
        elif cls.can_retry(item):
            return f"Retry {item.retry_count}/{item.max_retries}"
        else:
            return f"Max retries exceeded ({item.retry_count}/{item.max_retries})"
    
    @classmethod
    def should_mark_failed(cls, item: WorkItem) -> bool:
        """
        Check if a work item should be marked as failed due to retry limits.
        
        Args:
            item: Work item to check
            
        Returns:
            True if item should be marked failed due to retry limits
        """
        return item.retry_count >= item.max_retries
    
    @classmethod
    def create_retry_notes(cls, item: WorkItem, reason: str) -> str:
        """
        Create standardized retry notes for a work item.
        
        Args:
            item: Work item being retried
            reason: Reason for the retry
            
        Returns:
            Formatted retry notes string
        """
        retry_status = cls.get_retry_status(item)
        return f"Retry attempt - {reason}. Status: {retry_status}"
