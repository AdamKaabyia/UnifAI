"""
Local User model and repository for MongoDB storage
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4
from pydantic import BaseModel, Field
import pymongo
from pymongo.collection import Collection


class LocalUser(BaseModel):
    """
    Model for external users with local authentication.
    Mirrors the structure returned by Keycloak for compatibility.
    """
    sub: str = Field(default_factory=lambda: uuid4().hex)  # Unique identifier (matches Keycloak 'sub')
    username: str
    email: str
    name: str
    password_hash: str
    auth_provider: str = "local"  # 'local' for local auth, 'keycloak' for SSO
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_session_user(self) -> Dict[str, Any]:
        """
        Convert to session user format matching Keycloak response.
        This ensures frontend compatibility with useAuth.
        """
        return {
            'username': self.username,
            'email': self.email,
            'name': self.name,
            'sub': self.sub,
            'auth_provider': self.auth_provider
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        return {
            'sub': self.sub,
            'username': self.username,
            'email': self.email,
            'name': self.name,
            'password_hash': self.password_hash,
            'auth_provider': self.auth_provider,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LocalUser':
        """Create a LocalUser from a dictionary."""
        return cls(**data)


class UserRepository:
    """
    MongoDB repository for local user management.
    """
    
    def __init__(
        self,
        mongodb_ip: str = "localhost",
        mongodb_port: str = "27017",
        db_name: str = "UnifAI",
        collection_name: str = "local_users"
    ):
        mongo_uri = f"mongodb://{mongodb_ip}:{mongodb_port}/"
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self._collection: Collection = self.db[collection_name]
        
        # Create indexes for fast lookups
        self._collection.create_index([("username", pymongo.ASCENDING)], unique=True)
        self._collection.create_index([("email", pymongo.ASCENDING)], unique=True)
        self._collection.create_index([("sub", pymongo.ASCENDING)], unique=True)
    
    def create_user(self, user: LocalUser) -> LocalUser:
        """
        Create a new user in the database.
        
        Args:
            user: LocalUser instance to create
            
        Returns:
            Created user
            
        Raises:
            ValueError: If username or email already exists
        """
        try:
            self._collection.insert_one(user.to_dict())
            return user
        except pymongo.errors.DuplicateKeyError as e:
            if 'username' in str(e):
                raise ValueError("Username already exists")
            elif 'email' in str(e):
                raise ValueError("Email already exists")
            else:
                raise ValueError("User already exists")
    
    def find_by_username(self, username: str) -> Optional[LocalUser]:
        """Find a user by username."""
        doc = self._collection.find_one({"username": username})
        if doc:
            doc.pop('_id', None)
            return LocalUser.from_dict(doc)
        return None
    
    def find_by_email(self, email: str) -> Optional[LocalUser]:
        """Find a user by email."""
        doc = self._collection.find_one({"email": email})
        if doc:
            doc.pop('_id', None)
            return LocalUser.from_dict(doc)
        return None
    
    def find_by_sub(self, sub: str) -> Optional[LocalUser]:
        """Find a user by sub (unique identifier)."""
        doc = self._collection.find_one({"sub": sub})
        if doc:
            doc.pop('_id', None)
            return LocalUser.from_dict(doc)
        return None
    
    def find_by_username_or_email(self, identifier: str) -> Optional[LocalUser]:
        """Find a user by username or email."""
        doc = self._collection.find_one({
            "$or": [
                {"username": identifier},
                {"email": identifier}
            ]
        })
        if doc:
            doc.pop('_id', None)
            return LocalUser.from_dict(doc)
        return None
    
    def update_user(self, sub: str, updates: Dict[str, Any]) -> bool:
        """
        Update a user's data.
        
        Args:
            sub: User's unique identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if update was successful
        """
        updates['updated_at'] = datetime.utcnow()
        result = self._collection.update_one(
            {"sub": sub},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    def delete_user(self, sub: str) -> bool:
        """Delete a user by sub."""
        result = self._collection.delete_one({"sub": sub})
        return result.deleted_count > 0
    
    def username_exists(self, username: str) -> bool:
        """Check if a username already exists."""
        return self._collection.count_documents({"username": username}) > 0
    
    def email_exists(self, email: str) -> bool:
        """Check if an email already exists."""
        return self._collection.count_documents({"email": email}) > 0

