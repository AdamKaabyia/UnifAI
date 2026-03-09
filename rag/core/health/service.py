"""
Services Health Service - Application layer service for checking external service health.

This service checks the health of external services (Docling, Embedding, etc.) used for
document processing. It uses a registry-based approach: services register themselves
(name + port), and a single check logic handles all of them. Each port self-reports
its mode via is_remote.

Follows hexagonal architecture by depending on the HealthCheckable protocol rather than
concrete port types.

Usage:
    from bootstrap.app_container import remote_services_health

    service = remote_services_health()
    result = service.check_all()

    if result.upload_enabled:
        # Safe to allow document uploads
        pass

Adding a new service (e.g. OCR, reranker) is a one-line registration in app_container.
"""

import logging
from typing import Dict, List, Optional

from core.health.domain.model import ServiceHealthStatus, ServicesHealthResult
from core.health.domain.port import HealthCheckable


logger = logging.getLogger(__name__)

# Local mode messages for common services
_LOCAL_MESSAGES: Dict[str, str] = {
    "docling": "Using local docling library",
    "embedding": "Using local embedding model",
}


class ServicesHealthService:
    """
    Application service for checking health of external document processing services.

    Uses a registry pattern: services register via register(name, port).
    A single check() method handles all services uniformly. Adding new services
    (OCR, reranker, etc.) requires only a one-line registration call.
    """

    def __init__(self):
        """Initialize with empty registry. Services are registered via register()."""
        self._services: Dict[str, HealthCheckable] = {}
        logger.info("ServicesHealthService initialized with registry")

    def register(
        self,
        name: str,
        port: HealthCheckable,
    ) -> None:
        """
        Register a service for health checks.

        The service's mode (local vs remote) is read from port.is_remote,
        keeping the decision out of the composition root.

        Args:
            name: Service identifier (e.g. "docling", "embedding")
            port: Port implementing is_remote and test_connection()
        """
        self._services[name] = port
        logger.debug(f"Registered health check: {name} (remote={port.is_remote})")

    def check(self, name: str) -> ServiceHealthStatus:
        """
        Check health of a single registered service.

        Args:
            name: Service identifier previously passed to register().

        Returns:
            ServiceHealthStatus with:
            - status='unhealthy', message='Service not registered' if name is unknown
            - status='local' if port.is_remote is False (no network call made)
            - status='healthy'/'unhealthy' based on test_connection() if port.is_remote is True
        """
        if name not in self._services:
            return ServiceHealthStatus(
                service_name=name,
                status="unhealthy",
                mode="remote",
                message="Service not registered",
            )

        port = self._services[name]

        if not port.is_remote:
            local_msg = _LOCAL_MESSAGES.get(name, "Running locally")
            return ServiceHealthStatus(
                service_name=name,
                status="local",
                mode="local",
                message=local_msg,
            )

        try:
            is_healthy = port.test_connection()
            return ServiceHealthStatus(
                service_name=name,
                status="healthy" if is_healthy else "unhealthy",
                mode="remote",
                message="Service is available" if is_healthy else "Service is unavailable",
            )
        except Exception as e:
            logger.error(f"Error checking {name} health: {e}")
            return ServiceHealthStatus(
                service_name=name,
                status="unhealthy",
                mode="remote",
                message=str(e),
            )

    def check_all(
        self,
        required_for_upload: Optional[List[str]] = None,
    ) -> ServicesHealthResult:
        """
        Check health of all registered services.

        Args:
            required_for_upload: Service names required for upload to be enabled.
                Defaults to ["docling", "embedding"].

        Returns:
            ServicesHealthResult with status for each service and upload_enabled flag.
        """
        statuses = {name: self.check(name) for name in self._services}
        required = required_for_upload or ["docling", "embedding"]

        result = ServicesHealthResult.from_statuses(
            statuses=statuses,
            required_for_upload=required,
        )

        logger.debug(
            f"Health check result: {', '.join(f'{n}={s.status}' for n, s in statuses.items())}, "
            f"upload_enabled={result.upload_enabled}"
        )

        return result
