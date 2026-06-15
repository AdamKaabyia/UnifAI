"""List blueprints command — shows available blueprints from multi-agent."""
import logging

import requests

from slack_commands.clients.multiagent import MultiagentClient
from slack_commands.commands.base import CommandHandler
from slack_commands.formatters import format_blueprint_list
from slack_commands.models import SlackCommand, SlackResponse

logger = logging.getLogger(__name__)


class ListBlueprintsCommand(CommandHandler):

    def __init__(self, client: MultiagentClient):
        self._client = client

    def handle(self, command: SlackCommand) -> SlackResponse:
        try:
            blueprints = self._client.list_blueprints(command.user_name)
        except requests.Timeout:
            return SlackResponse(text=":hourglass: Multi-agent service timed out.")
        except requests.RequestException as e:
            logger.error("Failed to fetch blueprints: %s", e, exc_info=True)
            return SlackResponse(text=":x: Failed to reach multi-agent service.")
        except Exception as e:
            logger.error("Unexpected error listing blueprints: %s", e, exc_info=True)
            return SlackResponse(text=f":x: Unexpected error: {e}")

        return format_blueprint_list(blueprints)
