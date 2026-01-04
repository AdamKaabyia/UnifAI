"""
Local authentication endpoints for external users.
Provides signup, login, and session management for username/password auth.
"""
from flask import Blueprint, jsonify, request, session
from shared.logger import logger

# Create a blueprint for local auth routes
local_auth_bp = Blueprint('local_auth', __name__)


def get_local_auth_manager():
    """Get the LocalAuthManager from the Flask app context."""
    from flask import current_app
    return current_app.extensions.get('local_auth_manager')


@local_auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    Register a new external user.
    
    Request body:
    {
        "username": "string",
        "email": "string",
        "password": "string",
        "name": "string"
    }
    
    Returns:
    {
        "success": bool,
        "message": "string",
        "user": { ... } (on success)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Request body is required'
            }), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        local_auth_manager = get_local_auth_manager()
        if not local_auth_manager:
            logger.error("LocalAuthManager not initialized")
            return jsonify({
                'success': False,
                'message': 'Authentication service unavailable'
            }), 503
        
        success, message, user = local_auth_manager.signup(
            username=username,
            email=email,
            password=password,
            name=name
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'user': user.to_session_user()
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred during registration'
        }), 500


@local_auth_bp.route('/login', methods=['POST'])
def local_login():
    """
    Authenticate an external user with username/email and password.
    
    Request body:
    {
        "identifier": "string",  // username or email
        "password": "string"
    }
    
    Returns:
    {
        "authenticated": bool,
        "message": "string",
        "user": { ... } (on success)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'authenticated': False,
                'message': 'Request body is required'
            }), 400
        
        identifier = data.get('identifier', '').strip()
        password = data.get('password', '')
        
        local_auth_manager = get_local_auth_manager()
        if not local_auth_manager:
            logger.error("LocalAuthManager not initialized")
            return jsonify({
                'authenticated': False,
                'message': 'Authentication service unavailable'
            }), 503
        
        success, message, session_user = local_auth_manager.login(
            identifier=identifier,
            password=password
        )
        
        if success:
            return jsonify({
                'authenticated': True,
                'message': message,
                'user': session_user
            }), 200
        else:
            return jsonify({
                'authenticated': False,
                'message': message
            }), 401
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'authenticated': False,
            'message': 'An error occurred during login'
        }), 500


@local_auth_bp.route('/refresh', methods=['POST'])
def refresh_local_session():
    """
    Refresh the session token for a local auth user.
    
    Returns:
    {
        "success": bool,
        "message": "string"
    }
    """
    try:
        local_auth_manager = get_local_auth_manager()
        if not local_auth_manager:
            return jsonify({
                'success': False,
                'message': 'Authentication service unavailable'
            }), 503
        
        if not local_auth_manager.is_local_auth_session():
            return jsonify({
                'success': False,
                'message': 'Not a local auth session'
            }), 400
        
        success, message = local_auth_manager.refresh_session()
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 401
            
    except Exception as e:
        logger.error(f"Session refresh error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred during session refresh'
        }), 500


@local_auth_bp.route('/check-username', methods=['GET'])
def check_username():
    """
    Check if a username is available.
    
    Query params:
        username: The username to check
        
    Returns:
    {
        "available": bool
    }
    """
    username = request.args.get('username', '').strip()
    
    if not username or len(username) < 3:
        return jsonify({'available': False, 'message': 'Username too short'}), 400
    
    local_auth_manager = get_local_auth_manager()
    if not local_auth_manager:
        return jsonify({'available': False, 'message': 'Service unavailable'}), 503
    
    is_taken = local_auth_manager.user_repo.username_exists(username)
    
    return jsonify({
        'available': not is_taken
    }), 200


@local_auth_bp.route('/check-email', methods=['GET'])
def check_email():
    """
    Check if an email is available.
    
    Query params:
        email: The email to check
        
    Returns:
    {
        "available": bool
    }
    """
    email = request.args.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'available': False, 'message': 'Email required'}), 400
    
    local_auth_manager = get_local_auth_manager()
    if not local_auth_manager:
        return jsonify({'available': False, 'message': 'Service unavailable'}), 503
    
    is_taken = local_auth_manager.user_repo.email_exists(email)
    
    return jsonify({
        'available': not is_taken
    }), 200

