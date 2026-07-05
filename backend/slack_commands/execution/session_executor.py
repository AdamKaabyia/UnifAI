"""SessionExecutor — runs session lifecycle in a background thread.

Handles the deferred-response pattern required by Slack's 3-second limit:
submit → poll → extract answer → POST result to response_url.

This is the single place where the poll/respond logic lives (DRY).
"""
import atexit
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

from slack_commands.http import auth_headers, signed_post

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2
_POLL_TIMEOUT = 600
_TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
_MAX_WORKERS = 10


class SessionExecutor:
    """Executes a session asynchronously and posts the result to Slack."""

    def __init__(self, base_url: str, signing_secret: str, max_workers: int = _MAX_WORKERS):
        self._url = base_url.rstrip("/")
        self._secret = signing_secret
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        atexit.register(self.close)

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def run_new_session(
        self,
        user_id: str,
        blueprint_id: str,
        question: str,
        response_url: str,
    ) -> None:
        """Submit a background task that creates, submits, polls, and responds."""
        self._pool.submit(
            self._execute, user_id, blueprint_id, question, response_url, False,
        )

    def continue_session(
        self,
        user_id: str,
        session_id: str,
        question: str,
        response_url: str,
    ) -> None:
        """Submit a background task that submits to existing session, polls, and responds."""
        self._pool.submit(
            self._execute, user_id, session_id, question, response_url, True,
        )

    def _execute(
        self,
        user_id: str,
        ref_id: str,
        question: str,
        response_url: str,
        is_continuation: bool,
    ) -> None:
        try:
            if is_continuation:
                session_id = ref_id
            else:
                session_id = self._create_session(user_id, ref_id)

            self._submit_session(user_id, session_id, question)
            status = self._poll_until_terminal(session_id, user_id)

            if status == "COMPLETED":
                state = self._get_session_state(session_id, user_id)
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
                ":x: Session request failed. Please try again later.",
            )
        except TimeoutError:
            self._post_to_slack(
                response_url,
                ":x: Session timed out. It may still be running.",
            )
        except Exception as e:
            logger.error("Session execution failed: %s", e, exc_info=True)
            self._post_to_slack(
                response_url,
                ":x: An unexpected error occurred. Please try again later.",
            )

    # ── MAS API calls ─────────────────────────────────────────────

    def _create_session(self, user_id: str, blueprint_id: str) -> str:
        resp = signed_post(
            f"{self._url}/api/sessions/user.session.create",
            self._secret, user_id,
            {
                "blueprintId": blueprint_id,
                "userId": user_id,
                "identityType": "user",
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            sid = (
                payload.get("sessionId")
                or payload.get("session_id")
                or payload.get("id")
            )
            if sid:
                return str(sid)
        raise ValueError(f"Unexpected create_session response type: {type(payload).__name__}")

    def _submit_session(self, user_id: str, session_id: str, prompt: str) -> None:
        resp = signed_post(
            f"{self._url}/api/sessions/user.session.submit",
            self._secret, user_id,
            {
                "sessionId": session_id,
                "inputs": {"user_prompt": prompt},
                "userId": user_id,
                "identityType": "user",
            },
            timeout=15,
        )
        resp.raise_for_status()

    def _get_session_state(self, session_id: str, user_id: str) -> dict:
        resp = requests.get(
            f"{self._url}/api/sessions/session.state.get",
            params={"sessionId": session_id},
            headers=auth_headers(self._secret, user_id),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Poll / format / post ──────────────────────────────────────

    def _poll_until_terminal(self, session_id: str, user_id: str) -> str:
        elapsed = 0
        while elapsed < _POLL_TIMEOUT:
            time.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

            resp = requests.get(
                f"{self._url}/api/sessions/session.status.get",
                params={"sessionId": session_id},
                headers=auth_headers(self._secret, user_id),
                timeout=10,
            )
            resp.raise_for_status()
            status = resp.json()
            if isinstance(status, str) and status.upper() in _TERMINAL_STATUSES:
                return status.upper()

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
                if isinstance(last, dict):
                    answer = last.get("content") or last.get("text") or str(last)
                else:
                    answer = str(last)

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
            parsed = urlparse(response_url or "")
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not host.endswith(".slack.com"):
                logger.error("Refusing to post to non-Slack response_url: %s", host)
                return

            resp = requests.post(
                response_url,
                json={
                    "response_type": "in_channel" if success else "ephemeral",
                    "text": text,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error("Failed to post deferred response to Slack: %s", e)
