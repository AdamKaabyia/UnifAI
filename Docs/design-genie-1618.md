# Architecture Design Review (ADR)

**Feature Name:** [GENIE-1618 — Implement @require_team_session Decorator for Redis Session & Team Identity Validation](https://redhat.atlassian.net/browse/GENIE-1618)

**Author:** Pipeline Designer | **Date:** 2026-06-03 | **Priority:** High

---

## 1. Executive Summary

| Section | Details |
|:---|:---|
| **Problem Statement** | UnifAI currently uses an unvalidated `X-Authenticated-User` header for MAS authentication — any client can impersonate any user. The CLI bypasses Redis sessions entirely. RAG trusts `logged_in_user` in request bodies. Backend trusts `X-Username` headers. There is no server-side session validation outside the Identity service itself, creating a system-wide security gap. |
| **High-Level Solution** | Create a `@require_team_session` decorator factory in `global_utils` that validates callers against Redis-backed server sessions and authorizes team-level access via `IdentityClient.is_member()` (backed by MongoDB). Move Identity behind nginx (`proxy_pass` instead of 307 redirect) so the session cookie flows to all services on the same domain. Modify the Identity CLI login flow to create Redis sessions. Migrate **all modules** (MAS, RAG, Backend, CLI, UI) to session-based auth, eliminating `X-Authenticated-User`, `X-Username`, and body-param identity. |
| **Success Metrics** | All service endpoints validate requests against Redis sessions. `X-Authenticated-User` and `X-Username` headers are eliminated from production request paths. CLI sends `session_id` cookie. Team membership is checked via `IdentityClient` (MongoDB as single source of truth, 45s in-memory process cache). New unit tests achieve ≥ 90 % coverage of the decorator. |

---

## 2. Affected Components

| Layer | Component | Action (New / Modified) | File Path |
|:---|:---|:---|:---|
| Domain | `UserSessionData` model | Modified — add `user_id` property alias | `global_utils/src/global_utils/redis/session_model.py` |
| Application | `TeamMembershipCache` | **New** — Redis-backed team cache (follows `UserGroupsCache` pattern) | `global_utils/src/global_utils/redis/team_cache.py` (or in `identity_client.py`) |
| Application | `IdentityClient` team cache | Modified — replace in-memory dict with `TeamMembershipCache` (Redis) | `global_utils/src/global_utils/identity_client.py` |
| Application | `require_team_session` decorator factory | **New** | `global_utils/src/global_utils/flask/decorators.py` |
| Application | `_validate_session` helper | **New** — extracted from `require_identity_session` for reuse | `global_utils/src/global_utils/flask/decorators.py` |
| Adapter — UI / Frontend | Axios MAS interceptor | Modified — remove `X-Authenticated-User` header and interceptor | `ui/client/src/http/axiosAgentConfig.ts` |
| Adapter — UI / Frontend | `AuthContext` | Modified — remove `setAuthenticatedUser` call | `ui/client/src/contexts/AuthContext.tsx` |
| Adapter — UI / Frontend | Axios Backend client | Modified — remove `X-Username` header | `ui/client/src/api/adminConfig.ts` |
| Adapter — API / Inbound (MAS) | Flask app factory | Modified — add session cookie config matching Identity | `multi-agent/adapters/inbound/flask/flask_app.py` |
| Adapter — API / Inbound (MAS) | MAS Flask decorators | Modified — replace header-based decorators with `require_team_session` wrappers | `multi-agent/adapters/inbound/flask/decorators.py` |
| Adapter — API / Inbound (MAS) | All MAS endpoint files | Modified — read `g.user_id` / `g.team_id` instead of kwargs | `multi-agent/adapters/inbound/flask/endpoints/*.py` |
| Adapter — API / Inbound (RAG) | RAG Flask app factory | Modified — add `app.container` ref for `redis_kv_store`, add session cookie config | `rag/bootstrap/flask_app.py` |
| Adapter — API / Inbound (RAG) | RAG endpoint files | Modified — add `@require_team_session`, remove body-param identity | `rag/infrastructure/http/pipelines.py`, `docs.py`, `terms_approval.py`, `slack.py` |
| Adapter — API / Inbound (Backend) | Backend Flask app factory | Modified — add `redis_kv_store` to container, add session cookie config | `backend/api/flask/flask_app.py` |
| Adapter — API / Inbound (Backend) | Backend admin config endpoints | Modified — replace `X-Username` / `require_admin_access` with `require_team_session` + admin check | `backend/api/flask/endpoints/admin_config.py` |
| Adapter — Outbound (MAS) | `AppContainer` | Modified — add `redis_kv_store` | `multi-agent/bootstrap/container.py` |
| Adapter — Outbound (RAG) | `AppContainer` | Modified — add `redis_kv_store` | `rag/bootstrap/app_container.py` |
| Adapter — Outbound (Backend) | `AppContainer` | Modified — add `redis_kv_store` | `backend/core/app_container.py` |
| Adapter — Outbound (Identity) | `AuthManager.auth_callback` CLI path | Modified — create Redis session + return `session_id` | `shared-resources/identity/utils/auth_manager.py` |
| Adapter — Outbound (Identity) | `AuthManager._oauth_callback_redirect_uri` | Modified — use `frontend_url/api3/auth/callback` | `shared-resources/identity/utils/auth_manager.py` |
| Adapter — Outbound (CLI) | `MASClient` | Modified — send `session_id` cookie instead of `X-Authenticated-User` header | `cli/unifai_cli/api/base.py` |
| Adapter — Outbound (CLI) | CLI auth session | Modified — store `session_id` from login flow | `cli/unifai_cli/auth/session.py`, `cli/unifai_cli/auth/login.py` |
| Config / Infra | Nginx config | **Modified** — change `/api3` from 307 redirect to `proxy_pass` | `ui/deployment/nginx.conf.template` |
| Config / Infra | Identity postsync script | **New** — discovers Identity service, creates `identity-svc-config` ConfigMap | `helm/scripts/identity-postsync.sh` |
| Config / Infra | Identity helmfile | Modified — add postsync hook | `helm/identity.yaml.gotmpl` |
| Config / Infra | UI Helm values | Modified — add `identity-svc-config` to `globalConfigMapNames` | `helm/ui/values.yaml` |
| Config / Infra | Keycloak client | Modified — add nginx callback URL to allowed redirect URIs | External config (one-time admin change) |
| Tests | Decorator unit tests | **New** | `global_utils/tests/test_team_session_decorator.py` |

---

## 3. Technical Design

### 3.1 `UserSessionData` — Convenience Alias (`global_utils/redis/session_model.py`)

**Purpose:** Add a `user_id` property alias so consumers can use `data.user_id` instead of `data.username`, aligning with the `g.user_id` naming convention used by the decorator.

```python
class UserSessionData(BaseModel):
    # ... existing fields unchanged ...

    @property
    def user_id(self) -> str | None:
        return self.username
```

No schema or Redis key changes. The session hash remains: `username`, `email`, `name`, `sub`, `access_token`, `refresh_token`, timestamps.

### 3.2 Team Membership — MongoDB + Redis Cache via `IdentityClient`

**Decision:** Team membership is persisted in MongoDB (single source of truth). The decorator checks membership via `IdentityClient.is_member()` which is passed as the `team_membership_checker` callback. Team lookups are cached in Redis following the existing `UserGroupsCache` pattern.

**Data flow:**

```
Rover/LDAP groups → cached in Redis (UserGroupsCache, 1h TTL)
                  → used by TeamService to resolve group-type team members
                  → teams persisted in MongoDB (source of truth)
                  → team membership cached in Redis (new TeamMembershipCache)
                  → read by IdentityClient.is_member()
```

**Current state:** `IdentityClient` caches team lookups in a per-process Python `dict` (45s TTL, `threading.Lock`). This means each Gunicorn worker has its own isolated cache, and cache is lost on pod restart.

**Improvement:** Move the team cache to Redis, matching the `UserGroupsCache` pattern that already exists for Rover/LDAP groups:

```python
class TeamMembershipCache:
    """Redis-backed cache for user team memberships (follows UserGroupsCache pattern)."""

    KEY_PREFIX = "unifai:user_teams:"

    def __init__(self, store: RedisKVStore, ttl: int = 300):
        self._store = store
        self._ttl = ttl

    def get_team_ids(self, username: str) -> list[str] | None:
        raw = self._store.get(f"{self.KEY_PREFIX}{username}")
        return json.loads(raw) if raw else None

    def set_team_ids(self, username: str, team_ids: list[str]) -> None:
        self._store.set(f"{self.KEY_PREFIX}{username}", json.dumps(team_ids), ttl_seconds=self._ttl)

    def invalidate(self, username: str) -> None:
        self._store.delete(f"{self.KEY_PREFIX}{username}")
```

**`IdentityClient.is_member()` updated flow:**
1. Check Redis cache (`TeamMembershipCache.get_team_ids(username)`)
2. Cache hit → check if `team_id` in cached list → return result
3. Cache miss → HTTP GET to Identity pod → MongoDB query → cache result in Redis (5 min TTL)
4. Cache miss on specific team (team not in cached list) → invalidate cache + retry with fresh data (handles newly created teams)

**Benefits over in-memory dict:**
- Shared across all Gunicorn workers (consistent view)
- Survives pod restarts
- Consistent with existing `UserGroupsCache` pattern
- Longer TTL is safe (5 min vs 45s) because Redis cache is shared and can be explicitly invalidated

**Identity pod unavailable:** `is_member()` returns `True` (fails open) when `base_url` is not configured — unchanged from current behavior.

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
| `get_session_id` | Extracts `session_id` from the request | `lambda: session.get("session_id")` |
| `get_team_id` | Extracts `team_id` from the request (return `None` to skip team check) | `None` (no team check) |
| `team_membership_checker` | `(username, team_id) -> bool` — called when `get_team_id` returns a value | `None` (skip team check if no checker provided) |

**Default `get_session_id` behavior:** Uses `session.get("session_id")` which reads from Flask's signed session cookie. This works for the **browser flow** because all services share the same `SECRET_KEY` (via `shared-secret`) and the session cookie is now on the same domain (via nginx proxy_pass). For the **CLI flow**, each service's wrapper overrides `get_session_id` to also check a raw cookie fallback (see §3.8c).

**Key logic:**

1. Call `get_session_id()` → `sid`. If `None` → **401** `AUTHENTICATION_REQUIRED`.
2. Call `get_identity_session(get_redis_store(), sid)` → `UserSessionData`.
3. If `None` or not `has_auth_credentials()` → **401** `AUTHENTICATION_REQUIRED`.
4. Check `session_expires_at` — if expired → **401** `SESSION_EXPIRED`.
5. Set `g.identity_session = data` and `g.user_id = data.username`.
6. Call `get_team_id()` → `team_id`. If not `None` and `team_membership_checker` is provided:
   a. Call `team_membership_checker(data.username, team_id)`.
   b. If `False` → **403** `TEAM_ACCESS_DENIED`.
   c. If `True` → set `g.team_id = team_id`.
7. Any exception → **500** `ACCESS_CONTROL_ERROR`.
8. Call wrapped function.

**Session expiry check** (step 4) — aligns with Identity's `is_authenticated()` which checks `session_expires_at`. The existing `has_auth_credentials()` only checks presence of `username` + `access_token`, not expiry. The new decorator adds the expiry check.

**Refactoring:** Extract session validation (steps 1–5) into a private `_validate_session()` helper shared between `require_identity_session` and `require_team_session` to eliminate duplication.

### 3.4 Nginx — Proxy Pass for Identity (VERIFIED & IMPLEMENTED)

**Purpose:** Route Identity requests through nginx so the session cookie is set on the same domain as all other services. This was verified in staging — the `session` cookie now reaches `/api1`, `/api2`, and `/api4` automatically.

**Previous state:** `/api3` used a `307 redirect` to `IDENTITY_HOST`, causing the session cookie to land on Identity's domain (`unifai-identity-tag-ai--playground...`). The browser did **not** send this cookie to other services on the nginx domain (`unifai-ui-tag-ai--playground...`).

**Changes implemented:**

**3.4a `ui/deployment/nginx.conf.template`:**

```nginx
location /api3/ {
   proxy_pass http://${IDENTITY_SVC_IP}:${IDENTITY_SVC_PORT}/api/;
   proxy_set_header Host              ${DOLLAR}host;
   proxy_set_header X-Real-IP         ${DOLLAR}remote_addr;
   proxy_set_header X-Forwarded-For   ${DOLLAR}proxy_add_x_forwarded_for;
   proxy_set_header X-Forwarded-Proto ${DOLLAR}scheme;
   proxy_cookie_path / /;
}
```

> **Note on env var naming:** The Identity K8s Service is named `identity`, so Kubernetes auto-generates `IDENTITY_PORT=tcp://...` which collides with a plain `IDENTITY_PORT` ConfigMap key. The env vars are therefore prefixed as `IDENTITY_SVC_IP` and `IDENTITY_SVC_PORT` to avoid the collision.

**3.4b `helm/scripts/identity-postsync.sh` (new file):**

```bash
#!/bin/bash
set +e
echo "Starting identity postsync hook..."
source "$(dirname "$0")/postsync-lib.sh"

IDENTITY_ADDR=$(wait_for_ip identity) || exit 1
IDENTITY_PORT=$(wait_for_port identity) || exit 1
IDENTITY_IP=$(wait_for_service_name identity) || exit 1

create_or_update_configmap identity-svc-config \
  --from-literal=IDENTITY_SVC_ADDR="$IDENTITY_ADDR" \
  --from-literal=IDENTITY_SVC_PORT="$IDENTITY_PORT" \
  --from-literal=IDENTITY_SVC_IP="$IDENTITY_IP"
```

**3.4c `helm/identity.yaml.gotmpl`** — added postsync hook referencing the new script.

**3.4d `helm/ui/values.yaml`** — added `identity-svc-config` to `globalConfigMapNames`.

**3.4e `shared-resources/identity/utils/auth_manager.py`** — `redirect_uri` changed to use the public nginx URL:

```python
def _oauth_callback_redirect_uri(self) -> str:
    if config.backend_env == "production":
        return f"{config.frontend_url.rstrip('/')}/api3/auth/callback"
    return f"http://{config.hostname_local}:{config.port}/api/auth/callback"
```

**3.4f Keycloak** — the nginx callback URL must be added to the Keycloak client's allowed redirect URIs (one-time admin change).

**Why this eliminates CORS issues:** Since all services are now behind the same nginx origin, browser requests are same-origin. No `withCredentials: true` is needed, no CORS `Access-Control-Allow-Origin` changes are needed. The existing `origins: "*"` CORS config works fine for same-origin requests.

### 3.5 Shared `SECRET_KEY` for Flask Session Cookie Decoding

**Purpose:** For all services to decode the Flask `session` cookie set by Identity, they must share the same `SECRET_KEY`.

**Current state:** All services already share the key. The `shared-secret` Kubernetes Secret (created by `shared-resources-postsync.sh`) includes `SECRET_KEY` sourced from Vault. All service deployments mount `shared-secret`. All Flask app factories read `secret_key` from config:

```python
app.secret_key = config.get("secret_key", os.urandom(24))
```

`SharedConfig` (base class for all `AppConfig` classes) reads `SECRET_KEY` from the environment via pydantic-settings. Since all pods mount `shared-secret`, they all get the same value.

**No additional changes needed** — the shared key mechanism is already in place.

**Session cookie config alignment:** MAS, RAG, and Backend must configure session cookie settings to match Identity, so that if Flask re-signs the cookie on a response, the attributes remain consistent:

```python
app.config.update({
    'SESSION_COOKIE_SECURE': True,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'None',
})
```

### 3.6 Identity Service — CLI Redis Session (`shared-resources/identity/utils/auth_manager.py`)

**Purpose:** The CLI login path currently bypasses Redis session creation. Modify it to create a full Redis session and return `session_id` to the CLI.

In `auth_callback` CLI branch, after successful Keycloak token exchange:

```python
session_id = str(uuid.uuid4())
session_created_at = datetime.now()
session_expires_at = session_created_at + timedelta(hours=config.permanent_session_lifetime)

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
}

ttl_seconds = self._ttl_seconds_until_session_expires(session_expires_at.timestamp())
self.redis_store.hset(identity_session_key(session_id), session_data, ttl_seconds=ttl_seconds)

svc = current_app.extensions.get('team_service')
if svc:
    svc.cache_user_groups(userinfo.get('preferred_username'), token.get('access_token'))

return redirect(f"{cli_callback_url}?auth=success&user={user_b64}&session_id={session_id}")
```

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

Add session cookie configuration to match Identity, and remove `X-Authenticated-User` from CORS headers:

```python
app.config.update({
    'SESSION_COOKIE_SECURE': True,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'None',
})

CORS(app, resources={r"/api/*": {
    "origins": "*",
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
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
    # Flask session (browser — signed cookie decoded by Flask)
    # then raw cookie fallback (CLI — sends session_id as plain cookie)
    return session.get("session_id") or request.cookies.get("session_id")

def _get_team_id():
    body = request.get_json(silent=True) or {}
    identity_type = (request.args.get("identityType") or body.get("identityType") or "user").lower()
    if identity_type == "team":
        return request.args.get("userId") or body.get("userId") or ""
    return None

def _check_team_membership(username: str, team_id: str) -> bool:
    return current_app.container.identity_provider.is_member(username, team_id)

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
    team_membership_checker=_check_team_membership,
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

#### 3.8b Flask app factory — store container ref + session cookie config (`rag/bootstrap/flask_app.py`)

The RAG app factory currently does not attach a container to `app`. Add `app.container = app_container` so decorators can access `redis_kv_store`. Add session cookie configuration matching Identity.

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
    get_session_id=lambda: session.get("session_id") or request.cookies.get("session_id"),
)
```

Body/query `username`/`logged_in_user` parameters are removed from endpoint schemas. Handlers read `g.user_id` instead.

### 3.9 Backend Changes

#### 3.9a `AppContainer` — add `redis_kv_store` (`backend/core/app_container.py`)

Same pattern.

#### 3.9b Flask app factory — session cookie config + remove `X-Username` CORS header

Add session cookie config. Update CORS to remove `X-Username` / `X-User-Id` from `allow_headers`.

#### 3.9c Endpoint migration (`backend/api/flask/endpoints/admin_config.py`)

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

All `_get`, `_post`, `_delete` methods stop sending `X-Authenticated-User`. The CLI sends `session_id` as a **raw cookie** (not Flask-signed). The service-side `get_session_id` wrappers check `request.cookies.get("session_id")` as a fallback after `session.get("session_id")`, so the CLI's raw cookie is picked up.

#### 3.10d `bootstrap.py` — wire session_id

```python
user_info = ensure_authenticated()
client.set_authenticated_user(user_info["username"])   # keep for display
client.set_session_id(user_info.get("session_id", "")) # NEW — for auth
```

### 3.11 UI Changes

#### 3.11a `axiosAgentConfig.ts` — remove `X-Authenticated-User` header

```typescript
const axiosInstance = axios.create({
  baseURL: '/api2',
  timeout: 300000,
});
// Remove the X-Authenticated-User interceptor entirely.
// Remove setAuthenticatedUser export.
// No withCredentials needed — same-origin requests include cookies by default.
```

#### 3.11b `AuthContext.tsx` — remove `setAuthenticatedUser`

Remove the `useEffect` that calls `setAuthenticatedUser(user?.username ?? '')` and the import.

#### 3.11c `adminConfig.ts` — remove `X-Username` header

Remove explicit `X-Username` header setting on admin config API calls.

---

## 4. Data Flow

### 4.1 Web UI — Login + MAS Request

```
Browser → nginx /api3/auth/login
  → proxy_pass → Identity pod /api/auth/login
  → Identity redirects to Keycloak (redirect_uri = nginx/api3/auth/callback)
  → Keycloak authenticates → redirects to nginx/api3/auth/callback
  → proxy_pass → Identity pod /api/auth/callback (GUI branch):
    1. Generate session_id = UUID
    2. HSET identity:session:{id} {username, tokens, timestamps}
    3. Set Flask session cookie (on nginx domain ✓ — same domain for all services)
    4. Redirect → frontend/?auth=success

Browser → /api2/sessions/user.session.create:
  → Cookie: session=<Flask-signed {session_id: id}> (auto-sent, same domain)
  → proxy_pass → MAS Flask
    → MAS decodes Flask session cookie (shared SECRET_KEY)
    → @mas_require_team_session:
      1. session.get("session_id") → id
      2. HGETALL identity:session:{id} → UserSessionData
      3. has_auth_credentials() + expiry check → True
      4. g.user_id = data.username, g.identity_session = data
      5. get_team_id() → team_id from body (if identityType=team)
      6. IdentityClient.is_member(username, team_id) → MongoDB (45s cache)
      7. g.team_id = team_id
    → Handler reads g.user_id, g.team_id → 200
```

### 4.2 CLI — Login + MAS Request

```
CLI → browser → nginx /api3/auth/login?state={cli, callbackUrl}
  → proxy_pass → Identity → Keycloak OAuth
  → Identity callback (CLI branch):
    1. Back-channel token exchange with Keycloak
    2. Generate session_id
    3. HSET identity:session:{id} {username, tokens, timestamps}
    4. Redirect → localhost/callback?auth=success&user=...&session_id={id}

CLI → parse session_id → save to ~/.unifai/session.json
CLI → requests.Session() with raw cookie session_id={id}
  → MAS /api/sessions/user.session.create
  → @mas_require_team_session:
    1. session.get("session_id") → None (raw cookie, not Flask-signed)
    2. request.cookies.get("session_id") → id (fallback)
    3. HGETALL → same Redis + IdentityClient validation → 200
```

### 4.3 Team Membership Check (Per-Request)

```
Request to team-scoped endpoint with identityType=team, userId=team-x:
  → @require_team_session decorator:
    1. Redis HGETALL identity:session:{id} → UserSessionData (username = "alice")
    2. team_membership_checker("alice", "team-x")
       → IdentityClient.is_member("alice", "team-x")
         → Redis GET unifai:user_teams:alice → cache hit? Check list → return
         → Redis cache miss?
           → HTTP GET Identity /api/teams/teams.list?userId=alice
             → Identity queries MongoDB teams collection
             → (Rover group resolution uses UserGroupsCache in Redis)
             → Returns team list
           → Redis SET unifai:user_teams:alice (5 min TTL)
           → team-x in list? True/False
         → team-x not in cached list?
           → Invalidate Redis cache → retry with fresh HTTP call
    3. True → g.team_id = "team-x" → 200
       False → 403 TEAM_ACCESS_DENIED
```

Team membership changes in MongoDB are picked up within 5 minutes (Redis cache TTL) or immediately on cache miss (e.g., newly created team triggers cache invalidation + retry). The Redis cache is shared across all Gunicorn workers, unlike the previous per-process in-memory dict.

---

## 5. Risk & Reliability

### 5a. Edge Cases & Failure Modes

| Risk / Edge Case | Mitigation |
|:---|:---|
| **Deployment coordination:** All modules must deploy together | Deployment is coordinated with end-user notification (per product owner decision). All modules release simultaneously. |
| **Session expiry during long operations:** 10h session expires mid-execution of a MAS workflow | Decorator checks `session_expires_at`. For long-running async operations (Temporal workers), the session check happens at the HTTP entry point only — workflow execution continues independently once started. |
| **Team membership cache staleness:** IdentityClient cache has 45s TTL | Acceptable for most use cases. On cache miss for a specific team, the cache is invalidated and retried with a fresh HTTP call — newly created teams are recognized immediately. |
| **Unprotected MAS endpoints** (`session.chat.get`, `session.state.get`, etc.) | Currently unprotected and remain so. They operate on `sessionId` knowledge, not user identity. Flag for a follow-up security audit. |
| **Multiple concurrent sessions per user:** A user can be logged in from browser + CLI simultaneously | Supported — each session has its own `session_id` and Redis hash. Team checks go through IdentityClient (same MongoDB data regardless of session). |
| **Flask session cookie re-signed by MAS/RAG/Backend:** If a service modifies the Flask session, it re-signs the cookie on response | Services must NOT write to `flask.session`. The decorator only reads `session.get("session_id")`. Enforce via code review. Session cookie config (Secure, HttpOnly, SameSite) is aligned across all services. |

### 5b. External Dependency Failure Modes

| Dependency | Failure Scenario | Behavior | Degradation Path |
|:---|:---|:---|:---|
| **Redis** | Connection refused / timeout | Noisy: decorator catches exception, returns **500** `ACCESS_CONTROL_ERROR` | No graceful degradation — Redis is required for all session validation. Log error with full traceback. |
| **Redis** | Session key expired / missing | Silent from Redis | Returns **401** `AUTHENTICATION_REQUIRED`. User re-authenticates. |
| **Identity pod** (team check) | 503 / timeout on `is_member()` HTTP call | Noisy: `IdentityClient.get_team_ids` logs exception, returns `frozenset()` | Team check fails → user denied access (403). Logs provide visibility. |
| **Identity pod** | Not configured (`base_url` empty) | Silent: `is_member()` returns `True` (fails open) | Acceptable for local dev. In production, `IdentityPodProvider` requires `identity_host` to be set. |
| **Keycloak** | Down during CLI/GUI login | Noisy: OAuth callback fails | Login flow returns error. Existing sessions remain valid. |

### 5c. Local Development & Partial-Access Deployment

| Dependency | Local Dev Strategy | Deployment Without This Dependency |
|:---|:---|:---|
| **Redis** | `unifai-dev` starts Redis locally. Tests use `InMemoryRedisStore` / `fakeredis` to mock `hget`/`hset`. | Feature is unusable without Redis — all services already require Redis for other functions. |
| **Identity pod** | `DevIdentityProvider` bypasses auth (`requires_authentication=False`, `is_member=True`). Tests mock `team_membership_checker`. | `DevIdentityProvider` allows all access. System functions normally for development. |
| **Nginx proxy_pass** | Local dev: `unifai-dev` starts services on localhost with direct access; no nginx involved. | If nginx is not configured with proxy_pass, the session cookie won't reach backend services. The proxy_pass change is a production deployment requirement. |

---

## 6. Open Questions

- [x] **Phased migration:** All modules migrate simultaneously. Deployment coordination with end-user notification handles the cutover. *(Resolved)*
- [x] **CI/scripting `UNIFAI_USER` env var:** API token support will be a separate story (see §7 below for the plan). *(Resolved — separate story)*
- [x] **Nginx proxy_pass for `/api3`:** Required and implemented. Verified in staging — the session cookie now reaches all services. See §3.4 for full details. *(Resolved)*
- [x] **RAG and Backend scope:** In scope. All modules adopt `@require_team_session` with the same pattern. *(Resolved)*
- [x] **Team membership storage:** MongoDB is the single source of truth. `IdentityClient.is_member()` checks membership with a 45s in-memory process cache. No team data in Redis. *(Resolved)*
- [x] **Cookie name:** Use Flask's `session` cookie (contains signed `{session_id: uuid}`). User session data resides in the Redis hash keyed by the `session_id`. *(Resolved)*
- [x] **CORS changes:** Not needed. With proxy_pass, all services are on the same origin. Same-origin requests include cookies by default and do not trigger CORS preflight. *(Resolved)*
- [ ] **Session expiry enforcement in the decorator:** The new decorator checks `session_expires_at`. Required changes to existing code:
  - `UserSessionData.has_auth_credentials()` currently only checks `username + access_token`. The decorator adds a **separate** expiry check — no change to the existing method.
  - Identity's `_refresh_access_token()` updates `token_expires_at` but NOT `session_expires_at` — this is correct (session lifetime is absolute).
  - All services must handle the new `SESSION_EXPIRED` error type in their error handling.
- [ ] **Keycloak redirect URI:** Verify that `https://unifai-ui-tag-ai--playground.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com/api3/auth/callback` is added to the Keycloak client's allowed redirect URIs (one-time admin change, required for production).

---

## 7. Future Story: API Token Support

> *This section outlines the plan for a follow-up story to support non-interactive (CI/scripting) callers via API tokens, replacing the current `UNIFAI_USER` env var bypass.*

### Concept

API tokens are long-lived opaque credentials that map to a user identity in Redis, using the **same session infrastructure** as interactive sessions.

### How it works

1. **Token generation:** A new endpoint on Identity (e.g., `POST /api/auth/token.create`) generates an API token (UUID or cryptographic random), creates a Redis session hash under `identity:session:{token_id}` with the user's identity, and sets a long TTL (configurable, e.g. 90 days).
2. **Token storage:** The token is stored in MongoDB (for revocation, listing) and the session hash in Redis (for runtime validation). The MongoDB record maps `token_id → username, created_at, expires_at, revoked`.
3. **Token usage:** CI/scripts send the token as `Cookie: session_id=<token_id>` or `Authorization: Bearer <token_id>`. The `@require_team_session` decorator's `get_session_id` reads it from either source — **no decorator changes needed**. The Redis lookup is identical to interactive sessions.
4. **Token revocation:** Delete the Redis key and mark as revoked in MongoDB.
5. **Team membership:** Checked via `IdentityClient.is_member()` — same as interactive sessions. No special handling needed.
6. **Difference from interactive sessions:** No `access_token`/`refresh_token` (no Keycloak involvement). `has_auth_credentials()` would need adjustment — check `username` only for API tokens, or add a `token_type` field to the Redis hash.

### Why this reuses existing infrastructure

The `@require_team_session` decorator doesn't care whether the `session_id` came from an interactive login or an API token — it just looks up the Redis hash and validates the contents. The only new code is the token CRUD endpoints and a modified `has_auth_credentials()` that accepts token-type sessions.

### Implementation effort estimate

**~1-2 hours** total. The decorator/validation infrastructure already supports API tokens natively. The only code change in each service's auth resolution is extending the session ID extraction to also check the `Authorization` header:

```python
def _resolve_authenticated_user():
    # Try session cookie first (browser/CLI)
    sid = session.get("session_id")
    # Fall back to API token (CI/scripts)
    if not sid:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            sid = auth_header[7:].strip()

    if not sid:
        return None, _AUTH_REQUIRED_ERROR

    data, err = _validate_session(_get_redis_store, lambda: sid)
    ...
```

This is **3-5 lines** per service. The rest of the work is the Identity CRUD API:
- `POST /api/auth/token.create` — generate token, store in Redis + MongoDB
- `GET /api/auth/token.list` — list user's tokens
- `DELETE /api/auth/token.revoke` — delete Redis key, mark revoked in MongoDB

No changes to `TeamMembershipCache`, `IdentityClient`, or any endpoint code.

---

## 8. Reviewer Feedback

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
