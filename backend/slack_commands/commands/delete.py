"""Delete command — permanently removes a session."""
import requests

from slack_commands.commands.base import CommandHandler, handle_client_error
from slack_commands.http import MAS_TIMEOUT, auth_headers
from slack_commands.models import SlackCommand, SlackResponse, sanitize_slack_arg


class DeleteCommand(CommandHandler):

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai delete <session_id>`"
            )

        try:
            resp = requests.delete(
                f"{self._url}/api/sessions/session.delete",
                params={"sessionId": session_id},
                headers=auth_headers(command.user_name),
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            deleted = resp.json().get("success", False)
        except Exception as e:
            return handle_client_error(
                e, session_id=session_id, operation="Delete",
            )

        if deleted:
            return SlackResponse(
                text=f":wastebasket: Session `{session_id}` has been deleted.",
                response_type="in_channel",
            )

        return SlackResponse(
            text=f":warning: Session `{session_id}` was not found or already deleted."
        )
