from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

actions_bp = Blueprint("actions", __name__)


@actions_bp.route("/actions.list", methods=["GET"])
@from_query({
    "category": fields.Str(required=False),
    "type": fields.Str(required=False),
    "action_type": fields.Str(data_key="actionType", required=False),
    "tags": fields.List(fields.Str(), required=False),
})
def list_actions(category=None, type=None, action_type=None, tags=None):
    """
    List actions with optional filtering.
    
    Query parameters:
    - category: Element category (e.g., "PROVIDER", "LLMS") [optional]
    - type: Element type (e.g., "mcp_server", "openai_llm") [optional]
    - actionType: Filter by action type (validation, discovery, utility) [optional]
    - tags: Filter by tags (comma-separated) [optional]
    
    If no parameters provided, returns all actions.
    
    Response format:
    {
        "actions": [
            {
                "uid": "mcp.validate_connection",
                "name": "validate_connection",
                "description": "Validate that the MCP server endpoint is reachable",
                "action_type": "validation",
                "elements": [{"category": "PROVIDER", "type": "mcp_server"}],
                "tags": ["mcp", "validation"],
                "input_schema": {...},
                "output_schema": {...}
            }
        ],
        "total_actions": 2,
        "filters_applied": {
            "category": "PROVIDER",
            "type": "mcp_server",
            "action_type": "validation",
            "tags": ["mcp"]
        }
    }
    """
    try:
        svc = current_app.container.actions_service

        # Get actions metadata based on filters - let service handle validation
        actions_metadata = svc.get_actions_metadata(
            action_type_str=action_type,
            tags=tags,
            category=category,
            element_type=type
        )

        return jsonify({
            "actions": actions_metadata,
            "total_actions": len(actions_metadata),
            "filters_applied": {
                "category": category,
                "type": type,
                "action_type": action_type,
                "tags": tags
            }
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@actions_bp.route("/action.execute", methods=["POST"])
@from_body({
    "uid": fields.Str(required=True),
    "input_data": fields.Dict(data_key="inputData", required=False, load_default={}),
    "context": fields.Dict(required=False, load_default={})
})
def execute_action(uid, input_data, context):
    """
    Execute a specific action by UID (synchronously).
    Input is validated automatically before execution.
    
    Request body:
    {
        "uid": "mcp.validate_connection",
        "inputData": {
            "mcp_url": "http://localhost:3000/sse"
        },
        "context": {
            "element_config": {...}
        }
    }
    
    Response format:
    {
        "success": true,
        "message": "Connection successful",
        "is_reachable": true,
        "response_time_ms": 125.5
    }
    """
    try:
        svc = current_app.container.actions_service

        # Execute the action (validation happens automatically inside)
        result = svc.execute_action_sync(uid, input_data, context)

        return jsonify(result), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
