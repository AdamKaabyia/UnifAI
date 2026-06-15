"""List sessions command — shows the user's sessions from multi-agent."""
import logging

import requests

from slack_commands.clients.multiagent import MultiagentClient
from slack_commands.commands.base import CommandHandler
from slack_commands.formatters import format_session_list
from slack_commands.models import SlackCommand, SlackResponse

logger = logging.getLogger(__name__)

_PAGE_SIZE = 10


class ListSessionsCommand(CommandHandler):

    def __init__(self, client: MultiagentClient):
        self._client = client

    def handle(self, command: SlackCommand) -> SlackResponse:
        page = self._parse_page(command.args)

        try:
            sessions = self._client.list_sessions(command.user_name)
        except requests.Timeout:
            return SlackResponse(text=":hourglass: Multi-agent service timed out.")
        except requests.RequestException as e:
            logger.error("Failed to fetch sessions: %s", e, exc_info=True)
            return SlackResponse(text=":x: Failed to reach multi-agent service.")
        except Exception as e:
            logger.error("Unexpected error listing sessions: %s", e, exc_info=True)
            return SlackResponse(text=f":x: Unexpected error: {e}")

        return format_session_list(sessions, page=page, page_size=_PAGE_SIZE)

    @staticmethod
    def _parse_page(args: str) -> int:
        stripped = args.strip()
        if stripped.isdigit():
            return max(1, int(stripped))
        return 1
