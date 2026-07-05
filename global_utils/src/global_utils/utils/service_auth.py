"""Service-to-service HMAC request signing and verification.

Allows internal services (e.g. the backend calling MAS on behalf of a
Slack user) to prove their identity cryptographically.  Both sides share
a ``SERVICE_SIGNING_SECRET``; the caller signs each request and the
receiver verifies before trusting the embedded ``user_id``.

Signature scheme
~~~~~~~~~~~~~~~~
* Header ``X-Service-Timestamp`` — Unix epoch seconds (replay window: 5 min).
* Header ``X-Service-User-Id``   — The authenticated user id to assert.
* Header ``X-Service-Signature`` — ``svc0=<HMAC-SHA256 hex>``.

The HMAC is computed over ``svc0:{timestamp}:{user_id}:{body}`` where
*body* is the raw request body bytes (empty bytes for GET/DELETE).
"""

import hashlib
import hmac
import time
from typing import Optional

_REPLAY_WINDOW = 300  # 5 minutes

HEADER_TIMESTAMP = "X-Service-Timestamp"
HEADER_USER_ID = "X-Service-User-Id"
HEADER_SIGNATURE = "X-Service-Signature"
_SIG_VERSION = "svc0"


def sign_request(
    secret: str,
    user_id: str,
    body: bytes = b"",
) -> dict[str, str]:
    """Build signed headers for an outbound service request.

    Returns a dict with the three ``X-Service-*`` headers ready to be
    merged into the request headers.
    """
    timestamp = str(int(time.time()))
    sig_base = f"{_SIG_VERSION}:{timestamp}:{user_id}:".encode() + body
    signature = f"{_SIG_VERSION}=" + hmac.new(
        secret.encode("utf-8"),
        sig_base,
        hashlib.sha256,
    ).hexdigest()
    return {
        HEADER_TIMESTAMP: timestamp,
        HEADER_USER_ID: user_id,
        HEADER_SIGNATURE: signature,
    }


def verify_request(
    secret: str,
    headers: dict[str, str],
    body: bytes = b"",
) -> Optional[str]:
    """Verify an inbound signed service request.

    Returns the ``user_id`` on success, or ``None`` if verification fails
    (missing headers, expired timestamp, bad signature).
    """
    timestamp = headers.get(HEADER_TIMESTAMP, "")
    user_id = headers.get(HEADER_USER_ID, "")
    signature = headers.get(HEADER_SIGNATURE, "")

    if not timestamp or not user_id or not signature:
        return None

    try:
        if abs(time.time() - int(timestamp)) > _REPLAY_WINDOW:
            return None
    except ValueError:
        return None

    sig_base = f"{_SIG_VERSION}:{timestamp}:{user_id}:".encode() + body
    expected = f"{_SIG_VERSION}=" + hmac.new(
        secret.encode("utf-8"),
        sig_base,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return None

    return user_id
