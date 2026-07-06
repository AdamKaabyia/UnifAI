"""HTTP helpers for outbound MAS requests."""
import requests

_AUTH_HEADER = "X-Authenticated-User"

MAS_TIMEOUT = 10


def auth_headers(user_id: str) -> dict:
    return {_AUTH_HEADER: user_id}


def mas_post(
    url: str, user_id: str, payload: dict, **kwargs,
) -> requests.Response:
    """POST JSON to MAS with user identity header."""
    headers = {_AUTH_HEADER: user_id, "Content-Type": "application/json"}
    return requests.post(url, json=payload, headers=headers, **kwargs)
