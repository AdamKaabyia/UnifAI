"""Base HTTP client for the MAS API."""
from __future__ import annotations

from typing import Any

import requests

from unifai_cli.config.app_config import AppConfig


class MASClient:
    """HTTP primitives for the MAS (Multi-Agent System) API."""

    def __init__(self, base_url: str):
        config = AppConfig.get_instance()
        self.base_url = base_url.rstrip("/")
        self.api_prefix = config.api_prefix
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _url(self, parent: str, route: str) -> str:
        return f"{self.base_url}{self.api_prefix}/{parent}/{route}"

    def _get(self, parent: str, route: str, params: dict = None) -> Any:
        resp = self.session.get(self._url(parent, route), params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, parent: str, route: str, json: dict = None) -> Any:
        resp = self.session.post(self._url(parent, route), json=json)
        resp.raise_for_status()
        return resp.json()

    def _post_stream(self, parent: str, route: str, json: dict = None):
        """POST with NDJSON streaming response."""
        resp = self.session.post(self._url(parent, route), json=json, stream=True)
        resp.raise_for_status()
        return resp

    def _get_stream(self, parent: str, route: str, params: dict = None):
        """GET with NDJSON streaming response."""
        resp = self.session.get(self._url(parent, route), params=params, stream=True)
        resp.raise_for_status()
        return resp

    def _delete(self, parent: str, route: str, params: dict = None) -> Any:
        resp = self.session.delete(self._url(parent, route), params=params)
        resp.raise_for_status()
        return resp.json()
