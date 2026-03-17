"""
Decorators for Flask endpoints.
"""
from functools import wraps
from flask import jsonify, request, current_app


def require_admin_access(f):
    """
    Decorator to require admin access for an endpoint.
    
    Checks if the user_id (from query params) is in admin_allowed_users list.
    If admin_allowed_users is empty, denies all access (Analytics is disabled).
    
    The decorator extracts user_id from:
    - Query parameter: 'userId' or 'user_id'
    - Function kwargs: 'user_id' or 'userId' (if passed by @from_query)
    
    Returns:
        403 Forbidden if admin_allowed_users is empty (Analytics disabled).
        403 Forbidden if user is not in admin_allowed_users list.
        401 Unauthorized if user_id is missing.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Access admin_allowed_users from Flask's config (set during app initialization)
            admin_allowed_users = current_app.config.get("admin_allowed_users", [])
            
            # If admin_allowed_users is empty, deny all access (Analytics is disabled)
            if not admin_allowed_users:
                return jsonify({
                    "error": "Access denied: Analytics is not enabled",
                    "error_type": "FEATURE_DISABLED"
                }), 403
            
            # Extract user_id from kwargs (if passed by @from_query) or query parameters
            user_id = kwargs.get("user_id") or kwargs.get("userId") or request.args.get("user_id") or request.args.get("userId")
            
            if not user_id:
                return jsonify({
                    "error": "Access denied: user_id is required",
                    "error_type": "AUTHENTICATION_REQUIRED"
                }), 401
            
            # Check if user is in admin list
            if user_id not in admin_allowed_users:
                return jsonify({
                    "error": "Access denied: insufficient permissions",
                    "error_type": "ACCESS_DENIED"
                }), 403
            
            # User is authorized, proceed with the request
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({
                "error": f"Access control error: {str(e)}",
                "error_type": "ACCESS_CONTROL_ERROR"
            }), 500
    
    return decorated_function

