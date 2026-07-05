"""List sessions command — shows the user's sessions from multi-agent."""
import requests

from slack_commands.commands.base import (
    CommandHandler, MAS_TIMEOUT, auth_headers, handle_client_error,
)
from slack_commands.formatters import format_session_list
from slack_commands.models import SlackCommand, SlackResponse

_PAGE_SIZE = 10


class ListSessionsCommand(CommandHandler):

    def __init__(self, base_url: str, signing_secret: str):
        self._url = base_url.rstrip("/")
        self._secret = signing_secret

    def handle(self, command: SlackCommand) -> SlackResponse:
        page = self._parse_page(command.args)

        try:
            resp = requests.get(
                f"{self._url}/api/sessions/session.user.list",
                params={"userId": command.user_id, "identityType": "user"},
                headers=auth_headers(self._secret, command.user_id),
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            sessions = resp.json()
        except Exception as e:
            return handle_client_error(e, operation="Session listing")

        return format_session_list(sessions, page=page, page_size=_PAGE_SIZE)

    @staticmethod
    def _parse_page(args: str) -> int:
        stripped = args.strip()
        if stripped.isdigit():
            return max(1, int(stripped))
        return 1
