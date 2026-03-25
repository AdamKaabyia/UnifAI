"""
Phase management system for agents.

This module contains all phase-related components:
- Phase definitions and protocols
- Phase providers (simple, unified, extensible)
- Validation models and contexts
- Phase-specific guidance and tools
"""

# Core phase models and protocols
from .models import (
    ValidationSeverity,
    ValidationIssue, 
    ValidationResult,
    PhaseValidationContext
)

from .phase_definition import (
    PhaseValidator,
    PhaseDefinition,
    PhaseSystem
)

from .phase_protocols import (
    PhaseState,
    PhaseContextProvider,
    PhaseToolProvider,
    PhaseTransitionPolicy,
    create_phase_state
)

# Re-export WorkPlanStatus from workload layer (single source of truth)
from mas.elements.nodes.common.workload import WorkPlanStatus

# Phase providers
from .unified_phase_provider import (
    PhaseProvider,
    BasePhaseProvider
)

from .simple_phase_provider import PhaseProvider as SimplePhaseProvider

from .extensible_phases import (
    PhaseRegistry,
    ExtensiblePhaseProvider
)

from .flexible_phase_provider import FlexiblePhaseProvider

# Utility modules
from . import phase_guidance
from . import phase_tools


__all__ = [
    # Core models
    "ValidationSeverity",
    "ValidationIssue", 
    "ValidationResult",
    "PhaseValidationContext",
    
    # Phase definitions
    "PhaseValidator",
    "PhaseDefinition", 
    "PhaseSystem",
    
    # Phase protocols
    "PhaseState",
    "WorkPlanStatus",  # Re-exported from workload layer
    "PhaseContextProvider",
    "PhaseToolProvider",
    "PhaseTransitionPolicy",
    "create_phase_state",
    
    # Phase providers
    "PhaseProvider",
    "BasePhaseProvider",
    "SimplePhaseProvider",
    "PhaseRegistry",
    "ExtensiblePhaseProvider", 
    "FlexiblePhaseProvider",
    
    # Utility modules
    "phase_guidance",
    "phase_tools",
]
