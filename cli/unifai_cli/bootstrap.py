"""
CLI bootstrap — build the API client and resolve the user identity.

Configuration lives in ``unifai_cli.config.app_config``.
API methods live in ``unifai_cli.api``.
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


def build_client(mas_url: Optional[str] = None) -> MASClient:
    """Build a MAS API client from URL flag or environment."""
    config = AppConfig.get_instance()
    url = mas_url or os.environ.get("MAS_URL", config.mas_url)
    return _UnifAIClient(url)


def resolve_user_id(user_option: Optional[str] = None) -> str:
    """
    Resolve user ID from CLI flag, env var, or interactive prompt.

    Priority: explicit flag > UNIFAI_USER env var > interactive prompt.
    """
    if user_option:
        return user_option

    env_user = os.environ.get("UNIFAI_USER")
    if env_user:
        return env_user

    import questionary
    user_id = questionary.text(
        "Enter your user ID:",
        validate=lambda val: len(val.strip()) > 0 or "User ID cannot be empty",
    ).ask()

    if user_id is None:
        raise SystemExit(0)

    return user_id.strip()
