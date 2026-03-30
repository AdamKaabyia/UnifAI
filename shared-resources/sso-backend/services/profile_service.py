"""
Profile Service for Local Users

Handles user profile updates and password changes.
Follows Single Responsibility Principle - only handles profile management.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from flask import session

from models.user import UserRepository
from utils.password_utils import (
    hash_password, 
    verify_password, 
    validate_password_strength, 
    validate_email
)
from shared.logger import logger


@dataclass
class ProfileUpdateResult:
    """Result of a profile update operation."""
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


@dataclass
class PasswordUpdateResult:
    """Result of a password update operation."""
    success: bool
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message
        }


class ProfileService:
    """
    Service for handling user profile operations.
    
    Responsibilities:
    - Profile information updates (name, email, username)
    - Password changes
    - Profile validation
    
    Usage:
        service = ProfileService(user_repo)
        result = service.update_profile(user_sub, name="New Name")
        if result.success:
            # Profile updated successfully
    """
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    def update_profile(
        self,
        user_sub: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None
    ) -> ProfileUpdateResult:
        """
        Update user profile information.
        
        Args:
            user_sub: User's unique identifier
            name: New display name (optional)
            email: New email address (optional)
            username: New username (optional)
            
        Returns:
            ProfileUpdateResult with success status and updated user data
        """
        # Get current user
        current_user = self.user_repo.find_by_sub(user_sub)
        if not current_user:
            return ProfileUpdateResult(False, "User not found")
        
        updates = {}
        
        # Validate and prepare name update
        if name is not None:
            name = name.strip()
            if name and name != current_user.name:
                if len(name) < 2:
                    return ProfileUpdateResult(False, "Name must be at least 2 characters")
                updates['name'] = name
        
        # Validate and prepare username update
        if username is not None:
            username = username.strip()
            if username and username != current_user.username:
                if len(username) < 3:
                    return ProfileUpdateResult(False, "Username must be at least 3 characters")
                if self.user_repo.username_exists(username):
                    return ProfileUpdateResult(False, "Username is already taken")
                updates['username'] = username
        
        # Validate and prepare email update
        if email is not None:
            email = email.strip().lower()
            if email and email != current_user.email:
                if not validate_email(email):
                    return ProfileUpdateResult(False, "Invalid email format")
                if self.user_repo.email_exists(email):
                    return ProfileUpdateResult(False, "Email is already registered")
                updates['email'] = email
        
        # No changes
        if not updates:
            return ProfileUpdateResult(True, "No changes to update")
        
        # Apply updates
        success = self.user_repo.update_user(user_sub, updates)
        
        if success:
            # Update session with new values
            for key, value in updates.items():
                session['user'][key] = value
            
            logger.info(f"Profile updated for user {user_sub}: {list(updates.keys())}")
            return ProfileUpdateResult(
                success=True,
                message="Profile updated successfully",
                user=session['user']
            )
        
        return ProfileUpdateResult(False, "Failed to update profile")
    
    def update_password(
        self,
        user_sub: str,
        current_password: str,
        new_password: str
    ) -> PasswordUpdateResult:
        """
        Update user password.
        
        Args:
            user_sub: User's unique identifier
            current_password: Current password for verification
            new_password: New password to set
            
        Returns:
            PasswordUpdateResult indicating success or failure
        """
        if not current_password or not new_password:
            return PasswordUpdateResult(False, "Current password and new password are required")
        
        # Get current user
        current_user = self.user_repo.find_by_sub(user_sub)
        if not current_user:
            return PasswordUpdateResult(False, "User not found")
        
        # Verify current password
        if not verify_password(current_password, current_user.password_hash):
            return PasswordUpdateResult(False, "Current password is incorrect")
        
        # Validate new password strength
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            return PasswordUpdateResult(False, error_msg)
        
        # Hash and update password
        new_password_hash = hash_password(new_password)
        success = self.user_repo.update_user(user_sub, {
            'password_hash': new_password_hash
        })
        
        if success:
            logger.info(f"Password updated for user {user_sub}")
            return PasswordUpdateResult(True, "Password updated successfully")
        
        return PasswordUpdateResult(False, "Failed to update password")
    
    @staticmethod
    def verify_local_auth_session() -> tuple[bool, Optional[str], str]:
        """
        Verify that the current session is a local auth session.
        
        Returns:
            Tuple of (is_valid, user_sub, error_message)
        """
        if session.get('auth_provider') != 'local':
            return False, None, "This operation is only available for local accounts"
        
        user_sub = session.get('user', {}).get('sub')
        if not user_sub:
            return False, None, "Not authenticated"
        
        return True, user_sub, ""

