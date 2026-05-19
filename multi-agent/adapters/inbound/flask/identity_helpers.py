"""
Helpers for resolving an Identity from raw request parameters.

``resolve_identity`` is the canonical builder that turns raw strings
(``userId``, ``identityType``) into an ``Identity`` domain object.
It lives in ``global_utils.identity`` so all services share the same
implementation without a Flask import dependency.

For endpoint-level usage prefer the ``@with_identity`` decorator in
``global_utils.flask.decorators`` — it reads the params from the Flask
request automatically and injects the resolved ``Identity`` as a kwarg.
"""
from __future__ import annotations

from global_utils.identity import resolve_identity  # noqa: F401


def authenticated_username() -> str:
    """Username from the auth gateway (trusted). Empty if unset (e.g. local dev)."""
    from flask import has_request_context, request

    if not has_request_context():
        return ""
    return (request.headers.get("X-Authenticated-User") or "").strip()
