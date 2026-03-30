"""
Services package for SSO backend.
Contains business logic separated from endpoints following SOLID principles.
"""
from services.auth_service import AuthService, AuthResult
from services.profile_service import ProfileService, ProfileUpdateResult, PasswordUpdateResult

__all__ = [
    'AuthService', 
    'AuthResult',
    'ProfileService', 
    'ProfileUpdateResult', 
    'PasswordUpdateResult'
]

