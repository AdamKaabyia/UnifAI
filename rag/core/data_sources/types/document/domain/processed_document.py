"""ProcessedDocument - domain model for a converted and enriched document."""

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ProcessedDocument:
    """
    Domain model representing a document after conversion and metadata enrichment.

    Returned by DocumentConnector after delegating conversion to a
    DocumentConverterPort implementation.
    """

    text: str
    markdown: str
    path: str
    filename: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for downstream consumers that expect dict input."""
        return dataclasses.asdict(self)
