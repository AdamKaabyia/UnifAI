"""
Authorization URL construction — private to the oauth2 package.
"""

from __future__ import annotations

from urllib.parse import urlencode

from .config import OAuth2Config
from ._pkce import PKCEPair


def build_authorization_url(
    cfg: OAuth2Config,
    redirect_uri: str,
    state: str,
    pkce: PKCEPair,
) -> str:
    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": pkce.challenge,
        "code_challenge_method": pkce.method,
    }
    if cfg.scopes:
        params["scope"] = " ".join(cfg.scopes)
    if cfg.resource_uri:
        params["resource"] = cfg.resource_uri
    params.update(cfg.extra_authorize_params)
    return f"{cfg.authorization_endpoint}?{urlencode(params)}"
