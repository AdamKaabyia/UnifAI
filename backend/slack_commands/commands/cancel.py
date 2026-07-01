"""Cancel command — cancels a running session."""
import logging

import requests

from slack_commands.clients.multiagent import MultiagentClient
from slack_commands.commands.base import CommandHandler
from slack_commands.models import SlackCommand, SlackResponse, sanitize_slack_arg

logger = logging.getLogger(__name__)


class CancelCommand(CommandHandler):

    def __init__(self, client: MultiagentClient):
        self._client = client

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai cancel <session_id>`"
            )

        try:
            cancelled = self._client.cancel_session(session_id, command.user_name)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return SlackResponse(text=f":x: Session `{session_id}` not found.")
            logger.error("Cancel failed: %s", e, exc_info=True)
            return SlackResponse(text=":x: Failed to cancel session. Please try again later.")
        except requests.Timeout:
            return SlackResponse(text=":hourglass: Multi-agent service timed out.")
        except Exception as e:
            logger.error("Cancel failed: %s", e, exc_info=True)
            return SlackResponse(text=":x: An unexpected error occurred. Please try again later.")

        if cancelled:
            return SlackResponse(
                text=f":no_entry_sign: Session `{session_id}` has been cancelled.",
                response_type="in_channel",
            )

        return SlackResponse(
            text=f":warning: Session `{session_id}` is not in a cancellable state (may already be completed or cancelled)."
        )
