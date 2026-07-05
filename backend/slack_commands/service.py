"""
SlackCommandsService — application service for slash command routing.

Routes incoming commands to the appropriate handler and returns
a formatted Slack response. Stateless — all dependencies injected.
"""
import logging
from typing import Dict

import requests

from slack_commands.commands.base import CommandHandler
from slack_commands.models import SlackCommand, SlackResponse

logger = logging.getLogger(__name__)


class SlackCommandsService:
    """
    Routes slash commands to registered handlers.

    Handlers are registered by subcommand name at construction time
    (wired in AppContainer). Unknown commands return a help hint.
    """

    def __init__(self, handlers: Dict[str, CommandHandler]):
        self._handlers = handlers

    def execute(self, command: SlackCommand) -> SlackResponse:
        """Dispatch a parsed command to the matching handler."""
        handler = self._handlers.get(command.subcommand)

        if handler is None:
            return SlackResponse(
                text=(
                    f"Unknown command: `{command.subcommand}`. "
                    f"Type `{command.command} help` for available commands."
                ),
            )

        try:
            return handler.handle(command)
        except requests.RequestException as e:
            logger.error(
                "Command '%s' network error (user=%s): %s",
                command.subcommand, command.user_id, e, exc_info=True,
            )
            return SlackResponse(text=":x: Service unavailable. Please try again later.")
        except Exception as e:
            logger.error(
                "Command '%s' unexpected error (user=%s): %s",
                command.subcommand, command.user_id, e, exc_info=True,
            )
            return SlackResponse(text=":x: Command failed. Please try again later.")
