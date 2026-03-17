from typing import Any


class PluginConfigurationError(Exception):
    """
    Raised when a plugin factory fails to accept or create an instance from a config.

    Attributes:
        message: explanation of the failure.
        config:   the config dict that caused the error.
    """

    def __init__(self, message: str, config: Any):
        super().__init__(f"{message} | config={config!r}")
        self.message = message
        self.config = config
