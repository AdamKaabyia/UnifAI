"""History command — shows the conversation messages for a session."""
import logging
from typing import List

import requests

from slack_commands.clients.multiagent import MultiagentClient
from slack_commands.commands.base import CommandHandler
from slack_commands.models import SlackCommand, SlackResponse, sanitize_slack_arg

logger = logging.getLogger(__name__)

_MAX_MESSAGES = 10
_MAX_CONTENT_LENGTH = 300

_ROLE_EMOJI = {
    "user": ":bust_in_silhouette:",
    "human": ":bust_in_silhouette:",
    "assistant": ":robot_face:",
    "ai": ":robot_face:",
    "system": ":gear:",
    "tool": ":wrench:",
}


class HistoryCommand(CommandHandler):

    def __init__(self, client: MultiagentClient):
        self._client = client

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai history <session_id>`"
            )

        try:
            chat = self._client.get_session_chat(session_id, command.user_name)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return SlackResponse(text=f":x: Session `{session_id}` not found.")
            logger.error("History fetch failed: %s", e, exc_info=True)
            return SlackResponse(text=f":x: Failed to fetch history: {e}")
        except requests.Timeout:
            return SlackResponse(text=":hourglass: Multi-agent service timed out.")
        except Exception as e:
            logger.error("History fetch failed: %s", e, exc_info=True)
            return SlackResponse(text=f":x: Unexpected error: {e}")

        messages = chat.get("messages", [])
        if not messages:
            return SlackResponse(
                text=f":inbox_tray: No messages yet in session `{session_id}`."
            )

        return self._format_messages(session_id, messages)

    def _format_messages(self, session_id: str, messages: List[dict]) -> SlackResponse:
        total = len(messages)
        shown = messages[-_MAX_MESSAGES:]
        skipped = total - len(shown)

        lines = [f"*Chat History* — `{session_id}`\n"]

        if skipped > 0:
            lines.append(f"_({skipped} earlier messages not shown)_\n")

        for msg in shown:
            role = msg.get("role") or msg.get("type") or "unknown"
            content = msg.get("content") or msg.get("text") or ""
            emoji = _ROLE_EMOJI.get(role.lower(), ":speech_balloon:")

            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )

            if len(content) > _MAX_CONTENT_LENGTH:
                content = content[:_MAX_CONTENT_LENGTH] + "…"

            lines.append(f"{emoji} *{role}:* {content}")

        return SlackResponse(text="\n".join(lines))
