"""Common phase models and enums for validation system."""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any, Dict


class ValidationSeverity(Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation issue."""
    severity: ValidationSeverity
    message: str
    guidance: str
    item_ids: Optional[List[str]] = None


@dataclass(frozen=True)
class ValidationResult:
    """Validation result with issues and guidance."""
    issues: List[ValidationIssue]
    has_errors: bool
    has_warnings: bool
    summary_guidance: str
    
    @classmethod
    def empty(cls) -> "ValidationResult":
        """Create an empty validation result."""
        return cls(
            issues=[],
            has_errors=False,
            has_warnings=False,
            summary_guidance=""
        )
    
    @classmethod
    def from_issues(cls, issues: List[ValidationIssue]) -> "ValidationResult":
        """Create validation result from list of issues."""
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        has_warnings = any(issue.severity == ValidationSeverity.WARNING for issue in issues)
        
        # Build summary guidance from issues
        if issues:
            guidance_parts = [issue.guidance for issue in issues if issue.guidance]
            summary_guidance = "\n".join(guidance_parts)
        else:
            summary_guidance = ""
        
        return cls(
            issues=issues,
            has_errors=has_errors,
            has_warnings=has_warnings,
            summary_guidance=summary_guidance
        )


@dataclass(frozen=True)
class PhaseValidationContext:
    """
    Typed validation context for phase validators.
    
    Contains common fields that most validators need, with provider-specific
    data added by subclasses of BasePhaseProvider.
    """
    phase_state: Any                                    # PhaseState object, always present
    thread_id: Optional[str] = None                     # Common field 
    node_uid: Optional[str] = None                      # Common field
    plan: Optional[Any] = None                          # Provider-specific (e.g., WorkPlan)
    adjacent_nodes: Optional[Any] = None                # Provider-specific (AdjacentNodes model or dict for backward compatibility)
