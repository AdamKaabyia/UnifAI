"""
Local Authentication Endpoints

Thin routing layer for local user authentication.
Business logic is delegated to services following SOLID principles.
"""
from flask import Blueprint, jsonify, request, session
from shared.logger import logger

local_auth_bp = Blueprint('local_auth', __name__)


def get_auth_service():
    """Get AuthService from Flask app context."""
    from flask import current_app
    return current_app.extensions.get('auth_service')


def get_profile_service():
    """Get ProfileService from Flask app context."""
    from flask import current_app
    return current_app.extensions.get('profile_service')


# ============================================================================
# Authentication Endpoints
# ============================================================================

@local_auth_bp.route('/signup', methods=['POST'])
def signup():
    """Register a new external user."""
    data = request.get_json() or {}
    
    auth_service = get_auth_service()
    if not auth_service:
        return jsonify({'success': False, 'message': 'Service unavailable'}), 503
    
    result = auth_service.signup(
        username=data.get('username', '').strip(),
        email=data.get('email', '').strip().lower(),
        password=data.get('password', ''),
        name=data.get('name', '').strip()
    )
    
    status_code = 201 if result.success else 400
    return jsonify(result.to_dict()), status_code


@local_auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user with username/email and password."""
    data = request.get_json() or {}
    
    auth_service = get_auth_service()
    if not auth_service:
        return jsonify({'authenticated': False, 'message': 'Service unavailable'}), 503
    
    result = auth_service.login(
        identifier=data.get('identifier', '').strip(),
        password=data.get('password', '')
    )
    
    # Return authenticated format for login
    response = {
        'authenticated': result.success,
        'message': result.message
    }
    if result.user:
        response['user'] = result.user
    
    status_code = 200 if result.success else 401
    return jsonify(response), status_code


@local_auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh session token for local auth user."""
    auth_service = get_auth_service()
    if not auth_service:
        return jsonify({'success': False, 'message': 'Service unavailable'}), 503
    
    if not auth_service.is_local_auth_session():
        return jsonify({'success': False, 'message': 'Not a local auth session'}), 400
    
    result = auth_service.refresh_session()
    status_code = 200 if result.success else 401
    return jsonify(result.to_dict()), status_code


# ============================================================================
# Availability Check Endpoints
# ============================================================================

@local_auth_bp.route('/check-username', methods=['GET'])
def check_username():
    """Check if username is available."""
    username = request.args.get('username', '').strip()
    
    if len(username) < 3:
        return jsonify({'available': False, 'message': 'Username too short'}), 400
    
    auth_service = get_auth_service()
    if not auth_service:
        return jsonify({'available': False, 'message': 'Service unavailable'}), 503
    
    available = auth_service.check_username_available(username)
    return jsonify({'available': available}), 200


@local_auth_bp.route('/check-email', methods=['GET'])
def check_email():
    """Check if email is available."""
    email = request.args.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'available': False, 'message': 'Email required'}), 400
    
    auth_service = get_auth_service()
    if not auth_service:
        return jsonify({'available': False, 'message': 'Service unavailable'}), 503
    
    available = auth_service.check_email_available(email)
    return jsonify({'available': available}), 200


# ============================================================================
# Profile Management Endpoints
# ============================================================================

@local_auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update user profile (local auth only)."""
    from services.profile_service import ProfileService
    
    # Verify session
    is_valid, user_sub, error = ProfileService.verify_local_auth_session()
    if not is_valid:
        status = 403 if 'only available' in error else 401
        return jsonify({'success': False, 'message': error}), status
    
    profile_service = get_profile_service()
    if not profile_service:
        return jsonify({'success': False, 'message': 'Service unavailable'}), 503
    
    data = request.get_json() or {}
    result = profile_service.update_profile(
        user_sub=user_sub,
        name=data.get('name'),
        email=data.get('email'),
        username=data.get('username')
    )
    
    status_code = 200 if result.success else 400
    return jsonify(result.to_dict()), status_code


@local_auth_bp.route('/password', methods=['PUT'])
def update_password():
    """Update user password (local auth only)."""
    from services.profile_service import ProfileService
    
    # Verify session
    is_valid, user_sub, error = ProfileService.verify_local_auth_session()
    if not is_valid:
        status = 403 if 'only available' in error else 401
        return jsonify({'success': False, 'message': error}), status
    
    profile_service = get_profile_service()
    if not profile_service:
        return jsonify({'success': False, 'message': 'Service unavailable'}), 503
    
    data = request.get_json() or {}
    result = profile_service.update_password(
        user_sub=user_sub,
        current_password=data.get('current_password', ''),
        new_password=data.get('new_password', '')
    )
    
    status_code = 200 if result.success else 400
    return jsonify(result.to_dict()), status_code
