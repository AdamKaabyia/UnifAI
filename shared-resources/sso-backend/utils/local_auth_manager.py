"""
Local Authentication Manager for username/password authentication.
Handles user registration, login, and session management for external users.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from flask import session
from models.user import LocalUser, UserRepository
from utils.password_utils import hash_password, verify_password, validate_password_strength, validate_email
from shared.logger import logger
from config.app_config import AppConfig

config = AppConfig.get_instance()


class LocalAuthManager:
    """
    Manages local authentication for external users.
    Provides signup, login, and session management functionality.
    """
    
    def __init__(self, app=None):
        self.app = app
        self.user_repo: Optional[UserRepository] = None
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the local auth manager with Flask app."""
        self.app = app
        
        # Initialize user repository
        mongodb_ip = config.get('mongodb_ip', 'localhost')
        mongodb_port = config.get('mongodb_port', '27017')
        
        self.user_repo = UserRepository(
            mongodb_ip=mongodb_ip,
            mongodb_port=mongodb_port,
            db_name="UnifAI",
            collection_name="local_users"
        )
        
        logger.info("LocalAuthManager initialized")
    
    def signup(
        self,
        username: str,
        email: str,
        password: str,
        name: str
    ) -> Tuple[bool, str, Optional[LocalUser]]:
        """
        Register a new user.
        
        Args:
            username: Unique username
            email: User's email address
            password: Plain text password
            name: User's display name
            
        Returns:
            Tuple of (success, message, user)
        """
        # Validate inputs
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters long", None
        
        if not validate_email(email):
            return False, "Invalid email format", None
        
        is_valid_password, password_error = validate_password_strength(password)
        if not is_valid_password:
            return False, password_error, None
        
        if not name or len(name) < 2:
            return False, "Name must be at least 2 characters long", None
        
        # Check if username or email already exists
        if self.user_repo.username_exists(username):
            return False, "Username already exists", None
        
        if self.user_repo.email_exists(email):
            return False, "Email already exists", None
        
        # Create user
        try:
            password_hashed = hash_password(password)
            user = LocalUser(
                username=username,
                email=email,
                name=name,
                password_hash=password_hashed
            )
            
            created_user = self.user_repo.create_user(user)
            logger.info(f"New user registered: {username}")
            return True, "User registered successfully", created_user
            
        except ValueError as e:
            return False, str(e), None
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return False, "An error occurred during registration", None
    
    def login(self, identifier: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Authenticate a user with username/email and password.
        
        Args:
            identifier: Username or email
            password: Plain text password
            
        Returns:
            Tuple of (success, message, session_user_data)
        """
        if not identifier or not password:
            return False, "Username/email and password are required", None
        
        # Find user by username or email
        user = self.user_repo.find_by_username_or_email(identifier)
        
        if not user:
            # Use generic message to prevent user enumeration
            return False, "Invalid credentials", None
        
        if not user.is_active:
            return False, "Account is deactivated", None
        
        # Verify password
        if not verify_password(password, user.password_hash):
            return False, "Invalid credentials", None
        
        # Create session data matching Keycloak format
        session_user = self._create_session(user)
        
        logger.info(f"User {user.username} logged in successfully")
        return True, "Login successful", session_user
    
    def _create_session(self, user: LocalUser) -> Dict[str, Any]:
        """
        Create session data for authenticated user.
        Matches the format used by Keycloak SSO for frontend compatibility.
        """
        now = datetime.now()
        session_expires_at = now + timedelta(hours=10)
        token_expires_at = now + timedelta(hours=1)
        
        session_user = {
            'username': user.username,
            'email': user.email,
            'name': user.name,
            'sub': user.sub,
            'session_created_at': now.timestamp(),
            'session_expires_at': session_expires_at.timestamp(),
            'token_expires_at': token_expires_at.timestamp(),
            'auth_provider': 'local'
        }
        
        # Store in Flask session
        session.permanent = True
        session['user'] = session_user
        session['auth_provider'] = 'local'
        # For local auth, we generate a simple session token (not a real JWT)
        session['access_token'] = f"local_{user.sub}_{now.timestamp()}"
        session['token_expires_at'] = token_expires_at.timestamp()
        
        return session_user
    
    def refresh_session(self) -> Tuple[bool, str]:
        """
        Refresh the session for a local auth user.
        
        Returns:
            Tuple of (success, message)
        """
        if 'user' not in session or session.get('auth_provider') != 'local':
            return False, "No local auth session found"
        
        user_sub = session.get('user', {}).get('sub')
        if not user_sub:
            return False, "Invalid session"
        
        user = self.user_repo.find_by_sub(user_sub)
        if not user:
            session.clear()
            return False, "User not found"
        
        if not user.is_active:
            session.clear()
            return False, "Account is deactivated"
        
        # Refresh token expiration
        now = datetime.now()
        token_expires_at = now + timedelta(hours=1)
        
        session['user']['token_expires_at'] = token_expires_at.timestamp()
        session['token_expires_at'] = token_expires_at.timestamp()
        session['access_token'] = f"local_{user.sub}_{now.timestamp()}"
        
        logger.info(f"Session refreshed for user {user.username}")
        return True, "Session refreshed successfully"
    
    def is_local_auth_session(self) -> bool:
        """Check if current session is a local auth session."""
        return session.get('auth_provider') == 'local'
    
    def get_current_user(self) -> Optional[LocalUser]:
        """Get the current authenticated local user."""
        if not self.is_local_auth_session():
            return None
        
        user_sub = session.get('user', {}).get('sub')
        if not user_sub:
            return None
        
        return self.user_repo.find_by_sub(user_sub)

