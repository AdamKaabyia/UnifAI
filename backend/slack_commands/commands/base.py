"""Abstract base for slash command handlers."""
import logging
from abc import ABC, abstractmethod

import requests

from slack_commands.http import MAS_TIMEOUT, auth_headers, signed_post  # noqa: F401
from slack_commands.models import SlackCommand, SlackResponse

logger = logging.getLogger(__name__)


class CommandHandler(ABC):
    """
    Base class for slash command handlers.

    Each handler processes one subcommand (e.g. "list", "help", "health")
    and returns a SlackResponse.
    """

    @abstractmethod
    def handle(self, command: SlackCommand) -> SlackResponse:
        """Execute the command and return a Slack-formatted response."""
        ...


def handle_client_error(
    error: Exception,
    *,
    session_id: str = "",
    operation: str = "Request",
) -> SlackResponse:
    """Map MAS HTTP exceptions to user-friendly Slack responses."""
    if isinstance(error, requests.HTTPError):
        if error.response is not None and error.response.status_code == 404:
            return SlackResponse(
                text=f":x: Session `{session_id}` not found."
                if session_id
                else ":x: Resource not found.",
            )
        logger.error("%s failed: %s", operation, error, exc_info=True)
        return SlackResponse(
            text=f":x: {operation} failed. Please try again later.",
        )
    if isinstance(error, requests.Timeout):
        logger.warning("%s timed out (session=%s)", operation, session_id or "n/a")
        return SlackResponse(text=":hourglass: Multi-agent service timed out.")
    logger.error("%s failed: %s", operation, error, exc_info=True)
    return SlackResponse(
        text=":x: An unexpected error occurred. Please try again later.",
    )
