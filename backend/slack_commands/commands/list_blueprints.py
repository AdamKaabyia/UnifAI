"""List blueprints command — shows available blueprints from multi-agent."""
import requests

from slack_commands.commands.base import (
    CommandHandler, MAS_TIMEOUT, auth_headers, handle_client_error,
)
from slack_commands.formatters import format_blueprint_list
from slack_commands.models import SlackCommand, SlackResponse


class ListBlueprintsCommand(CommandHandler):

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")

    def handle(self, command: SlackCommand) -> SlackResponse:
        try:
            resp = requests.get(
                f"{self._url}/api/blueprints/available.blueprints.summary.get",
                params={"userId": command.user_name, "identityType": "user"},
                headers=auth_headers(command.user_name),
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            blueprints = resp.json()
        except Exception as e:
            return handle_client_error(e, operation="Blueprint listing")

        return format_blueprint_list(blueprints)
