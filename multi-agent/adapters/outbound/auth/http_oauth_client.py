"""
HttpxAuthClient — implements :class:`HttpClient` port using httpx.

This is the *only* place in the auth layer that imports httpx.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from mas.core.auth.ports import HttpClient, HttpResponse

logger = logging.getLogger(__name__)


class HttpxAuthClient(HttpClient):

    async def post(
        self,
        url: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, data=data, json=json, headers=headers)
            body = self._parse_body(resp)
            return HttpResponse(
                status_code=resp.status_code,
                body=body,
                headers=dict(resp.headers),
            )

    async def get(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
            body = self._parse_body(resp)
            return HttpResponse(
                status_code=resp.status_code,
                body=body,
                headers=dict(resp.headers),
            )

    @staticmethod
    def _parse_body(resp: httpx.Response) -> Dict[str, Any]:
        """Parse response body, handling both JSON and form-encoded formats."""
        content_type = resp.headers.get("content-type", "")

        if "application/json" in content_type:
            try:
                return resp.json()
            except Exception:
                return {"raw": resp.text}

        if "application/x-www-form-urlencoded" in content_type:
            from urllib.parse import parse_qs
            parsed = parse_qs(resp.text)
            return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}
