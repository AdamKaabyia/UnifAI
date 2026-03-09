"""Health check endpoints - driving adapter."""
from flask import Blueprint, jsonify

from config.app_config import AppConfig
from bootstrap.app_container import remote_services_health

health_bp = Blueprint("health", __name__)


@health_bp.route("/", methods=["GET"])
def health_check():
    """Basic health check endpoint."""
    return jsonify({"status": "ok", "message": "Server is healthy"}), 200


@health_bp.route("/version", methods=["GET"])
def get_version():
    """Get application version."""
    config = AppConfig.get_instance()
    return jsonify({"version": config.get("version", "1.0.0")}), 200


@health_bp.route("/service.readiness.get", methods=["GET"])
def service_readiness_get():
    """
    Check readiness of external services (Docling, Embedding).
    
    This endpoint is used by the UI to determine if document upload
    should be enabled. It checks each service independently.
    
    Returns:
        JSON with status for each service and an upload_enabled flag:
        {
            "docling": {
                "status": "healthy" | "unhealthy" | "local",
                "mode": "remote" | "local",
                "message": "..."
            },
            "embedding": {
                "status": "healthy" | "unhealthy" | "local",
                "mode": "remote" | "local",
                "message": "..."
            },
            "upload_enabled": true | false
        }
    """
    service = remote_services_health()
    result = service.check_all()
    return jsonify(result.to_dict()), 200
