from pydantic import BaseModel


class DirectoryUser(BaseModel):
    """A user record from an external directory (e.g. LDAP, SSO user-store)."""
    user_id: str
    username: str
    display_name: str
    email: str = ""
    title: str = ""
