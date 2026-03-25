from typing import List, Optional, Tuple
from mas.catalog.element_registry import ElementRegistry
from mas.graph.graph_plan import GraphPlan
from .interfaces import ValidationProvider, FixSuggestionProvider
from .models import ValidationReport, ValidationResult
from .fix_models import FixSuggestion
from .settings import ValidationSettings


class GraphValidationService:
    """Orchestrates validation and fix suggestion providers."""

    def __init__(self, element_registry: ElementRegistry, settings: ValidationSettings = None):
        self._settings = settings or ValidationSettings()
        self._validation_providers = self._create_validation_providers(
            element_registry=element_registry,
            settings=self._settings
        )
        self._fix_providers = self._create_fix_providers(
            element_registry=element_registry,
            settings=self._settings
        )

    def _create_validation_providers(self, *args, **kwargs) -> List[ValidationProvider]:
        """Create all registered validation providers."""
        return [
            provider_class(*args, **kwargs)
            for provider_class in ValidationProvider.get_all_providers()
        ]

    def _create_fix_providers(self, *args, **kwargs) -> List[FixSuggestionProvider]:
        """Create all registered fix suggestion providers."""
        return [
            provider_class(*args, **kwargs)
            for provider_class in FixSuggestionProvider.get_all_providers()
        ]

    def validate_all(self, plan: GraphPlan) -> ValidationResult:
        """Run all validators and return aggregate result."""
        reports = [provider.validate(plan) for provider in self._validation_providers]
        is_valid = all(report.is_valid for report in reports)

        return ValidationResult(
            is_valid=is_valid,
            reports=reports
        )

    def get_validator(self, name: str) -> Optional[ValidationProvider]:
        """Get validator by name."""
        return next((v for v in self._validation_providers if v.name == name), None)

    def run_validator(self, name: str, plan: GraphPlan) -> ValidationReport:
        """Run specific validator by name."""
        validator = self.get_validator(name)
        if not validator:
            raise ValueError(f"Validator '{name}' not found")
        return validator.validate(plan)

    def suggest_fixes(
            self,
            plan: GraphPlan,
            validation_result: ValidationResult | None = None
    ) -> List[FixSuggestion]:
        """Get fix suggestions from all providers."""
        suggestions = []

        # Create report lookup for providers that can use validation context
        report_map = {}
        if validation_result:
            report_map = {report.validator_name: report for report in validation_result.reports}

        for provider in self._fix_providers:
            # Pass the matching validation report if available
            matching_report = report_map.get(provider.name)
            provider_suggestions = provider.suggest_fixes(plan, matching_report)
            suggestions.extend(provider_suggestions)

        return suggestions

    def validate_and_suggest(self, plan: GraphPlan) -> Tuple[ValidationResult, List[FixSuggestion]]:
        """Convenience method to validate and get suggestions in one call."""
        validation_result = self.validate_all(plan)
        suggestions = self.suggest_fixes(plan, validation_result)
        return validation_result, suggestions

    def _get_suggestions_for_provider(
            self,
            provider_name: str,
            plan: GraphPlan,
            validation_report: ValidationReport
    ) -> List[FixSuggestion]:
        """Get fix suggestions from a specific provider."""
        for provider in self._fix_providers:
            if provider.name == provider_name:
                return provider.suggest_fixes(plan, validation_report)
        return []

    def validate_dependencies(self, plan: GraphPlan) -> Tuple[ValidationReport, List[FixSuggestion]]:
        """Validate dependencies and get fix suggestions."""
        validation_report = self.run_validator('dependency', plan)
        suggestions = self._get_suggestions_for_provider('dependency', plan, validation_report)
        return validation_report, suggestions

    def validate_cycles(self, plan: GraphPlan) -> Tuple[ValidationReport, List[FixSuggestion]]:
        """Validate cycles and get fix suggestions."""
        validation_report = self.run_validator('cycle', plan)
        suggestions = self._get_suggestions_for_provider('cycle', plan, validation_report)
        return validation_report, suggestions

    def validate_orphans(self, plan: GraphPlan) -> Tuple[ValidationReport, List[FixSuggestion]]:
        """Validate orphans and get fix suggestions."""
        validation_report = self.run_validator('orphan', plan)
        suggestions = self._get_suggestions_for_provider('orphan', plan, validation_report)
        return validation_report, suggestions

    def validate_channels(self, plan: GraphPlan) -> Tuple[ValidationReport, List[FixSuggestion]]:
        """Validate channels and get fix suggestions."""
        validation_report = self.run_validator('channel', plan)
        suggestions = self._get_suggestions_for_provider('channel', plan, validation_report)
        return validation_report, suggestions

    def validate_required_nodes(self, plan: GraphPlan) -> Tuple[ValidationReport, List[FixSuggestion]]:
        """Validate required nodes and get fix suggestions."""
        validation_report = self.run_validator('required_nodes', plan)
        suggestions = self._get_suggestions_for_provider('required_nodes', plan, validation_report)
        return validation_report, suggestions

    def get_validation_names(self) -> List[str]:
        """Get list of all available validation names."""
        return [provider.name for provider in self._validation_providers]
