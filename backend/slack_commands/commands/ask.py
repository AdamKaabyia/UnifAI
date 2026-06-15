"""Ask command — creates or continues a session against a blueprint.

Thin handler: parses input, resolves blueprint/session, and delegates
the long-running execution to SessionExecutor (deferred response pattern).
"""
import re

from slack_commands.clients.multiagent import MultiagentClient
from slack_commands.commands.base import CommandHandler
from slack_commands.execution.session_executor import SessionExecutor
from slack_commands.models import SlackCommand, SlackResponse, sanitize_slack_arg

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class AskCommand(CommandHandler):

    def __init__(self, client: MultiagentClient, executor: SessionExecutor):
        self._client = client
        self._executor = executor

    def handle(self, command: SlackCommand) -> SlackResponse:
        parts = command.args.split(maxsplit=1)

        if len(parts) < 2:
            return self._usage()

        ref, question = sanitize_slack_arg(parts[0]), parts[1]

        if _UUID_PATTERN.match(ref) and self._client.session_exists(ref, command.user_name):
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
            return label  # label is a SlackResponse error in this case

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

    def _resolve_blueprint(
        self, user_name: str, ref: str
    ) -> "tuple[str | None, str | SlackResponse]":
        """Resolve a blueprint reference (UUID or name) to (id, display_label).

        Returns (None, SlackResponse) on error so the caller can short-circuit.
        """
        if _UUID_PATTERN.match(ref):
            return ref, ref

        blueprints = self._client.list_blueprints(user_name)
        matches = [bp for bp in blueprints if bp.name.lower() == ref.lower()]

        if len(matches) == 1:
            return matches[0].blueprint_id, matches[0].name

        if len(matches) > 1:
            ids = "\n".join(
                f"• `{bp.blueprint_id}` — {bp.name}" for bp in matches
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
