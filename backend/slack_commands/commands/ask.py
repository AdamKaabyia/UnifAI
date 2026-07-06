"""Ask command — creates or continues a session against a blueprint.

Thin handler: parses input, resolves blueprint/session, and delegates
the long-running execution to SessionExecutor (deferred response pattern).
"""
import logging
import re

import requests

from slack_commands.commands.base import CommandHandler, MAS_TIMEOUT, auth_headers, mas_post
from slack_commands.execution.session_executor import SessionExecutor
from slack_commands.models import SlackCommand, SlackResponse, sanitize_slack_arg

logger = logging.getLogger(__name__)

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class AskCommand(CommandHandler):

    def __init__(self, base_url: str, executor: SessionExecutor):
        self._url = base_url.rstrip("/")
        self._executor = executor

    def handle(self, command: SlackCommand) -> SlackResponse:
        parts = command.args.split(maxsplit=1)

        if len(parts) < 2:
            return self._usage()

        ref, question = sanitize_slack_arg(parts[0]), parts[1]

        if _UUID_PATTERN.match(ref):
            exists = self._session_exists(ref, command.user_name)
            if exists is None:
                return SlackResponse(
                    text=":x: Could not verify session. Please try again.",
                )
            if exists:
                self._executor.continue_session(
                    user_name=command.user_name,
                    session_id=ref,
                    question=question,
                    response_url=command.response_url,
                )
                return SlackResponse(
                    text=f":hourglass: Continuing session `{ref[:8]}…` with your question...",
                    response_type="in_channel",
                )

        blueprint_id, label = self._resolve_blueprint(command.user_name, ref)
        if blueprint_id is None:
            return label

        self._executor.run_new_session(
            user_name=command.user_name,
            blueprint_id=blueprint_id,
            question=question,
            response_url=command.response_url,
        )
        return SlackResponse(
            text=f":hourglass: Running *{label}* with your question...",
            response_type="in_channel",
        )

    def _session_exists(self, session_id: str, user_id: str):
        """Returns True / False / None (transient error)."""
        try:
            resp = requests.get(
                f"{self._url}/api/sessions/session.status.get",
                params={"sessionId": session_id},
                headers=auth_headers(user_id),
                timeout=5,
            )
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return False
            logger.warning("session_exists check failed: %s", e)
            return None
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning("session_exists check failed: %s", e)
            return None

    def _resolve_blueprint(self, user_id: str, ref: str):
        """Resolve a blueprint reference (UUID or name) to (id, display_label).

        Returns (None, SlackResponse) on error so the caller can short-circuit.
        """
        if _UUID_PATTERN.match(ref):
            return ref, ref

        resp = requests.get(
            f"{self._url}/api/blueprints/available.blueprints.summary.get",
            params={"userId": user_id, "identityType": "user"},
            headers=auth_headers(user_id),
            timeout=MAS_TIMEOUT,
        )
        resp.raise_for_status()
        blueprints = resp.json()

        matches = [
            bp for bp in blueprints
            if (bp.get("name") or bp.get("spec_dict", {}).get("name") or "").lower() == ref.lower()
        ]

        if len(matches) == 1:
            bp = matches[0]
            bp_id = bp.get("blueprint_id", "")
            name = bp.get("name") or bp.get("spec_dict", {}).get("name") or bp_id
            return bp_id, name

        if len(matches) > 1:
            ids = "\n".join(
                f"• `{bp.get('blueprint_id', '?')}` — {bp.get('name', '?')}"
                for bp in matches
            )
            return None, SlackResponse(
                text=(
                    f":warning: Multiple blueprints named *{ref}*:\n{ids}\n"
                    f"Please use the full ID."
                ),
            )

        return None, SlackResponse(
            text=(
                f":x: No blueprint found with name *{ref}*.\n"
                f"Run `/unifai blueprints` to see available options."
            ),
        )

    @staticmethod
    def _usage() -> SlackResponse:
        return SlackResponse(
            text=(
                "*Usage:*\n"
                "• `/unifai ask <blueprint> <question>` — Start a new session\n"
                "• `/unifai ask <session_id> <question>` — Continue an existing session\n"
                "\nRun `/unifai blueprints` to see available blueprints."
            ),
        )
