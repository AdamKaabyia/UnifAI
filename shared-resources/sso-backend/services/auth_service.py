"""
Authentication Service for Local Users

Handles signup, login, and session management operations.
Follows Single Responsibility Principle - only handles authentication logic.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from flask import session

from models.user import LocalUser, UserRepository
from utils.password_utils import hash_password, verify_password, validate_password_strength, validate_email
from shared.logger import logger
from directory.provider import DirectoryProvider


@dataclass
class AuthResult:
    """Result of an authentication operation."""
    success: bool
    message: str
    user: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'success': self.success,
            'message': self.message
        }
        if self.user:
            result['user'] = self.user
        return result


class AuthService:
    """
    Service for handling user authentication operations.
    
    Responsibilities:
    - User registration (signup)
    - User authentication (login)
    - Session creation and management
    - Session refresh
    
    Usage:
        service = AuthService(user_repo)
        result = service.signup(username, email, password, name)
        if result.success:
            # User registered successfully
    """
    
    def __init__(self, user_repo: UserRepository,
                 directory_provider: Optional[DirectoryProvider] = None):
        self.user_repo = user_repo
        self._directory = directory_provider
    
    def signup(self, username: str, email: str, password: str, name: str) -> AuthResult:
        """
        Register a new user.
        
        Args:
            username: Unique username (min 3 chars)
            email: Valid email address
            password: Password meeting strength requirements
            name: Display name (min 2 chars)
            
        Returns:
            AuthResult with success status, message, and user data if successful
        """
        # Validate username
        if not username or len(username) < 3:
            return AuthResult(False, "Username must be at least 3 characters long")
        
        # Validate email
        if not validate_email(email):
            return AuthResult(False, "Invalid email format")
        
        # Validate password
        is_valid_password, password_error = validate_password_strength(password)
        if not is_valid_password:
            return AuthResult(False, password_error)
        
        # Validate name
        if not name or len(name) < 2:
            return AuthResult(False, "Name must be at least 2 characters long")
        
        # Check for existing username/email (local DB + directory/Rover)
        if self.user_repo.username_exists(username):
            return AuthResult(False, "Username already exists")
        
        if self._username_exists_in_directory(username):
            return AuthResult(False, "Username already exists in the organization directory")

        if self.user_repo.email_exists(email):
            return AuthResult(False, "Email already exists")
        
        # Create user
        try:
            user = LocalUser(
                username=username,
                email=email,
                name=name,
                password_hash=hash_password(password)
            )
            created_user = self.user_repo.create_user(user)
            logger.info(f"New user registered: {username}")
            
            return AuthResult(
                success=True,
                message="User registered successfully",
                user=created_user.to_session_user()
            )
        except ValueError as e:
            return AuthResult(False, str(e))
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return AuthResult(False, "An error occurred during registration")
    
    def login(self, identifier: str, password: str) -> AuthResult:
        """
        Authenticate a user with username/email and password.
        
        Args:
            identifier: Username or email
            password: User's password
            
        Returns:
            AuthResult with success status and session user data if successful
        """
        if not identifier or not password:
            return AuthResult(False, "Username/email and password are required")
        
        # Find user
        user = self.user_repo.find_by_username_or_email(identifier)
        if not user:
            return AuthResult(False, "Invalid credentials")
        
        # Verify password
        if not verify_password(password, user.password_hash):
            return AuthResult(False, "Invalid credentials")
        
        # Create session
        session_user = self._create_session(user)
        logger.info(f"User {user.username} logged in successfully")
        
        return AuthResult(
            success=True,
            message="Login successful",
            user=session_user
        )
    
    def refresh_session(self) -> AuthResult:
        """
        Refresh the current session token for another 10 hours.
        
        Returns:
            AuthResult indicating success or failure
        """
        if 'user' not in session or session.get('auth_provider') != 'local':
            return AuthResult(False, "No local auth session found")
        
        user_sub = session.get('user', {}).get('sub')
        if not user_sub:
            return AuthResult(False, "Invalid session")
        
        user = self.user_repo.find_by_sub(user_sub)
        if not user:
            session.clear()
            return AuthResult(False, "User not found")

        # Refresh both session and token for another 10 hours
        now = datetime.now()
        session_expires_at = now + timedelta(hours=10)
        token_expires_at = now + timedelta(hours=10)
        
        session['user']['session_expires_at'] = session_expires_at.timestamp()
        session['user']['token_expires_at'] = token_expires_at.timestamp()
        session['token_expires_at'] = token_expires_at.timestamp()
        session['access_token'] = f"local_{user.sub}_{now.timestamp()}"
        
        logger.info(f"Session refreshed for user {user.username} - expires at {session_expires_at}")
        return AuthResult(True, "Session refreshed successfully")
    
    def _create_session(self, user: LocalUser) -> Dict[str, Any]:
        """Create session data for authenticated user."""
        now = datetime.now()
        # Both session and token expire in 10 hours for local users
        session_expires_at = now + timedelta(hours=10)
        token_expires_at = now + timedelta(hours=10)
        
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
        session['access_token'] = f"local_{user.sub}_{now.timestamp()}"
        session['token_expires_at'] = token_expires_at.timestamp()
        
        return session_user
    
    def is_local_auth_session(self) -> bool:
        """Check if current session is a local auth session."""
        return session.get('auth_provider') == 'local'
    
    def _username_exists_in_directory(self, username: str) -> bool:
        """Check if username already exists in the external directory (Rover/LDAP)."""
        if not self._directory:
            return False
        try:
            user = self._directory.get_user(username)
            return user is not None
        except Exception as e:
            logger.warning(f"Directory lookup failed for '{username}': {e}")
            return False

    def check_username_available(self, username: str) -> bool:
        """Check if a username is available (local DB + directory/Rover)."""
        if not username or len(username) < 3:
            return False
        if self.user_repo.username_exists(username):
            return False
        if self._username_exists_in_directory(username):
            return False
        return True
    
    def check_email_available(self, email: str) -> bool:
        """Check if an email is available."""
        if not email:
            return False
        return not self.user_repo.email_exists(email)

