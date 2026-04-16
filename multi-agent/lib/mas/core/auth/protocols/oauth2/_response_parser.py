"""
Token endpoint response parser — private to the oauth2 package.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from mas.core.auth.errors import TokenEndpointError
from mas.core.auth.credentials.models import TokenSet


def parse_token_response(body: Dict[str, Any]) -> TokenSet:
    if "error" in body:
        raise TokenEndpointError(
            f"{body.get('error')}: {body.get('error_description', '')}"
        )

    expires_at = None
    if "expires_in" in body:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=int(body["expires_in"])
            )
        except (ValueError, TypeError):
            pass

    return TokenSet(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        token_type=body.get("token_type", "Bearer"),
        expires_at=expires_at,
        scope=body.get("scope"),
    )
