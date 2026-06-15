"""Delete command — permanently removes a session."""
import logging

import requests

from slack_commands.clients.multiagent import MultiagentClient
from slack_commands.commands.base import CommandHandler
from slack_commands.models import SlackCommand, SlackResponse, sanitize_slack_arg

logger = logging.getLogger(__name__)


class DeleteCommand(CommandHandler):

    def __init__(self, client: MultiagentClient):
        self._client = client

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai delete <session_id>`"
            )

        try:
            deleted = self._client.delete_session(session_id, command.user_name)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return SlackResponse(text=f":x: Session `{session_id}` not found.")
            logger.error("Delete failed: %s", e, exc_info=True)
            return SlackResponse(text=f":x: Failed to delete session: {e}")
        except requests.Timeout:
            return SlackResponse(text=":hourglass: Multi-agent service timed out.")
        except Exception as e:
            logger.error("Delete failed: %s", e, exc_info=True)
            return SlackResponse(text=f":x: Unexpected error: {e}")

        if deleted:
            return SlackResponse(
                text=f":wastebasket: Session `{session_id}` has been deleted.",
                response_type="in_channel",
            )

        return SlackResponse(
            text=f":warning: Session `{session_id}` was not found or already deleted."
        )
