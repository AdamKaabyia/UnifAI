"""SessionExecutor — runs session lifecycle in a background thread.

Handles the deferred-response pattern required by Slack's 3-second limit:
submit → poll → extract answer → POST result to response_url.

This is the single place where the poll/respond logic lives (DRY).
"""
import logging
import time
from threading import Thread

import requests

from slack_commands.clients.multiagent import MultiagentClient

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2
_POLL_TIMEOUT = 600
_TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


class SessionExecutor:
    """Executes a session asynchronously and posts the result to Slack."""

    def __init__(self, client: MultiagentClient):
        self._client = client

    def run_new_session(
        self,
        user_name: str,
        blueprint_id: str,
        question: str,
        response_url: str,
    ) -> None:
        """Spawn a background thread that creates, submits, polls, and responds."""
        Thread(
            target=self._execute,
            args=(user_name, blueprint_id, question, response_url, False),
            daemon=True,
        ).start()

    def continue_session(
        self,
        user_name: str,
        session_id: str,
        question: str,
        response_url: str,
    ) -> None:
        """Spawn a background thread that submits to existing session, polls, and responds."""
        Thread(
            target=self._execute,
            args=(user_name, session_id, question, response_url, True),
            daemon=True,
        ).start()

    def _execute(
        self,
        user_name: str,
        ref_id: str,
        question: str,
        response_url: str,
        is_continuation: bool,
    ) -> None:
        try:
            if is_continuation:
                session_id = ref_id
            else:
                session_id = self._client.create_session(user_name, ref_id)

            self._client.submit_session(user_name, session_id, question)
            status = self._poll_until_terminal(session_id, user_name)

            if status == "COMPLETED":
                state = self._client.get_session_state(session_id, user_name)
                text = self._format_answer(state, session_id)
                self._post_to_slack(response_url, text, success=True)
            else:
                self._post_to_slack(
                    response_url,
                    f":x: Session ended with status: *{status}*\n"
                    f"_Session ID: `{session_id}`_",
                )

        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "?"
            body = self._extract_error_body(e)
            logger.error("Session HTTP error: %s %s", status_code, body, exc_info=True)
            self._post_to_slack(
                response_url,
                f":x: Request failed (HTTP {status_code}): {body or e}",
            )
        except TimeoutError:
            self._post_to_slack(
                response_url,
                f":x: Session timed out after {_POLL_TIMEOUT}s. It may still be running.",
            )
        except Exception as e:
            logger.error("Session execution failed: %s", e, exc_info=True)
            self._post_to_slack(response_url, f":x: Error: {e}")

    def _poll_until_terminal(self, session_id: str, user_name: str) -> str:
        elapsed = 0
        while elapsed < _POLL_TIMEOUT:
            time.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

            status = self._client.get_session_status(session_id, user_name)
            if status and status in _TERMINAL_STATUSES:
                return status

        raise TimeoutError(
            f"Session {session_id} did not complete within {_POLL_TIMEOUT}s"
        )

    @staticmethod
    def _format_answer(result: dict, session_id: str) -> str:
        answer = (
            result.get("final_answer")
            or result.get("output")
            or result.get("answer")
            or result.get("result")
        )

        if not answer and isinstance(result, dict):
            messages = result.get("messages", [])
            if messages and isinstance(messages, list):
                last = messages[-1]
                answer = last.get("content") or last.get("text") or str(last)

        if not answer:
            answer = (
                f"Session completed but no answer extracted.\n"
                f"Raw result: ```{str(result)[:500]}```"
            )

        return (
            f":white_check_mark: *Session Complete*\n\n"
            f"{answer}\n\n"
            f"_Session ID: `{session_id}`_"
        )

    @staticmethod
    def _extract_error_body(error: requests.HTTPError) -> str:
        try:
            if error.response is not None:
                return error.response.json().get("error", "")
        except Exception:
            pass
        return ""

    @staticmethod
    def _post_to_slack(response_url: str, text: str, success: bool = False) -> None:
        try:
            requests.post(
                response_url,
                json={
                    "response_type": "in_channel" if success else "ephemeral",
                    "text": text,
                },
                timeout=10,
            )
        except Exception as e:
            logger.error("Failed to post deferred response to Slack: %s", e)
