"""Domain models for Slack slash commands."""
import re
from typing import Optional

from pydantic import BaseModel

_SLACK_FORMAT_CHARS = re.compile(r"[`_*~]")


def sanitize_slack_arg(value: str) -> str:
    """Strip Slack formatting characters (backticks, underscores, bold, strike) from a value."""
    return _SLACK_FORMAT_CHARS.sub("", value).strip()


class SlackCommand(BaseModel):
    """Parsed incoming slash command from Slack."""
    command: str
    text: str
    subcommand: str
    args: str
    user_id: str
    user_name: str
    channel_id: str
    channel_name: str
    team_id: str
    response_url: str

    @classmethod
    def from_form(cls, form: dict) -> "SlackCommand":
        text = (form.get("text") or "").strip()
        parts = text.split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "help"
        args = parts[1].strip() if len(parts) > 1 else ""

        return cls(
            command=form.get("command", ""),
            text=text,
            subcommand=subcommand,
            args=args,
            user_id=form.get("user_id", ""),
            user_name=form.get("user_name", ""),
            channel_id=form.get("channel_id", ""),
            channel_name=form.get("channel_name", ""),
            team_id=form.get("team_id", ""),
            response_url=form.get("response_url", ""),
        )


class SlackResponse(BaseModel):
    """Response to send back to Slack."""
    text: str
    response_type: str = "ephemeral"
    blocks: Optional[list] = None

    def to_dict(self) -> dict:
        result = {
            "response_type": self.response_type,
            "text": self.text,
        }
        if self.blocks:
            result["blocks"] = self.blocks
        return result
