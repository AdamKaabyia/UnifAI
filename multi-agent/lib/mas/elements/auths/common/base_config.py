from pydantic import BaseModel


class AuthBaseConfig(BaseModel):
    """Base configuration for all auth element types."""

    class Config:
        extra = "forbid"
