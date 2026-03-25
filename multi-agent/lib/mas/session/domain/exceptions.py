class SessionBlueprintError(Exception):
    """Base class for session blueprint-related errors."""
    pass


class BlueprintNotFoundError(SessionBlueprintError):
    """Raised when a blueprint required by a session is not found or has been deleted."""
    
    def __init__(self, blueprint_id: str, session_id: str = None):
        self.blueprint_id = blueprint_id
        self.session_id = session_id
        
        if session_id:
            msg = f"Cannot load session '{session_id}': Blueprint '{blueprint_id}' has been deleted"
        else:
            msg = f"Blueprint '{blueprint_id}' does not exist or has been deleted"
            
        super().__init__(msg)
