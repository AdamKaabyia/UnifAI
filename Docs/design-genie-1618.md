# Architecture Design Review (ADR)

**Feature Name:** [GENIE-1618 — Implement @require_team_session Decorator for Redis Session & Team Identity Validation](https://redhat.atlassian.net/browse/GENIE-1618)

**Author:** Pipeline Designer | **Date:** 2026-06-03 | **Priority:** High

---

## 1. Executive Summary

| Section | Details |
|:---|:---|
| **Problem Statement** | UnifAI currently uses an unvalidated `X-Authenticated-User` header for MAS authentication — any client can impersonate any user. The CLI bypasses Redis sessions entirely. RAG trusts `logged_in_user` in request bodies. Backend trusts `X-Username` headers. There is no server-side session validation outside the Identity service itself, creating a system-wide security gap. |
| **High-Level Solution** | Create a `@require_team_session` decorator factory in `global_utils` that validates callers against Redis-backed server sessions and authorizes team-level access. Extend `UserSessionData` in Redis to include team memberships, updated in real-time on team changes. Modify the Identity CLI login flow to create Redis sessions. Migrate **all modules** (MAS, RAG, Backend, CLI, UI) to session-based auth, eliminating `X-Authenticated-User`, `X-Username`, and body-param identity. |
| **Success Metrics** | All service endpoints validate requests against Redis sessions. `X-Authenticated-User` and `X-Username` headers are eliminated from production request paths. CLI sends `session_id` cookie. Team membership is resolved from the Redis session object (no per-request HTTP call to Identity). New unit tests achieve ≥ 90 % coverage of the decorator and session sync logic. |

---

## 2. Affected Components

| Layer | Component | Action (New / Modified) | File Path |
|:---|:---|:---|:---|
| Domain | `UserSessionData` model | Modified — add `team_ids`, `user_id` alias | `global_utils/src/global_utils/redis/session_model.py` |
| Domain | `UserSessionData` serialization | Modified — JSON-encode `team_ids` list in Redis hash | `global_utils/src/global_utils/redis/session_model.py` |
| Application | `require_team_session` decorator factory | **New** | `global_utils/src/global_utils/flask/decorators.py` |
| Application | `_validate_session` helper | **New** — extracted from `require_identity_session` for reuse | `global_utils/src/global_utils/flask/decorators.py` |
| Application | Redis session index helpers | **New** — secondary index `identity:user_sessions:<username>` | `global_utils/src/global_utils/redis/server_session.py` |
| Adapter — UI / Frontend | Axios MAS interceptor | Modified — remove `X-Authenticated-User`, set `session_id` cookie | `ui/client/src/http/axiosAgentConfig.ts` |
| Adapter — UI / Frontend | Axios RAG client | Modified — add `session_id` cookie / `withCredentials` | `ui/client/src/http/` (RAG axios client) |
| Adapter — UI / Frontend | Axios Backend client | Modified — remove `X-Username` header, add cookie | `ui/client/src/api/adminConfig.ts` |
| Adapter — UI / Frontend | `AuthContext` | Modified — store `session_id` from Identity, set cookie on domain | `ui/client/src/contexts/AuthContext.tsx` |
| Adapter — API / Inbound (MAS) | Flask app factory | Modified — add session cookie config | `multi-agent/adapters/inbound/flask/flask_app.py` |
| Adapter — API / Inbound (MAS) | MAS Flask decorators | Modified — replace header-based decorators with `require_team_session` wrappers | `multi-agent/adapters/inbound/flask/decorators.py` |
| Adapter — API / Inbound (MAS) | All MAS endpoint files | Modified — read `g.user_id` / `g.team_id` instead of kwargs | `multi-agent/adapters/inbound/flask/endpoints/*.py` |
| Adapter — API / Inbound (RAG) | RAG Flask app factory | Modified — add `app.container` ref for `redis_kv_store` | `rag/bootstrap/flask_app.py` |
| Adapter — API / Inbound (RAG) | RAG endpoint files | Modified — add `@require_team_session`, remove body-param identity | `rag/infrastructure/http/pipelines.py`, `docs.py`, `terms_approval.py`, `slack.py` |
| Adapter — API / Inbound (Backend) | Backend Flask app factory | Modified — add `redis_kv_store` to container | `backend/api/flask/flask_app.py` |
| Adapter — API / Inbound (Backend) | Backend admin config endpoints | Modified — replace `X-Username` / `require_admin_access` with `require_team_session` + admin check | `backend/api/flask/endpoints/admin_config.py` |
| Adapter — Outbound (MAS) | `AppContainer` | Modified — add `redis_kv_store` | `multi-agent/bootstrap/container.py` |
| Adapter — Outbound (RAG) | `AppContainer` | Modified — add `redis_kv_store` | `rag/bootstrap/app_container.py` |
| Adapter — Outbound (Backend) | `AppContainer` | Modified — add `redis_kv_store` | `backend/core/app_container.py` |
| Adapter — Outbound (Identity) | `AuthManager.auth_callback` CLI path | Modified — create Redis session + return `session_id` | `shared-resources/identity/utils/auth_manager.py` |
| Adapter — Outbound (Identity) | `AuthManager.get_current_user` | Modified — return `session_id` in response | `shared-resources/identity/utils/auth_manager.py` |
| Adapter — Outbound (Identity) | `TeamService` | Modified — update Redis sessions on team membership change | `shared-resources/identity/teams/service.py` |
| Adapter — Outbound (CLI) | `MASClient` | Modified — send `session_id` cookie instead of `X-Authenticated-User` header | `cli/unifai_cli/api/base.py` |
| Adapter — Outbound (CLI) | CLI auth session | Modified — store `session_id` from login flow | `cli/unifai_cli/auth/session.py`, `cli/unifai_cli/auth/login.py` |
| Config / Infra | Helm shared secret | Modified — add `FLASK_SESSION_SECRET` | `helm/scripts/shared-resources-postsync.sh` or Vault |
| Tests | Decorator + session sync unit tests | **New** | `global_utils/tests/test_team_session_decorator.py` |

---

## 3. Technical Design

### 3.1 `UserSessionData` — Team Membership in Redis (`global_utils/redis/session_model.py`)

**Purpose:** Extend the Redis session hash to carry the user's team memberships, so downstream services can check team access without an HTTP call to Identity.

**Interface changes:**

```python
class UserSessionData(BaseModel):
    # ... existing fields ...
    team_ids: list[str] = Field(default_factory=list)

    @property
    def user_id(self) -> str | None:
        return self.username

    @classmethod
    def from_redis_hash(cls, data: Mapping[str, Any] | None) -> UserSessionData | None:
        # Existing parsing + handle team_ids:
        # Redis stores it as a JSON string: '["team-a","team-b"]'
        # Parse: json.loads(value) if key == "team_ids" and isinstance(value, str)

    def is_team_member(self, team_id: str) -> bool:
        return team_id in self.team_ids
```

**Serialization contract:** When writing to Redis via `hset`, `team_ids` is JSON-encoded: `json.dumps(["team-a", "team-b"])`. When reading via `from_redis_hash`, the JSON string is parsed back into `list[str]`. All other fields remain as plain strings/floats (unchanged).

### 3.2 Secondary Redis Index — Sessions by Username (`global_utils/redis/server_session.py`)

**Purpose:** Enable looking up all active session IDs for a given username, so team membership updates can propagate to all of a user's sessions.

**New constants** (`constants.py`):

```python
USER_SESSIONS_PREFIX = "identity:user_sessions"

def user_sessions_key(username: str) -> str:
    return f"{USER_SESSIONS_PREFIX}:{username}"
```

**New helpers** (`server_session.py`):

```python
def register_session(redis_store, username: str, session_id: str) -> None:
    """Add session_id to the user's session set."""
    redis_store._client.sadd(user_sessions_key(username), session_id)

def unregister_session(redis_store, username: str, session_id: str) -> None:
    """Remove session_id from the user's session set."""
    redis_store._client.srem(user_sessions_key(username), session_id)

def get_user_session_ids(redis_store, username: str) -> set[str]:
    """Return all active session IDs for a username."""
    return {
        (s.decode() if isinstance(s, bytes) else s)
        for s in redis_store._client.smembers(user_sessions_key(username))
    }

def update_team_ids_for_user(redis_store, username: str, team_ids: list[str]) -> None:
    """Update team_ids in all active sessions for a user."""
    import json
    encoded = json.dumps(team_ids)
    for sid in get_user_session_ids(redis_store, username):
        key = identity_session_key(sid)
        if redis_store._client.exists(key):
            redis_store._client.hset(key, "team_ids", encoded)
        else:
            # Session expired; clean up stale index entry
            redis_store._client.srem(user_sessions_key(username), sid)
```

> **Note:** These helpers access `redis_store._client` directly for Redis SET operations (`SADD`, `SMEMBERS`, `SREM`) that `KVStore` port does not expose. This is a pragmatic adapter-layer escape hatch. If SET operations are needed more broadly, extend `KVStore` with `sadd`/`smembers`/`srem`.

### 3.3 `require_team_session` Decorator (`global_utils/flask/decorators.py`)

**Purpose:** Pluggable decorator factory that enforces Redis-backed session validation and optional team membership authorization for any Flask service.

**Signature:**

```python
G_USER_ID = "user_id"
G_TEAM_ID = "team_id"

def require_team_session(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None] | None = None,
    get_team_id: Callable[[], str | None] | None = None,
    team_membership_checker: Callable[[str, str], bool] | None = None,
) -> Callable:
```

**Parameters:**

| Parameter | Purpose | Default |
|:---|:---|:---|
| `get_redis_store` | Returns a `RedisKVStore` (or compatible) for session lookups | Required |
| `get_session_id` | Extracts `session_id` from the request | `lambda: request.cookies.get("session_id") or session.get("session_id")` |
| `get_team_id` | Extracts `team_id` from the request (return `None` to skip team check) | `None` (no team check) |
| `team_membership_checker` | `(username, team_id) -> bool` — only used when `get_team_id` is provided | `None` (use `UserSessionData.is_team_member()` from Redis) |

**Key logic:**

1. Call `get_session_id()` → `sid`. If `None` → **401** `AUTHENTICATION_REQUIRED`.
2. Call `get_identity_session(get_redis_store(), sid)` → `UserSessionData`.
3. If `None` or not `has_auth_credentials()` → **401** `AUTHENTICATION_REQUIRED`.
4. Check `session_expires_at` — if expired → **401** `SESSION_EXPIRED`.
5. Set `g.identity_session = data` and `g.user_id = data.username`.
6. Call `get_team_id()` → `team_id`. If not `None`:
   a. If `team_membership_checker` is provided → call it.
   b. Else → call `data.is_team_member(team_id)` (from Redis session).
   c. If `False` → **403** `TEAM_ACCESS_DENIED`.
   d. If `True` → set `g.team_id = team_id`.
7. Any exception → **500** `ACCESS_CONTROL_ERROR`.
8. Call wrapped function.

**Session expiry check** (step 4) — aligns with Identity's `is_authenticated()` which checks `session_expires_at`. The existing `has_auth_credentials()` only checks presence of `username` + `access_token`, not expiry. The new decorator adds the expiry check.

**Refactoring:** Extract session validation (steps 1–5) into a private `_validate_session()` helper shared between `require_identity_session` and `require_team_session` to eliminate duplication.

### 3.4 Identity Service — CLI Redis Session + `session_id` in API (`shared-resources/identity/utils/auth_manager.py`)

#### 3.4a CLI login creates Redis session

In `auth_callback` CLI branch, after successful Keycloak token exchange:

```python
# After userinfo fetch (existing code) — NEW:
session_id = str(uuid.uuid4())
session_created_at = datetime.now()
session_expires_at = session_created_at + timedelta(hours=config.permanent_session_lifetime)

# Fetch user's teams for Redis session
team_ids = []
svc = current_app.extensions.get('team_service')
if svc:
    try:
        teams = svc.list_user_teams(userinfo.get('preferred_username'))
        team_ids = [t.team_id for t in teams]
    except Exception:
        pass
    svc.cache_user_groups(userinfo.get('preferred_username'), token.get('access_token'))

session_data = {
    'username': userinfo.get('preferred_username'),
    'email': userinfo.get('email'),
    'name': userinfo.get('name'),
    'sub': userinfo.get('sub'),
    'session_created_at': session_created_at.timestamp(),
    'session_expires_at': session_expires_at.timestamp(),
    'token_expires_at': token.get('expires_at', 0),
    'access_token': token.get('access_token'),
    'refresh_token': token.get('refresh_token'),
    'team_ids': json.dumps(team_ids),
}

ttl_seconds = self._ttl_seconds_until_session_expires(session_expires_at.timestamp())
self.redis_store.hset(identity_session_key(session_id), session_data, ttl_seconds=ttl_seconds)
register_session(self.redis_store, userinfo.get('preferred_username'), session_id)

# Append session_id to CLI redirect:
return redirect(f"{cli_callback_url}?auth=success&user={user_b64}&session_id={session_id}")
```

#### 3.4b GUI login also stores `team_ids` and registers session index

In `auth_callback` GUI branch, add `team_ids` to `session_data` and call `register_session()`.

#### 3.4c `/api/auth/user` returns `session_id`

Modify `get_current_user()` to include `session_id` in the response:

```python
session_id = session.get('session_id')
return jsonify({
    'user': user,
    'authenticated': True,
    'access_token': session_data.get('access_token'),
    'session_id': session_id,  # NEW
})
```

This allows the UI to extract `session_id` and set a cookie on its own domain.

#### 3.4d Logout cleans up session index

In the logout handler, call `unregister_session(self.redis_store, username, session_id)` before deleting the Redis key.

### 3.5 Identity Service — Team Membership Sync (`shared-resources/identity/teams/service.py`)

**Purpose:** When team membership changes (create, update, delete), update `team_ids` in all affected users' Redis sessions.

**Key logic in `TeamService`:**

```python
def _sync_team_memberships_to_sessions(self, affected_usernames: set[str]) -> None:
    """Re-compute and update team_ids in Redis for all affected users."""
    for username in affected_usernames:
        try:
            teams = self._repo.find_by_member(username)
            team_ids = [t.team_id for t in teams]
            update_team_ids_for_user(self._redis_store, username, team_ids)
        except Exception:
            logger.warning("Failed to sync team memberships to Redis for %s", username)
```

**Wiring:** `TeamService` needs a `redis_store` parameter (injected from `build_auth_stack` via `flask_app.py`). It already receives `user_groups_cache` which uses the same Redis store.

**Call sites:**

| Method | Affected users |
|:---|:---|
| `create()` | All members in the new team |
| `update()` (when `members` changes) | Union of old members and new members |
| `delete()` | All members of the deleted team |

### 3.6 Session ID Transport — No Nginx Change Required

**Background on why the nginx proxy_pass was originally proposed and why it is NOT needed:**

The current nginx config for `/api3` uses a `307 redirect` to `IDENTITY_HOST`:

```nginx
location ~ /api3/(.*)$ {
   return 307 ${IDENTITY_HOST}/api/${DOLLAR}1${DOLLAR}is_args${DOLLAR}args;
}
```

This means the browser navigates **directly** to the Identity service host. Any session cookie set by Identity lands on Identity's domain, not on the nginx/UI domain. Since `/api2` (MAS), `/api1` (RAG), and `/api4` (Backend) are on the nginx domain, the browser would **not** automatically send Identity's cookie to those services.

A `proxy_pass` change would make Identity sit behind nginx, so cookies would be on the same domain. **However, this is NOT required.** Here's why:

The UI already calls Identity's `/api/auth/user` after login to fetch user info. By adding `session_id` to that response (§3.4c), the UI can extract it and set a **separate cookie** on its own domain:

```javascript
document.cookie = `session_id=${sessionId}; path=/; secure; samesite=strict`;
```

This cookie lives on the nginx domain and is automatically sent to `/api1`, `/api2`, `/api4`. The `session_id` is an opaque UUID validated against Redis — it is **not** a credential that needs to be signed or HttpOnly. This is strictly more secure than the current approach where `X-Authenticated-User` carries a guessable username set by JavaScript.

**For the CLI:** The CLI receives `session_id` from the login callback and sets it as a cookie in its `requests.Session()` — no nginx involvement.

### 3.7 MAS Changes

#### 3.7a `AppContainer` — add `redis_kv_store` (`multi-agent/bootstrap/container.py`)

```python
from global_utils.redis import RedisKVStore, build_redis_client

# In AppContainer.__init__:
self.redis_kv_store: RedisKVStore | None = None
redis_url = get_redis_url()
if redis_url:
    self.redis_kv_store = RedisKVStore(build_redis_client(cfg.redis_db))
```

#### 3.7b Flask app factory — session cookie config (`multi-agent/adapters/inbound/flask/flask_app.py`)

CORS must allow the `Cookie` header and credentials:

```python
CORS(app, resources={r"/api/*": {
    "origins": "*",
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "Cookie"],
    "supports_credentials": True,
}})
```

#### 3.7c MAS decorator migration (`multi-agent/adapters/inbound/flask/decorators.py`)

Replace `with_authenticated_user` and `with_require_identity_authorization` with wrappers:

```python
from global_utils.flask.decorators import require_team_session, G_USER_ID, G_TEAM_ID

def _get_redis_store():
    return current_app.container.redis_kv_store

def _get_session_id():
    return request.cookies.get("session_id") or session.get("session_id")

def _get_team_id():
    body = request.get_json(silent=True) or {}
    identity_type = (request.args.get("identityType") or body.get("identityType") or "user").lower()
    if identity_type == "team":
        return request.args.get("userId") or body.get("userId") or ""
    return None

# Primary decorator for most MAS endpoints:
mas_require_session = require_team_session(
    get_redis_store=_get_redis_store,
    get_session_id=_get_session_id,
)

# Decorator for team-scoped endpoints:
mas_require_team_session = require_team_session(
    get_redis_store=_get_redis_store,
    get_session_id=_get_session_id,
    get_team_id=_get_team_id,
    # team_membership_checker omitted — uses UserSessionData.is_team_member() from Redis
)
```

**Endpoint migration:** Each endpoint currently receives `authenticated_user` or `identity` as kwargs. After migration:

- Replace `@with_authenticated_user` → `@mas_require_session`, read `g.user_id`
- Replace `@with_require_identity_authorization` → `@mas_require_team_session`, read `g.user_id` + `g.team_id`
- Build `Identity` domain objects from `g` values where needed (thin helper):

```python
def identity_from_g() -> Identity:
    team_id = getattr(g, G_TEAM_ID, None)
    user_id = getattr(g, G_USER_ID, "")
    if team_id:
        return Identity.team(team_id)
    return Identity.user(user_id)
```

### 3.8 RAG Changes

#### 3.8a `AppContainer` — add `redis_kv_store` (`rag/bootstrap/app_container.py`)

Same pattern as MAS — instantiate `RedisKVStore` from `build_redis_client`.

#### 3.8b Flask app factory — store container ref (`rag/bootstrap/flask_app.py`)

The RAG app factory currently does not attach a container to `app`. Add `app.container = app_container` so decorators can access `redis_kv_store`.

#### 3.8c Endpoint migration

| Current | After |
|:---|:---|
| `logged_in_user` in body (pipelines.py) | `@rag_require_session` decorator, read `g.user_id` |
| `username` in body (docs.py, terms_approval.py) | `@rag_require_session` decorator, read `g.user_id` |
| `loggedInUser` in query (docs.py) | `@rag_require_session` decorator, read `g.user_id` |

Each RAG module defines a thin wrapper:

```python
from global_utils.flask.decorators import require_team_session

def _get_redis_store():
    return current_app.container.redis_kv_store

rag_require_session = require_team_session(
    get_redis_store=_get_redis_store,
    get_session_id=lambda: request.cookies.get("session_id") or session.get("session_id"),
)
```

Body/query `username`/`logged_in_user` parameters are removed from endpoint schemas. Handlers read `g.user_id` instead.

### 3.9 Backend Changes

#### 3.9a `AppContainer` — add `redis_kv_store` (`backend/core/app_container.py`)

Same pattern.

#### 3.9b Endpoint migration (`backend/api/flask/endpoints/admin_config.py`)

Replace `@require_admin_access(_get_current_user, _is_admin)` with:

```python
@backend_require_session   # validates session, sets g.user_id
@require_admin_access(lambda req: getattr(g, "user_id", None), _is_admin)
```

Remove `X-Username` / `X-User-Id` header reading. The admin check now uses `g.user_id` from the session.

### 3.10 CLI Changes

#### 3.10a `auth/login.py` — parse `session_id` from callback

Extract `session_id` from the callback URL query params alongside existing `user` data.

#### 3.10b `auth/session.py` — store `session_id`

Add `session_id` to the session JSON at `~/.unifai/session.json`:

```python
data = {
    "username": user_info.get("username", ""),
    # ... existing fields ...
    "session_id": user_info.get("session_id", ""),
    "expires_at": ...,
}
```

#### 3.10c `api/base.py` — send cookie instead of header

```python
# Remove AUTH_USER_HEADER and _auth_headers()
# Add:
def set_session_id(self, session_id: str) -> None:
    self._session_id = session_id
    self.session.cookies.set("session_id", session_id, domain="", path="/")
```

All `_get`, `_post`, `_delete` methods stop sending `X-Authenticated-User`.

#### 3.10d `bootstrap.py` — wire session_id

```python
user_info = ensure_authenticated()
client.set_authenticated_user(user_info["username"])   # keep for display
client.set_session_id(user_info.get("session_id", "")) # NEW — for auth
```

### 3.11 UI Changes

#### 3.11a `AuthContext.tsx` — store `session_id`, set cookie

After the `/api3/auth/user` call returns:

```typescript
// In the auth check effect, after receiving user + session_id:
if (data.session_id) {
  document.cookie = `session_id=${data.session_id}; path=/; secure; samesite=strict`;
}
```

Remove `setAuthenticatedUser(user?.username)` call.

#### 3.11b `axiosAgentConfig.ts` — remove header, enable credentials

```typescript
const axiosInstance = axios.create({
  baseURL: '/api2',
  timeout: 300000,
  withCredentials: true,  // sends session_id cookie
});
// Remove the X-Authenticated-User interceptor entirely.
// Remove setAuthenticatedUser export.
```

#### 3.11c RAG / Backend axios clients — same pattern

Ensure `withCredentials: true` is set. Remove any `X-Username` / `X-User-Id` header setting.

---

## 4. Data Flow

### 4.1 Web UI — Login + MAS Request

```
Browser → /api3/auth/login → 307 redirect → Identity host
  → Keycloak OAuth flow
  → Identity /api/auth/callback (GUI branch):
    1. Generate session_id = UUID
    2. Fetch user's teams → team_ids
    3. HSET identity:session:{id} {username, tokens, team_ids, ...}
    4. SADD identity:user_sessions:{username} {id}
    5. Set Flask session cookie (on Identity domain)
    6. Redirect → frontend/?auth=success

Browser → /api3/auth/user (307 → Identity):
  → Identity reads session from cookie → returns {user, session_id, ...}
  → UI stores session_id
  → document.cookie = "session_id={id}; path=/; secure; samesite=strict"

Browser → /api2/sessions/user.session.create:
  → Cookie: session_id={id} (on nginx domain, auto-sent)
  → MAS Flask → @mas_require_team_session:
    1. request.cookies.get("session_id") → id
    2. HGETALL identity:session:{id} → UserSessionData (incl. team_ids)
    3. has_auth_credentials() + expiry check → True
    4. g.user_id = data.username, g.identity_session = data
    5. get_team_id() → team_id from body (if identityType=team)
    6. data.is_team_member(team_id) → check from Redis data
    7. g.team_id = team_id
  → Handler reads g.user_id, g.team_id → 200
```

### 4.2 CLI — Login + MAS Request

```
CLI → browser → Identity /api/auth/login?state={cli, callbackUrl}
  → Keycloak OAuth
  → Identity callback (CLI branch):
    1. Back-channel token exchange with Keycloak
    2. Generate session_id, fetch teams
    3. HSET identity:session:{id} + SADD user_sessions index
    4. Redirect → localhost/callback?auth=success&user=...&session_id={id}

CLI → parse session_id → save to ~/.unifai/session.json
CLI → requests.Session() with cookie session_id={id}
  → MAS /api/sessions/user.session.create
  → @mas_require_team_session → same Redis validation → 200
```

### 4.3 Team Membership Change

```
Admin → Identity /api/teams/team.update (add user "alice" to team "team-x")
  → TeamService.update():
    1. Update team in MongoDB
    2. Compute affected_usernames = old_members ∪ new_members
    3. For each affected username:
       a. Find all their teams from MongoDB
       b. Collect team_ids
       c. For each session_id in SMEMBERS identity:user_sessions:{username}:
          - HSET identity:session:{sid} team_ids = json.dumps(team_ids)

Next request from "alice":
  → @require_team_session reads updated team_ids from Redis → access granted
```

---

## 5. Risk & Reliability

### 5a. Edge Cases & Failure Modes

| Risk / Edge Case | Mitigation |
|:---|:---|
| **Deployment coordination:** All modules must deploy together | Deployment is coordinated with end-user notification (per product owner decision). All modules release simultaneously. |
| **Session expiry during long operations:** 10h session expires mid-execution of a MAS workflow | Decorator checks `session_expires_at`. For long-running async operations (Temporal workers), the session check happens at the HTTP entry point only — workflow execution continues independently once started. |
| **Stale team_ids in Redis:** Race condition between team update and next user request | `TeamService._sync_team_memberships_to_sessions()` runs synchronously inside the team update transaction. The window is sub-second. For strict consistency, the decorator can fall back to `IdentityClient.is_member()` if `UserSessionData.team_ids` is empty (backward compat with sessions created before this feature). |
| **Session index cleanup:** `identity:user_sessions:{username}` accumulates expired session IDs | `update_team_ids_for_user()` cleans up stale entries (checks `EXISTS` before `HSET`, removes missing keys from the SET). Additionally, the SET entries can be given a TTL matching the session TTL. |
| **Unprotected MAS endpoints** (`session.chat.get`, `session.state.get`, etc.) | Currently unprotected and remain so. They operate on `sessionId` knowledge, not user identity. Flag for a follow-up security audit. |
| **UserSessionData backward compatibility:** Existing Redis sessions lack `team_ids` | `team_ids` defaults to `[]` in the model. If empty, the decorator falls back to `team_membership_checker` callable (which can use `IdentityClient.is_member()`). New sessions include `team_ids` from the start. |
| **Multiple concurrent sessions per user:** A user can be logged in from browser + CLI simultaneously | Supported by design. Each session gets its own `session_id` in the `identity:user_sessions:{username}` SET. Team updates propagate to all sessions. |

### 5b. External Dependency Failure Modes

| Dependency | Failure Scenario | Behavior | Degradation Path |
|:---|:---|:---|:---|
| **Redis** | Connection refused / timeout | Noisy: decorator catches exception, returns **500** `ACCESS_CONTROL_ERROR` | No graceful degradation — Redis is required for all session validation. Log error with full traceback. |
| **Redis** | Session key expired / missing | Silent from Redis | Returns **401** `AUTHENTICATION_REQUIRED`. User re-authenticates. |
| **Identity pod** (team sync) | 503 / timeout during team update | Noisy: `_sync_team_memberships_to_sessions` logs warning | Team update in MongoDB succeeds; Redis session not updated. Next login will pick up correct teams. Existing sessions use stale team_ids until session expiry (max 10h). |
| **Keycloak** | Down during CLI/GUI login | Noisy: OAuth callback fails | Login flow returns error. Existing sessions remain valid. |

### 5c. Local Development & Partial-Access Deployment

| Dependency | Local Dev Strategy | Deployment Without This Dependency |
|:---|:---|:---|
| **Redis** | `unifai-dev` starts Redis locally. Tests use `InMemoryRedisStore` / `fakeredis` to mock `hget`/`hset`/`sadd`/`smembers`. | Feature is unusable without Redis — all services already require Redis for other functions. |
| **Identity pod** | `DevIdentityProvider` bypasses auth (`requires_authentication=False`). Tests seed Redis with `valid_session_data()` including `team_ids`. | `DevIdentityProvider` returns `is_member=True`. System functions normally for development. |
| **Team membership sync** | Not needed locally — `DevIdentityProvider` allows all access. Tests seed team_ids directly in Redis. | Team updates won't propagate to sessions if Identity pod is unavailable. Sessions use login-time team snapshot. |

---

## 6. Open Questions

- [x] **Phased migration:** All modules migrate simultaneously. Deployment coordination with end-user notification handles the cutover. *(Resolved)*
- [x] **CI/scripting `UNIFAI_USER` env var:** API token support will be a separate story (see §7 below for the plan). *(Resolved — separate story)*
- [x] **Nginx proxy_pass for `/api3`:** Not needed. Identity returns `session_id` in the `/api/auth/user` response; the UI sets a cookie on its own domain. See §3.6 for full explanation. *(Resolved — no nginx change)*
- [x] **RAG and Backend scope:** In scope. All modules adopt `@require_team_session` with the same pattern. *(Resolved)*
- [x] **Team membership caching:** Team IDs are stored in the Redis session hash (`UserSessionData.team_ids`), updated on team create/update/delete via `TeamService`. *(Resolved)*
- [x] **Cookie name:** Use `session_id` as the cookie name across all clients. All session data (user profile, tokens, team_ids) resides in the Redis hash keyed by `session_id`. *(Resolved)*
- [ ] **Session expiry enforcement in the decorator:** The new decorator checks `session_expires_at`. Required changes to existing code:
  - `UserSessionData.has_auth_credentials()` currently only checks `username + access_token`. The decorator adds a **separate** expiry check — no change to the existing method.
  - Identity's `_refresh_access_token()` updates `token_expires_at` but NOT `session_expires_at` — this is correct (session lifetime is absolute).
  - All services must handle the new `SESSION_EXPIRED` error type in their error handling.
- [ ] **CORS `origins` tightening:** Currently MAS, RAG, and Backend use `"*"` for CORS origins. With `withCredentials: true`, browsers require the server to echo a specific origin (not `"*"`). All Flask CORS configs need to be updated with the actual frontend URL.

---

## 7. Future Story: API Token Support

> *This section outlines the plan for a follow-up story to support non-interactive (CI/scripting) callers via API tokens, replacing the current `UNIFAI_USER` env var bypass.*

### Concept

API tokens are long-lived opaque credentials that map to a user identity in Redis, using the **same session infrastructure** as interactive sessions.

### How it works

1. **Token generation:** A new endpoint on Identity (e.g., `POST /api/auth/token.create`) generates an API token (UUID or cryptographic random), creates a Redis session hash under `identity:session:{token_id}` with the user's identity and team memberships, and sets a long TTL (configurable, e.g. 90 days).
2. **Token storage:** The token is stored in MongoDB (for revocation, listing) and the session hash in Redis (for runtime validation). The MongoDB record maps `token_id → username, created_at, expires_at, revoked`.
3. **Token usage:** CI/scripts send the token as `Cookie: session_id=<token_id>` or `Authorization: Bearer <token_id>`. The `@require_team_session` decorator's `get_session_id` reads it from either source — **no decorator changes needed**. The Redis lookup is identical to interactive sessions.
4. **Token revocation:** Delete the Redis key and mark as revoked in MongoDB.
5. **Team membership sync:** API token sessions are included in `identity:user_sessions:{username}` SET, so team updates propagate automatically.
6. **Difference from interactive sessions:** No `access_token`/`refresh_token` (no Keycloak involvement). `has_auth_credentials()` would need adjustment — check `username` only for API tokens, or add a `token_type` field to the Redis hash.

### Why this reuses existing infrastructure

The `@require_team_session` decorator doesn't care whether the `session_id` came from an interactive login or an API token — it just looks up the Redis hash and validates the contents. The only new code is the token CRUD endpoints and a modified `has_auth_credentials()` that accepts token-type sessions.

---

## 7. Reviewer Feedback

<!-- This section is populated by the Design Reviewer (Phase 2). Do not fill manually. -->

### Verdict: **[PENDING]**

### Critical Findings

### Architectural Violations

### Efficiency Concerns

### Duplication & Reusability Issues

### Risks to Existing System

### Local Dev & Partial-Access Deployment Findings

### Recommended Improvements

### Revision Items

- [ ] ...
