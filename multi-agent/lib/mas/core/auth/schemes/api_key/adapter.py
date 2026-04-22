"""
ApiKeyScheme — static credential, no acquisition flow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from mas.core.auth.ports import AuthScheme
from mas.core.auth.credentials.models import StoredCredential, RecoveryResult

from .config import ApiKeyConfig

logger = logging.getLogger(__name__)


class ApiKeyScheme(AuthScheme):

    @property
    def scheme_type(self) -> str:
        return "api_key"

    def build_headers(self, credential: StoredCredential) -> Dict[str, str]:
        cfg = ApiKeyConfig()
        value = f"{cfg.header_prefix}{credential.access_token}" if cfg.header_prefix else credential.access_token
        return {cfg.header_name: value}

    async def validate(self, credential: StoredCredential, server_url: str) -> bool:
        """Probe *server_url* with the API key; ``True`` if 2xx."""
        headers = self.build_headers(credential)
        headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    server_url,
                    json={
                        "jsonrpc": "2.0", "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "unifai-probe", "version": "1.0"},
                        },
                    },
                    headers=headers,
                )
                return 200 <= resp.status_code < 300
        except Exception as exc:
            logger.debug("API key validation probe failed for %s: %s", server_url, exc)
            return False

    async def attempt_recovery(
        self,
        credential: StoredCredential,
        config: Dict[str, Any],
    ) -> RecoveryResult:
        return RecoveryResult(
            recovered=False,
            should_retry=False,
            reason="API key was rejected; verify the key or generate a new one",
        )
