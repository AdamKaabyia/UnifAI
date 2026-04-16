"""
Token exchange and refresh — private to the oauth2 package.
"""

from __future__ import annotations

from typing import Optional

from mas.core.auth.errors import TokenEndpointError, TokenRefreshError
from mas.core.auth.ports import HttpClient
from mas.core.auth.credentials.models import TokenSet

from .config import OAuth2Config
from ._response_parser import parse_token_response


async def exchange_code(
    http: HttpClient,
    cfg: OAuth2Config,
    code: str,
    code_verifier: Optional[str],
    redirect_uri: str,
) -> TokenSet:
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": cfg.client_id,
    }
    if code_verifier:
        body["code_verifier"] = code_verifier
    if cfg.client_secret:
        body["client_secret"] = cfg.client_secret

    try:
        resp = await http.post(
            cfg.token_endpoint, data=body,
            headers={"Accept": "application/json"}, timeout=15.0,
        )
    except Exception as exc:
        raise TokenEndpointError(f"Code exchange request failed: {exc}") from exc

    if resp.status_code >= 400:
        raise TokenEndpointError(
            f"Token endpoint returned {resp.status_code}: "
            f"{resp.body.get('error_description', resp.body.get('error', ''))}"
        )
    return parse_token_response(resp.body)


async def refresh_token_set(
    http: HttpClient,
    cfg: OAuth2Config,
    refresh_token: str,
) -> TokenSet:
    body = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": cfg.client_id,
    }
    if cfg.client_secret:
        body["client_secret"] = cfg.client_secret

    try:
        resp = await http.post(
            cfg.token_endpoint, data=body,
            headers={"Accept": "application/json"}, timeout=15.0,
        )
    except Exception as exc:
        raise TokenRefreshError(f"Refresh request failed: {exc}") from exc

    if resp.status_code >= 400:
        raise TokenRefreshError(
            f"Token endpoint returned {resp.status_code}: "
            f"{resp.body.get('error_description', resp.body.get('error', ''))}"
        )
    return parse_token_response(resp.body)
