"""
Dynamic Client Registration (RFC 7591) — private to the oauth2 package.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mas.core.auth.errors import ClientRegistrationError
from mas.core.auth.ports import HttpClient


async def register_client(
    http: HttpClient,
    registration_endpoint: str,
    client_name: str = "UnifAI",
    redirect_uris: Optional[List[str]] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "client_name": client_name,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_post",
    }
    if redirect_uris:
        body["redirect_uris"] = redirect_uris

    try:
        resp = await http.post(
            registration_endpoint, json=body,
            headers={"Accept": "application/json"}, timeout=10.0,
        )
    except Exception as exc:
        raise ClientRegistrationError(f"DCR request failed: {exc}") from exc

    if resp.status_code >= 400:
        raise ClientRegistrationError(
            f"DCR returned {resp.status_code}: "
            f"{resp.body.get('error_description', resp.body.get('error', ''))}"
        )
    if "client_id" not in resp.body:
        raise ClientRegistrationError("DCR response missing client_id")
    return resp.body
