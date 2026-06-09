"""
CLI bootstrap — build the API client and resolve the user identity.

Configuration lives in ``unifai_cli.config.app_config``.
API methods live in ``unifai_cli.api``.
Auth session lives in ``unifai_cli.auth``.
"""
from __future__ import annotations

import os
from typing import Optional

from unifai_cli.api.base import MASClient
from unifai_cli.api.blueprints import BlueprintsAPI
from unifai_cli.api.resources import ResourcesAPI
from unifai_cli.api.sessions import SessionsAPI
from unifai_cli.config.app_config import AppConfig


class _UnifAIClient(BlueprintsAPI, ResourcesAPI, SessionsAPI):
    """Composite client with blueprints, resources, and sessions capabilities."""


def build_client(
    mas_url: Optional[str] = None,
    user_id: Optional[str] = None,
    session_cookie: Optional[str] = None,
) -> MASClient:
    """Build a MAS API client from URL flag or environment.

    When *session_cookie* is provided the client sends it with every
    request so MAS can validate the caller via the Redis session store.
    """
    config = AppConfig.get_instance()
    url = mas_url or os.environ.get("MAS_URL", config.mas_url)
    client = _UnifAIClient(url)
    if user_id:
        client.set_authenticated_user(user_id)
    if session_cookie:
        client.set_session_cookie(session_cookie)
    return client


def resolve_user_id(user_option: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Resolve the authenticated user ID and session cookie.

    Returns:
        ``(username, session_cookie)`` — *session_cookie* is ``None``
        when the identity was provided via ``--user`` / ``UNIFAI_USER``
        (no server session exists).

    Priority:
      1. Explicit ``--user`` flag (CI / scripting override — no session)
      2. ``UNIFAI_USER`` env var (CI / scripting override — no session)
      3. Local SSO session (``~/.unifai/session.json``, 10-hour TTL)
      4. Browser-based SSO login (triggers automatically when no session exists)
    """
    if user_option:
        return user_option, None

    env_user = os.environ.get("UNIFAI_USER")
    if env_user:
        return env_user, None

    from unifai_cli.auth.flow import ensure_authenticated
    user_info = ensure_authenticated()
    return user_info["username"], user_info.get("session_cookie")
