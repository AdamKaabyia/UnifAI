from typing import Any, Optional
from pydantic import BaseModel
from enum import Enum


class ActionType(Enum):
    VALIDATION = "validation"
    DISCOVERY = "discovery"
    UTILITY = "utility"


class BaseActionInput(BaseModel):
    """Base class for all action inputs"""
    pass


class BaseActionOutput(BaseModel):
    """Base class for all action outputs"""
    success: bool
    message: str
    
    class Config:
        extra = "forbid"
