"""
Outbound HTTP client for Identity pod team APIs.

MAS must never inline HTTP calls to the Identity pod inside Flask decorators
or endpoint handlers.  All team-related queries (membership checks, team-id
resolution, team listing) go through this client so that:

  - The Identity pod owns the logic; MAS owns only the HTTP call.
  - The client is registered in the DI container and injected where needed.
  - ``flask_app.py`` stays free of identity-base URL manipulation.
"""
import logging
import time
from threading import Lock
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TEAM_IDS_CACHE_TTL_SEC = 45.0


class IdentityTeamsClient:
    """Thin HTTP client for the Identity pod ``teams.*`` endpoints.

    Registered in the DI container so that inbound adapters (Flask endpoints,
    Flask decorators) can consume it via ``current_app.container`` rather than
    making raw HTTP calls with an identity base URL read from Flask config.
    """

    def __init__(self, base_url: str, timeout: int = 5):
        self._base = (base_url or "").rstrip("/")
        self._timeout = timeout
        self._cache: dict[str, tuple[float, list]] = {}
        self._lock = Lock()

    # ── Internal helpers ────────────────────────────────────────────────

    def _get_cached(self, username: str) -> Optional[list]:
        now = time.monotonic()
        with self._lock:
            entry = self._cache.get(username)
            if entry is not None and (now - entry[0]) < _TEAM_IDS_CACHE_TTL_SEC:
                return entry[1]
        return None

    def _set_cached(self, username: str, teams: list) -> None:
        with self._lock:
            self._cache[username] = (time.monotonic(), teams)

    def _fetch_teams(self, username: str) -> list:
        """Return raw ``teams`` array from Identity ``teams.list``."""
        resp = requests.get(
            f"{self._base}/api/teams/teams.list",
            params={"userId": username},
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"teams.list HTTP {resp.status_code}")
        return resp.json().get("teams", []) or []

    # ── Public API ──────────────────────────────────────────────────────

    @property
    def configured(self) -> bool:
        """True when an identity base URL has been provided."""
        return bool(self._base)

    def get_team_ids(self, username: str) -> frozenset[str]:
        """Return the set of team IDs the *username* belongs to.

        Results are cached briefly (``_TEAM_IDS_CACHE_TTL_SEC``) to reduce
        load on the Identity pod.  Returns an empty set when the client is
        not configured or the request fails.
        """
        if not self._base:
            return frozenset()

        cached = self._get_cached(username)
        if cached is not None:
            return frozenset(str(t.get("team_id")) for t in cached if t.get("team_id"))

        try:
            teams = self._fetch_teams(username)
            self._set_cached(username, teams)
            return frozenset(str(t.get("team_id")) for t in teams if t.get("team_id"))
        except Exception:
            logger.exception("IdentityTeamsClient.get_team_ids failed for %s", username)
            return frozenset()

    def is_member(self, username: str, team_id: str) -> bool:
        """Return True when *username* is a member of *team_id*.

        Fails **open** (returns True) when the client is not configured so
        that local-dev setups without an Identity pod still work.
        Fails **closed** (returns False) when the client IS configured but
        the request fails, preventing unauthorized access.
        """
        if not self._base:
            return True
        try:
            return team_id in self.get_team_ids(username)
        except Exception:
            logger.exception("IdentityTeamsClient.is_member check failed — denying")
            return False

    def resolve_team_id(self, username: str, team_name_or_id: str) -> Optional[str]:
        """Map a team display name or id to its canonical ``team_id``.

        Returns *team_name_or_id* unchanged when the client is not configured
        (legacy/local-dev).  Returns ``None`` when the Identity pod is
        reachable but the user has no matching team, or on error.
        """
        raw = str(team_name_or_id).strip()
        if not raw:
            return None
        if not self._base:
            return raw

        cached = self._get_cached(username)
        try:
            teams = cached if cached is not None else self._fetch_teams(username)
            if cached is None:
                self._set_cached(username, teams)
        except Exception:
            logger.exception("IdentityTeamsClient.resolve_team_id failed for %s", username)
            return None

        for t in teams:
            tid = str(t.get("team_id") or "").strip()
            if not tid:
                continue
            if raw.casefold() == tid.casefold():
                return tid
            nm = str(t.get("name") or "").strip()
            if nm and raw.casefold() == nm.casefold():
                return tid
        return None
