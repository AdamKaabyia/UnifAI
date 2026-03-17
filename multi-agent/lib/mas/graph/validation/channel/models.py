from typing import Dict, List, Set, Tuple
from pydantic import BaseModel, Field, ConfigDict, computed_field


class PathValidation(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    path_id: str
    steps: List[str]
    missing_channels: Dict[str, Set[str]]
    impossible_channels: Dict[str, Set[str]]
    is_valid: bool = False


class DependencyMatrix(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    producer_map: Dict[str, Set[Tuple[str, str]]]
    consumer_map: Dict[str, Set[Tuple[str, str]]]
    external_channels: Set[str]

    def can_produce(self, channel: str) -> bool:
        return channel in self.producer_map or channel in self.external_channels


class NodeSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    node_type: str
    category: str
    reason: str


class PathSuggestion(BaseModel):
    """Suggestions for fixing a specific path."""
    model_config = ConfigDict(frozen=True)
    
    path_id: str
    missing_channels: Set[str]
    suggestions: List[NodeSuggestion]
    
    @computed_field
    @property
    def has_suggestions(self) -> bool:
        """Whether this path has any suggestions."""
        return len(self.suggestions) > 0


class ChannelSummary(BaseModel):
    """Summary of channel validation across all paths."""
    model_config = ConfigDict(frozen=True)
    
    missing: Set[str] = Field(default_factory=set)
    impossible: Set[str] = Field(default_factory=set)
    
    @computed_field
    @property
    def total_issues(self) -> int:
        """Total number of channel issues."""
        return len(self.missing) + len(self.impossible)


class ChannelValidationDetails(BaseModel):
    """Channel-specific validation details."""
    model_config = ConfigDict(frozen=True)
    
    path_validations: Dict[str, PathValidation] = Field(default_factory=dict)
    summary: ChannelSummary = Field(default_factory=ChannelSummary)
    
    def get_path_validation(self, path_id: str) -> PathValidation:
        """Get validation for specific path."""
        return self.path_validations.get(path_id)
    
    def get_all_missing_channels(self) -> Set[str]:
        """Get all missing channels across all paths."""
        return self.summary.missing
    
    def get_all_impossible_channels(self) -> Set[str]:
        """Get all impossible channels across all paths."""
        return self.summary.impossible
    
    @computed_field
    @property
    def valid_paths(self) -> Dict[str, PathValidation]:
        """Get only valid paths."""
        return {pid: pv for pid, pv in self.path_validations.items() if pv.is_valid}
    
    @computed_field
    @property
    def invalid_paths(self) -> Dict[str, PathValidation]:
        """Get only invalid paths."""
        return {pid: pv for pid, pv in self.path_validations.items() if not pv.is_valid} 