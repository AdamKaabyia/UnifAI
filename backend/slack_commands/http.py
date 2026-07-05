"""HMAC-signed HTTP helpers for outbound MAS requests."""
import json as _json

import requests

from global_utils.utils.service_auth import sign_request

MAS_TIMEOUT = 10


def auth_headers(secret: str, user_id: str) -> dict:
    return sign_request(secret, user_id)


def signed_post(
    url: str, secret: str, user_id: str, payload: dict, **kwargs,
) -> requests.Response:
    """POST JSON to MAS with an HMAC-signed body."""
    body = _json.dumps(payload).encode()
    headers = {**sign_request(secret, user_id, body), "Content-Type": "application/json"}
    return requests.post(url, data=body, headers=headers, **kwargs)
