"""Health check domain models (DTOs)."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


# "local" means no remote dependency - always considered ready (no health check needed)
ServiceStatus = Literal["healthy", "unhealthy", "local"]
ServiceMode = Literal["remote", "local"]


@dataclass
class ServiceHealthStatus:
    """Health status for a single service."""

    service_name: str
    status: ServiceStatus
    mode: ServiceMode
    message: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "mode": self.mode,
            "message": self.message,
        }


@dataclass
class ServicesHealthResult:
    """Aggregated health status for all services."""

    services: Dict[str, ServiceHealthStatus]
    required_for_upload: List[str] = field(
        default_factory=lambda: ["docling", "embedding"]
    )

    @property
    def upload_enabled(self) -> bool:
        """
        Check if document upload should be enabled.

        Upload is enabled only when all required services are either
        healthy or running locally.
        """
        for name in self.required_for_upload:
            status = self.services.get(name)
            if not status or status.status not in ("healthy", "local"):
                return False
        return True

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = {name: s.to_dict() for name, s in self.services.items()}
        result["upload_enabled"] = self.upload_enabled
        return result

    @classmethod
    def from_statuses(
        cls,
        statuses: Dict[str, ServiceHealthStatus],
        required_for_upload: Optional[List[str]] = None,
    ) -> "ServicesHealthResult":
        """Create result from a dict of service statuses."""
        return cls(
            services=statuses,
            required_for_upload=required_for_upload or ["docling", "embedding"],
        )
