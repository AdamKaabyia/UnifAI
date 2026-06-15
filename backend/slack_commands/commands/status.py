"""Status command — shows current status and metadata for a session."""
import logging

import requests

from slack_commands.clients.multiagent import MultiagentClient
from slack_commands.commands.base import CommandHandler
from slack_commands.models import SlackCommand, SlackResponse, sanitize_slack_arg

logger = logging.getLogger(__name__)

_STATUS_EMOJI = {
    "COMPLETED": ":white_check_mark:",
    "RUNNING": ":arrows_counterclockwise:",
    "QUEUED": ":hourglass:",
    "PENDING": ":clock3:",
    "FAILED": ":x:",
    "CANCELLED": ":no_entry_sign:",
    "LOCKED": ":lock:",
    "IN_USE": ":arrows_counterclockwise:",
}


class StatusCommand(CommandHandler):

    def __init__(self, client: MultiagentClient):
        self._client = client

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai status <session_id>`"
            )

        try:
            status = self._client.get_session_status(session_id, command.user_name)
            meta_resp = self._client.get_session_meta(session_id, command.user_name)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return SlackResponse(text=f":x: Session `{session_id}` not found.")
            logger.error("Status check failed: %s", e, exc_info=True)
            return SlackResponse(text=f":x: Failed to get status: {e}")
        except requests.Timeout:
            return SlackResponse(text=":hourglass: Multi-agent service timed out.")
        except Exception as e:
            logger.error("Status check failed: %s", e, exc_info=True)
            return SlackResponse(text=f":x: Unexpected error: {e}")

        emoji = _STATUS_EMOJI.get((status or "").upper(), ":grey_question:")
        meta = meta_resp.get("meta", {})
        title = meta.get("title") or "untitled"
        status_message = meta.get("status_message") or ""

        lines = [
            f"{emoji} *Session Status*",
            f"• *ID:* `{session_id}`",
            f"• *Status:* {status or 'unknown'}",
            f"• *Title:* {title}",
        ]
        if status_message:
            lines.append(f"• *Message:* {status_message}")

        return SlackResponse(text="\n".join(lines))
