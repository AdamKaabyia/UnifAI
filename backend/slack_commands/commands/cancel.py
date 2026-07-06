"""Cancel command — cancels a running session."""
from slack_commands.commands.base import (
    CommandHandler, MAS_TIMEOUT, mas_post, handle_client_error,
)
from slack_commands.models import SlackCommand, SlackResponse, sanitize_slack_arg


class CancelCommand(CommandHandler):

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai cancel <session_id>`"
            )

        try:
            resp = mas_post(
                f"{self._url}/api/sessions/session.cancel",
                command.user_name,
                {"sessionId": session_id},
                timeout=MAS_TIMEOUT,
            )
            if resp.status_code == 409:
                return SlackResponse(
                    text=f":warning: Session `{session_id}` is not in a cancellable state (may already be completed or cancelled)."
                )
            resp.raise_for_status()
        except Exception as e:
            return handle_client_error(
                e, session_id=session_id, operation="Cancel",
            )

        return SlackResponse(
            text=f":no_entry_sign: Session `{session_id}` has been cancelled.",
            response_type="in_channel",
        )
