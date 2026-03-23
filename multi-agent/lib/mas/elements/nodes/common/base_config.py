from typing import Optional, List, Union, Annotated
from pydantic import BaseModel, Field, Extra


class NodeBaseConfig(BaseModel):
    """
    Common fields for all node types.
    Pure configuration schema - no UI metadata.
    
    Defines all atomic node fields as optional by default.
    Subclasses will override required ones as needed.
    UI metadata is now handled by ElementSpec classes.
    """
    retries: Optional[int] = Field(1, description="Retry count if failure")

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
