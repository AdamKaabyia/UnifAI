# GENIE-1576 — Vault-Backed Credential Store for Multi-Agent

**Ticket:** [GENIE-1576](https://redhat.atlassian.net/browse/GENIE-1576)
**Status:** Design v3
**Author:** Pipeline Designer Agent
**Date:** 2026-05-07 | **Last updated:** 2026-05-11

---

## 1. Overview

### 1.1 Problem Statement

The multi-agent service stores user-managed credentials (OAuth access/refresh tokens, MCP API keys, MCP bearer tokens) in the MongoDB `credentials` collection via `MongoCredentialStore`. Sensitive fields (`access_token`, `refresh_token`) are encrypted at rest using application-level Fernet when `credential_encryption_key` is set. While functional, this approach has limitations:

- **Single storage backend** — `MongoCredentialStore` is the only `CredentialStore` adapter; there is no config toggle to select an alternative backend.
- **No external secret store** — credentials live entirely in MongoDB, meaning a MongoDB compromise exposes all encrypted tokens (Fernet key + ciphertext are both reachable from the same breach).
- **No runtime caching** — every `find_by_server` call hits MongoDB directly, adding latency to every authenticated HTTP call from MCP providers and tools.
- **No Vault audit trail** — secret access is invisible to the company's centralized audit infrastructure.

### 1.2 Proposed Solution

Add a **`VaultCredentialStore`** adapter that implements the existing `CredentialStore` ABC, backed by HashiCorp Vault KV v2 with an optional Redis read-through cache. The container selects between `MongoCredentialStore` and a composite `VaultCredentialStore` (which uses Mongo as fallback) based on a config flag. The existing `AuthService`, `AuthHandle`, strategies, and all consumers remain **completely unchanged** — only the wired adapter differs.

### 1.3 Scope

**In scope — this story covers ONLY:**

- Secrets that flow through the `CredentialStore` port (i.e., via `AuthService`)
- OAuth2 tokens (`access_token`, `refresh_token`) stored in the `credentials` collection
- MCP API keys (moved to `credentials` by `McpProviderConfig.on_pre_save`)
- MCP bearer tokens (moved to `credentials` by `McpProviderConfig.on_pre_save`)
- A new `VaultCredentialStore` adapter inside `multi-agent`
- A `CachedCredentialStore` decorator for Redis caching
- A config flag to select credential store backend
- Vault AppRole authentication and token renewal
- Redis cache invalidation on writes and token refresh

**See Section 9 (Out of Scope) for everything explicitly excluded.**

### 1.4 Success Criteria

- `VaultCredentialStore` passes all existing `CredentialStore` contract tests
- Credentials are replicated to Vault on every `upsert` (create and update)
- Read path: Redis cache hit → Vault → MongoDB fallback (when in composite mode)
- Deleting a credential cleans up Vault and Redis
- OAuth token refresh (via `AuthService.attempt_recovery`) propagates to Vault and invalidates cache
- Vault is optional — if disabled or unavailable, the system falls back to `MongoCredentialStore` seamlessly
- Zero changes to `AuthService`, `AuthHandle`, `AuthCredential`, strategies, or any consumer code

---

## 2. Affected Components

| Layer | Component | Action | File Path |
|-------|-----------|--------|-----------|
| Port (Domain) | `CredentialStore` | **Unchanged** | `multi-agent/lib/mas/core/auth/credentials/ports.py` |
| Port (Domain) | `StoredCredential` model | **Unchanged** | `multi-agent/lib/mas/core/auth/credentials/models.py` |
| Adapter (Outbound) | `VaultCredentialStore` | **New** | `multi-agent/adapters/outbound/vault/credential_store.py` |
| Adapter (Outbound) | `CachedCredentialStore` | **New** | `multi-agent/adapters/outbound/cache/cached_credential_store.py` |
| Adapter (Outbound) | `MongoCredentialStore` | **Unchanged** | `multi-agent/adapters/outbound/mongo/auth_token_repository.py` |
| Config | `AppConfig` | **Modified** — add Vault + cache config fields | `multi-agent/config/app_config.py` |
| Bootstrap | `AppContainer` | **Modified** — conditional store wiring | `multi-agent/bootstrap/container.py` |
| Service | `AuthService` | **Unchanged** | `multi-agent/lib/mas/core/auth/service.py` |
| Dependencies | `requirements.txt` | **Modified** — add `hvac` | `multi-agent/requirements.txt` |

---

## 3. Technical Design

### 3.1 Architecture — How It Fits the Existing Hexagon

The existing credential flow is:

```
MCP tools / elements
    ↓ (AuthCredential protocol)
AuthHandle
    ↓
AuthService  ← owns CRUD, recovery, onboarding
    ↓ (CredentialStore ABC)
MongoCredentialStore  ← only adapter today
```

After this story, the adapter layer becomes selectable:

```
AuthService  ← UNCHANGED
    ↓ (CredentialStore ABC)
    ├── "mongo"       → MongoCredentialStore (as today)
    ├── "vault"       → CachedCredentialStore → VaultCredentialStore
    └── "vault+mongo" → CachedCredentialStore → VaultCredentialStore
                              ↓ (fallback on read miss/failure)
                         MongoCredentialStore
```

`AuthService` calls the same `upsert`, `find_by_server`, `delete`, `update_status` methods regardless of which adapter is wired. The `CredentialStore` port and all domain models remain **completely untouched**.

### 3.2 `VaultCredentialStore` — New Adapter

**File:** `multi-agent/adapters/outbound/vault/credential_store.py`

**Purpose:** Implements `CredentialStore` using Vault KV v2 as the primary secret backend, with optional MongoDB fallback for reads.

**Vault path convention:**

```
apps/automation-and-tools/unifai/{env}/runtime/credentials/{user_id}/{server_identifier_hash}
```

Where `server_identifier_hash` is a SHA-256 truncated to 16 hex chars (Vault paths must be safe — no slashes, colons, or special chars from URLs).

**Interface (implements existing ABC):**

```python
class VaultCredentialStore(CredentialStore):

    def __init__(
        self,
        vault_url: str,
        vault_role_id: str,
        vault_secret_id: str,
        vault_base_path: str,           # e.g. "apps/automation-and-tools/unifai/staging/runtime/credentials"
        vault_ca_cert: str = "",        # path to CA cert for TLS verification
        mongo_fallback: Optional[CredentialStore] = None, # to be removed as we don't need the fall back
        encryption_key: str = "",       # to be removed as we don't need the fall back , Fernet key for Mongo fallback writes
    ):
        ...

    def upsert(self, credential: StoredCredential) -> None:
        """Write to Vault. Also write to Mongo fallback (if configured) for durability."""

    def find_by_server(
        self, user_id: str, server_identifier: str, scheme_type: str = "",
    ) -> Optional[StoredCredential]:
        """Read from Vault. On Vault failure, fall back to Mongo."""

    def delete(self, user_id: str, server_identifier: str) -> None:
        """Delete from Vault. Also delete from Mongo fallback."""

    def update_status(self, user_id: str, server_identifier: str, status: str) -> None:
        """Read-modify-write in Vault. Also update Mongo fallback."""
```

**Vault KV v2 storage format:**

Each credential is stored as a single Vault secret at its path. The secret data is a flat dict of the `StoredCredential` model fields:

```json
{
  "id": "abc123",
  "user_id": "john",
  "server_identifier": "https://accounts.google.com",
  "access_token": "ya29.a0A...",
  "refresh_token": "1//0eX...",
  "token_type": "Bearer",
  "expires_at": "2026-05-11T16:00:00Z",
  "scopes": ["openid", "email"],
  "status": "active",
  "scheme_type": "oauth2",
  "created_at": "2026-05-10T12:00:00Z",
  "updated_at": "2026-05-11T12:00:00Z"
}
```

Vault encrypts all data at rest (Vault's seal/unseal barrier encryption). No application-level Fernet is needed for the Vault path — Vault itself provides the encryption. The Mongo fallback path still uses Fernet via the existing `MongoCredentialStore`.

**Vault AppRole authentication and token lifecycle:**

```python
def _ensure_authenticated(self) -> None:
    """Check Vault token validity; re-authenticate if expired or close to expiry."""
    if self._token_valid():
        return
    resp = self._client.auth.approle.login(
        role_id=self._role_id,
        secret_id=self._secret_id,
    )
    self._token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=resp["auth"]["lease_duration"]
    )

def _token_valid(self, buffer_seconds: int = 120) -> bool:
    """Return True if the Vault token has >buffer_seconds remaining."""
    if self._token_expires_at is None:
        return False
    return self._token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=buffer_seconds)
```

Every public method calls `_ensure_authenticated()` before Vault I/O.

**Write path (`upsert`):**

1. Serialize `StoredCredential` to dict (JSON-safe)
2. `_ensure_authenticated()`
3. Write to Vault KV v2 at the credential's path
4. If `mongo_fallback` is set, also call `mongo_fallback.upsert(credential)` for durability
5. On Vault write failure: log error, write to Mongo fallback only, raise no exception (degrade gracefully)

**Read path (`find_by_server`):**

1. `_ensure_authenticated()`
2. Read from Vault KV v2
3. On success: deserialize to `StoredCredential`, return
4. On Vault failure (network, auth, not found): if `mongo_fallback` is set, delegate to `mongo_fallback.find_by_server()`
5. On both miss: return `None`

**Delete path:**

1. `_ensure_authenticated()`
2. Delete from Vault KV v2 (metadata delete, permanently removes all versions)
3. If `mongo_fallback` is set, also call `mongo_fallback.delete()`

**Error handling philosophy:** Vault failures on **writes** are logged but don't crash the request — the Mongo fallback ensures the credential is persisted. Vault failures on **reads** silently fall back to Mongo. This gives "Vault as replication target" semantics: Vault adds security and auditability, but the system never breaks if Vault is temporarily down.

### 3.3 `CachedCredentialStore` — Redis Read-Through Cache

**File:** `multi-agent/adapters/outbound/cache/cached_credential_store.py`

**Purpose:** Decorator around any `CredentialStore` that adds a Redis read-through cache for `find_by_server`. All other methods (`upsert`, `delete`, `update_status`) delegate to the inner store and **invalidate the cache**.

```python
class CachedCredentialStore(CredentialStore):

    def __init__(
        self,
        inner: CredentialStore,
        redis_client: redis.Redis,
        encryption_key: str,          # REQUIRED — refuse to start without it
        cache_ttl_seconds: int = 300, # fixed 5-minute TTL
        key_prefix: str = "cred_cache:", #might change after discussion with Odai/Lina
    ):
        if not encryption_key:
            raise ValueError("CachedCredentialStore requires an encryption_key")
        self._inner = inner
        self._redis = redis_client
        self._cipher = _FieldCipher(encryption_key)
        self._ttl = cache_ttl_seconds
        self._prefix = key_prefix
```

**Cache key format:** `cred_cache:{user_id}:{sha256(server_identifier)[:16]}:{scheme_type}`

**`find_by_server` (read path):**

1. Build cache key
2. `GET` from Redis
3. On hit: decrypt with Fernet, deserialize to `StoredCredential`, return
4. On miss: delegate to `self._inner.find_by_server()`
5. On inner hit: encrypt with Fernet, `SETEX` to Redis with TTL, return the model
6. On inner miss: return `None` (don't cache negative results)

**`upsert` (write path — invalidate + write-through):**

1. Delegate to `self._inner.upsert(credential)`
2. Build cache key from credential fields
3. Encrypt and `SETEX` the new value (write-through, so the next read is a cache hit)

**`delete` (write path — invalidate):**

1. Delegate to `self._inner.delete()`
2. `DEL` the cache key

**`update_status` (write path — invalidate):**

1. Delegate to `self._inner.update_status()`
2. `DEL` the cache key (don't write-through — status-only update may not have full model)

**Why mandatory encryption:** Even though Redis is internal, the `credentials` collection contains OAuth tokens and API keys. The existing `RedisFlowStateStore` already encrypts pending OAuth state with Fernet. The cache must follow the same standard — secrets in Redis are always encrypted.

**`_FieldCipher` reuse:** The `_FieldCipher` class from `MongoCredentialStore` is duplicated here for now. A future story (see Section 9) can extract it to a shared location. For this story, minimizing blast radius means keeping the duplication.

### 3.4 Configuration

**New fields in `AppConfig`** (`multi-agent/config/app_config.py`):

```python
class AppConfig(SharedConfig):
    # ... existing fields ...

    # Credential store backend: "mongo" (default), "vault", or "vault+mongo"
    credential_store_backend: str = "mongo"

    # Vault connection (used when credential_store_backend != "mongo")
    vault_url: str = ""
    vault_role_id: str = ""
    vault_secret_id: str = ""
    vault_base_path: str = "apps/automation-and-tools/unifai/staging/runtime/credentials"
    vault_ca_cert: str = ""

    # Credential cache (used when credential_store_backend != "mongo")
    credential_cache_ttl: int = 300  # seconds
```

**Backend modes:**

| `credential_store_backend` | Behaviour | When to use |
|---------------------------|-----------|-------------|
| `"mongo"` (default) | `MongoCredentialStore` only — **identical to today** | Local dev, tests, pre-migration |
| `"vault"` | `CachedCredentialStore` → `VaultCredentialStore` (no Mongo fallback) | Full Vault commitment (after migration validated) |
| `"vault+mongo"` | `CachedCredentialStore` → `VaultCredentialStore` with `MongoCredentialStore` as fallback | **Recommended for rollout** — zero risk |

### 3.5 Container Wiring

**Modified section in `AppContainer.__init__`** (`multi-agent/bootstrap/container.py`):

```python
# ── Credential Store ──────────────────────────────────────────

mongo_cred_store = MongoCredentialStore(
    mongodb_ip=cfg.mongodb_ip,
    mongodb_port=cfg.mongodb_port,
    db_name=cfg.mongo_db,
    coll_name=cfg.credentials_coll,
    encryption_key=cfg.credential_encryption_key,
)

if cfg.credential_store_backend == "mongo":
    self.credential_store = mongo_cred_store

elif cfg.credential_store_backend in ("vault", "vault+mongo"):
    from outbound.vault.credential_store import VaultCredentialStore

    vault_store = VaultCredentialStore(
        vault_url=cfg.vault_url,
        vault_role_id=cfg.vault_role_id,
        vault_secret_id=cfg.vault_secret_id,
        vault_base_path=cfg.vault_base_path,
        vault_ca_cert=cfg.vault_ca_cert,
        mongo_fallback=mongo_cred_store if cfg.credential_store_backend == "vault+mongo" else None, #removed
        encryption_key=cfg.credential_encryption_key, #removed
    )

    redis_url = get_redis_url()
    if redis_url and cfg.credential_encryption_key:
        import redis as redis_lib
        from outbound.cache.cached_credential_store import CachedCredentialStore
        redis_client = redis_lib.Redis.from_url(redis_url)
        self.credential_store = CachedCredentialStore(
            inner=vault_store,
            redis_client=redis_client,
            encryption_key=cfg.credential_encryption_key,
            cache_ttl_seconds=cfg.credential_cache_ttl,
        )
    else:
        self.credential_store = vault_store
else:
    raise ValueError(f"Unknown credential_store_backend: {cfg.credential_store_backend!r}")
```

**What does NOT change in container wiring:**

- `AuthService` construction — still receives `self.credential_store`
- `RedisFlowStateStore` construction — unchanged (separate from credential cache)
- `MongoServerConfigStore` — unchanged (client configs are NOT credentials; see Section 9)
- All strategy registrations, action registrations, service bindings

### 3.6 Refresh & Token Lifecycle

This is the key integration point that makes the design work seamlessly with the existing auth system.

**OAuth token refresh — already works, no code changes needed:**

The existing flow when a token expires:

1. `AuthHandle.get_headers()` calls `AuthService.get_headers()`
2. `AuthService` calls `self._store.find_by_server()` → gets expired `StoredCredential`
3. `cred.is_valid()` returns `False` (expired)
4. `AuthService.attempt_recovery()` calls `OAuth2Strategy.attempt_recovery()`
5. Strategy calls `_refresh()` which exchanges `refresh_token` for new tokens
6. On success: `AuthService` builds a new `StoredCredential` and calls `self._store.upsert(updated)`

**Step 6 is the key:** `self._store` is now `CachedCredentialStore` → `VaultCredentialStore`. The `upsert` call:
- Writes the new tokens to **Vault**
- Writes to **Mongo** fallback (if `vault+mongo`) # no fallback, 
- **Write-through** updates the **Redis** cache

No changes to `AuthService` or any strategy. The port abstraction means the refresh flow "just works" with the new backend.

**API key updates — same path:**

When a user updates an MCP API key, `McpProviderConfig.on_pre_save` calls `AuthService.save_credential()` → `self._store.upsert()` → same write-through path.

**Vault AppRole token renewal:**

The `VaultCredentialStore` manages its own Vault auth token internally:

- On first use: authenticates via AppRole, caches the Vault token and its `lease_duration`
- Before each Vault operation: calls `_ensure_authenticated()` which checks remaining TTL
- If token is within 2 minutes of expiry: re-authenticates automatically
- If re-authentication fails: logs error, falls back to Mongo (in `vault+mongo` mode)

**Redis cache staleness prevention:**

| Event | Cache action |
|-------|-------------|
| `upsert` (create or update, including refresh) | Write-through: encrypt + `SETEX` new value |
| `delete` | `DEL` cache key |
| `update_status` | `DEL` cache key (conservative — force next read to hit backend) |
| TTL expiry (5 min default) | Automatic eviction by Redis |

This means the cache is **never stale** for writes originating from this process. For multi-process deployments (multiple multiagent pods), the fixed 5-minute TTL provides eventual consistency — a credential updated by pod A will be stale in pod B's cache for at most 5 minutes.

---

## 4. Data Flow

### 4.1 Write — New Credential (OAuth complete or API key save)

```
AuthService.save_credential(cred) / AuthService.complete()
    ↓
CachedCredentialStore.upsert(cred)
    ↓
VaultCredentialStore.upsert(cred)
    ├── Vault KV v2 PUT (primary write)
    └── MongoCredentialStore.upsert(cred) [fallback, if vault+mongo]
        └── Fernet-encrypts access_token, refresh_token → MongoDB
    ↓
Redis SETEX (Fernet-encrypted serialized StoredCredential, TTL=300s)
```

### 4.2 Read — Get Headers for Authenticated Request

```
AuthHandle.get_headers()
    ↓
AuthService.get_headers()
    ↓
CachedCredentialStore.find_by_server(user_id, server_id)
    ↓
Redis GET cred_cache:{user_id}:{hash}:{scheme}
    ├── HIT  → Fernet-decrypt → StoredCredential → return
    └── MISS ↓
VaultCredentialStore.find_by_server(user_id, server_id)
    ├── Vault KV v2 GET → deserialize → StoredCredential
    │   → cache in Redis (Fernet-encrypted, SETEX TTL)
    │   → return
    └── Vault FAILURE ↓
MongoCredentialStore.find_by_server(user_id, server_id) [if vault+mongo]
    → Fernet-decrypt → StoredCredential
    → cache in Redis
    → return
```

### 4.3 Token Refresh (OAuth2)

```
AuthHandle.get_token() → AuthService.get_valid_token()
    ↓ cred.is_valid() == False
AuthService.attempt_recovery()
    ↓
OAuth2Strategy.attempt_recovery(cred, config)
    ↓ _refresh() → POST to token endpoint with refresh_token
    ↓ returns RecoveryResult(recovered=True, new_token_set=...)
AuthService: builds updated StoredCredential with new tokens
    ↓
self._store.upsert(updated)  ← same as Write flow (4.1)
    → Vault updated, Mongo updated, Redis write-through
```

### 4.4 Delete

```
AuthService.delete_credential(user_id, server_id)
    ↓
CachedCredentialStore.delete(user_id, server_id)
    ↓
VaultCredentialStore.delete(user_id, server_id)
    ├── Vault KV v2 DELETE (metadata delete — all versions)
    └── MongoCredentialStore.delete(user_id, server_id) [if vault+mongo]
    ↓
Redis DEL cred_cache:{user_id}:{hash}:{scheme}
```

### 4.5 Local Development (unchanged)

```
credential_store_backend = "mongo" (default)
    ↓
MongoCredentialStore only — identical to today
No Vault, no Redis cache, no new dependencies needed
```

---

## 5. Edge Cases & Risks

| Edge Case | Handling |
|-----------|----------|
| **Vault unavailable on write** | Log error, write to Mongo fallback only. Credential is safe. Vault will be out of sync until next `upsert` for that credential. |
| **Vault unavailable on read** | Fall back to Mongo (in `vault+mongo` mode). Return `None` in `vault`-only mode if both Vault and cache miss. |
| **Redis unavailable** | Skip cache on read (go to Vault/Mongo directly). Skip cache write-through on upsert. Log warning. |
| **Both Vault and Redis down** | Degrades to Mongo-only behavior (in `vault+mongo` mode). Identical to today. |
| **Vault AppRole token expires** | `_ensure_authenticated()` re-authenticates automatically before each operation. |
| **Vault AppRole secret_id revoked** | Re-authentication fails. All Vault operations fail. Falls back to Mongo in `vault+mongo` mode. Alerts should fire on repeated auth failures. |
| **Concurrent refresh from multiple pods** | Two pods may refresh the same OAuth token simultaneously. Both write to Vault/Mongo. Last-writer-wins semantics — both write valid tokens, no data loss. The "losing" pod's token may expire slightly sooner. Acceptable. |
| **Read-modify-write race on `update_status`** | `update_status` reads from Vault, modifies status field, writes back. Two concurrent calls could lose one update. Mitigated: `update_status` only changes the `status` field, which is idempotent for the same value. |
| **Server identifier with special chars** | Hashed to SHA-256 for the Vault path. Mongo keeps the original (URL-normalized). |
| **`scheme_type` filtering in Vault** | Vault stores one credential per path. The Vault adapter must encode `scheme_type` into the path (or store it in the secret data and filter post-read). Design uses the latter for simplicity — filter after reading. |
| **Migration from Mongo to Vault** | See Section 7 (Migration Plan). |
| **`_FieldCipher` duplication** | Duplicated in `CachedCredentialStore`. Acceptable for v1 — extracted to shared utility in a future story (Section 9). |

---

## 6. Testing Strategy

| Test Level | What | How |
|------------|------|-----|
| **Unit** | `VaultCredentialStore` against mock `hvac.Client` | Verify `upsert`/`find_by_server`/`delete`/`update_status` call correct Vault paths |
| **Unit** | `CachedCredentialStore` against mock Redis + mock inner store | Verify cache hit, cache miss, write-through, invalidation |
| **Unit** | `VaultCredentialStore` Mongo fallback | Mock Vault failure → verify Mongo fallback is called |
| **Unit** | Vault token renewal | Mock expired token → verify re-authentication |
| **Integration** | Full stack with `credential_store_backend=vault+mongo` | Docker Compose with Vault dev server, Redis, MongoDB |
| **Contract** | `VaultCredentialStore` passes all existing `CredentialStore` tests | Existing test suite unchanged, parameterized for both backends |
| **E2E** | OAuth flow end-to-end with Vault backend | Login → token stored in Vault → token refresh → verify Vault updated |

---

## 7. Migration Plan

### Phase 1 — Deploy with `vault+mongo` (shadow mode)

1. Add Vault config to staging environment
2. Set `credential_store_backend=vault+mongo`
3. Deploy. All existing credentials remain in Mongo. New writes go to both.
4. Verify: Vault audit logs show writes. Reads fall back to Mongo for pre-existing credentials.

### Phase 2 — Backfill existing credentials to Vault

1. One-time migration script: read all credentials from Mongo, `upsert` each through `VaultCredentialStore`
2. Verify: Vault has all credentials. Reads now hit Vault (via cache).
3. Script is idempotent — safe to re-run.

### Phase 3 — Validate and promote

1. Monitor for 1-2 weeks in `vault+mongo` mode
2. Verify no Vault fallback-to-Mongo reads in logs (all credentials are in Vault)
3. Optionally switch to `credential_store_backend=vault` (Vault-only, no Mongo writes)
4. Or stay in `vault+mongo` permanently for safety

### Phase 4 — Production rollout

1. Repeat Phases 1-3 for production
2. Coordinate with GENIE-948 deployment for Vault connectivity

### Rollback at any phase

Set `credential_store_backend=mongo` → instant rollback to current behavior. No data loss — Mongo always has a copy in `vault+mongo` mode.

---

## 8. Open Questions

1. **Vault path layout** — Should runtime credential paths live under the same `apps/automation-and-tools/unifai/{env}/` prefix as GENIE-948 deploy-time secrets, or a separate mount? Using the same prefix simplifies policy management but requires careful path separation.

2. **Multi-pod cache coherence** — The 5-minute fixed TTL is a simple eventual-consistency model. If tighter consistency is needed (e.g., immediate cross-pod invalidation after a key rotation), Redis Pub/Sub or a shorter TTL could be used. Is 5 minutes acceptable?

3. **`server_configs` collection** — `ClientConfig` objects (OAuth client registration — `client_id`, `client_secret`) are stored via `ServerConfigStore` in the `server_configs` collection, currently in plaintext. These are NOT covered by this story. Should they be a fast-follow?

4. **Vault policy granularity** — Should the runtime AppRole have read+write access to all credential paths, or should there be per-user or per-scheme path restrictions?

---

## 9. Out of Scope (Future Stories)

This section explicitly documents what was considered but **deliberately excluded** from GENIE-1576 to keep the scope focused and the blast radius minimal.

### 9.1 Move to `global_utils`

**Previous design iterations (v1, v2) proposed** placing `SecretProvider`, `VaultSecretProvider`, `CachedSecretProvider`, and `FieldCipher` in `global_utils` so all services (multi-agent, backend, RAG, identity) could use them.

**Why deferred:** Moving to `global_utils` before proving the design inside `multi-agent` risks fragmenting the code and creating a premature abstraction. The `CredentialStore` port exists only in `multi-agent` today. The correct sequence is:
1. **This story:** Prove Vault integration works within `multi-agent`, aligned with the existing `CredentialStore` port
2. **Follow-up story:** Extract the proven Vault adapter and cache decorator into `global_utils` as a reusable `CredentialStore` adapter, once other services (backend, RAG) also need it

**What a future `global_utils` extraction would include:**
- `VaultCredentialStore` → `global_utils/adapters/vault/credential_store.py`
- `CachedCredentialStore` → `global_utils/adapters/cache/cached_credential_store.py`
- `_FieldCipher` → `global_utils/crypto/field_cipher.py` (eliminating the current duplication between `MongoCredentialStore` and `RedisFlowStateStore`)
- Vault config fields → `SharedConfig` (so all services can configure Vault)

### 9.2 Non-Credential Secrets (`cfg_dict` fields)

**What:** LLM API keys (`BaseLLMConfig.api_key`), A2A bearer tokens (`A2AAgentNodeConfig.bearer_token`), SSH tool passwords, and other secrets stored in `Resource.cfg_dict` via `MongoResourceRepository`.

**Why excluded:** These secrets flow through `ResourcesService` → `MongoResourceRepository`, NOT through `CredentialStore` / `AuthService`. They have a different storage model (embedded in a JSON dict, keyed by resource ID, no `user_id` + `server_identifier` composite key). Handling them requires:
- A separate `SecretFieldProvider` port (key→value string storage)
- Changes to `ResourcesService.create()` / `update()` to externalize secret fields
- Potentially a `SecretRef` marker pattern or field-level interception
- UI coordination for placeholder/actual value handling on update

This is a fundamentally different problem from credential store swapping and should be its own story.

**MCP bearer tokens and API keys are partially covered** because `McpProviderConfig.on_pre_save` already moves them from `cfg_dict` into the `credentials` collection via `AuthService.save_credential()`. So for MCP secrets specifically, this story does cover their Vault storage — once they land in `credentials`, they go through `CredentialStore`.

### 9.3 `ServerConfigStore` / `ClientConfig` in Vault

**What:** OAuth client registration data (`client_id`, `client_secret`, endpoints) stored in the `server_configs` collection.

**Why excluded:** `ServerConfigStore` is a separate port from `CredentialStore`. The `client_secret` field is currently stored in plaintext. Moving it to Vault requires a separate adapter (`VaultServerConfigStore`) and is lower priority than user tokens.

### 9.4 `_FieldCipher` Extraction

**What:** The Fernet encryption utility class `_FieldCipher` is currently private in `MongoCredentialStore` and will be duplicated in `CachedCredentialStore`.

**Why excluded:** Extracting it to a shared module (either within `multi-agent` or in `global_utils`) is a clean-up task that doesn't affect behavior. It should be done as part of the `global_utils` extraction (9.1).

### 9.5 TLS for Internal Connections (Redis, MongoDB)

**What:** All internal connections (App → Redis, App → MongoDB) are currently unencrypted `redis://` and `mongodb://` schemes.

**Why excluded:** This is an infrastructure concern that affects all services, not just the credential store. See Related Stories (Appendix A) for details.

### 9.6 MongoDB Client-Side Field Level Encryption (CSFLE)

**What:** MongoDB's native CSFLE feature, which encrypts fields at the driver level before they reach the server.

**Why excluded:** The codebase uses application-level Fernet, not CSFLE. Adopting CSFLE would require a separate MongoDB Key Management Service (KMS), driver reconfiguration, and schema changes. It's orthogonal to Vault integration.

---

## 10. Design Review (Phase 2) — From Original v1 Design

The original v1 design proposed a standalone `SecretProvider` port with `SecretRef` markers stored in MongoDB. A thorough Phase 2 review identified critical issues that drove the v3 redesign. These findings are preserved here for traceability — they explain **why** the design evolved to use the existing `CredentialStore` port instead.

### 10.1 Critical Findings (v1)

**1. `$secret_ref` markers break Pydantic model hydration (CRITICAL)**

The v1 design proposed storing `{"$secret_ref": {"provider": "vault", "path": "...", "key": "api_key"}}` inside `cfg_dict`. But `ResourcesService.resolve()` does `model_cls(**self._store.raw_config(rid))` — Pydantic models (e.g. `BaseLLMConfig`) expect `api_key: str`, not a dict. This would cause validation errors on every read unless every config model accepted `Union[str, dict]`.

**v3 resolution:** By scoping to `CredentialStore` only, no `SecretRef` markers are needed. `StoredCredential` is a complete Pydantic model that serializes/deserializes cleanly to/from Vault. MongoDB documents in `credentials` remain unchanged.

**2. `SecretRef.provider` leaks infrastructure into the domain**

`SecretRef.provider` with values `"vault"` | `"mongo"` embeds infrastructure awareness in a domain model. The domain shouldn't know where secrets are stored.

**v3 resolution:** No `SecretRef` model exists. The `CredentialStore` ABC is the only domain port — the adapter selection is purely a composition-time concern in `AppContainer`.

**3. `SecretHint` coupling — UI hints used for security decisions**

The v1 design proposed scanning `cfg_dict` for `SecretHint` annotations to identify secret fields. `SecretHint` is documented as "UI should render this as a password field" — using it for backend security decisions couples business logic to UI metadata.

**v3 resolution:** Not applicable — we no longer scan `cfg_dict` at all. The `CredentialStore` port has a well-defined model (`StoredCredential`) with known encrypted fields.

**4. `MongoSecretProvider` as a separate collection was unnecessary**

Creating a new `secrets` MongoDB collection fragmented secret storage. The existing `credentials` collection with Fernet was already functional.

**v3 resolution:** No new collections. `MongoCredentialStore` is reused as-is for the fallback path.

**5. Write-retry on Vault failure was hand-waved**

v1 said "enqueue retry (log warning; retry mechanism is a follow-up concern)." But a Redis-only cache for a secret that never reaches Vault means the secret is lost on Redis eviction.

**v3 resolution:** In `vault+mongo` mode, Vault write failures fall through to `MongoCredentialStore.upsert()` — the credential is always durably stored in Mongo. No retry mechanism needed for v1 because Mongo acts as the durable fallback.

**6. `on_pre_save` hook interaction unaddressed**

MCP's `on_pre_save` moves `bearer_token` to the `credentials` collection. The v1 design added another interception layer in `ResourcesService` — the order of operations was unclear.

**v3 resolution:** No `ResourcesService` changes. MCP `on_pre_save` continues to move tokens into `credentials` via `AuthService.save_credential()`, which calls `CredentialStore.upsert()`. The Vault adapter is transparently invoked through the same port. No interaction conflicts.

### 10.2 Architectural Violations Found in v1

1. **`SecretRef` in domain** — infrastructure knowledge in domain models → eliminated in v3
2. **`SecretHint` introspection** — UI metadata used for security logic → eliminated in v3
3. **Parallel encryption paths** — `SecretProvider` alongside `CredentialStore` → unified under `CredentialStore` in v3

### 10.3 Efficiency Concerns Resolved

| v1 Issue | v3 Resolution |
|----------|--------------|
| **Read-modify-write race on Vault** (concurrent `set_secret` for same path) | Each credential is a separate Vault secret at its own path. `upsert` writes the full `StoredCredential` — no read-modify-write needed. |
| **Sliding TTL = 2 Redis ops per read** | Fixed TTL — single `GET` per cache hit. |
| **`KVStore` port not leveraged** | `CachedCredentialStore` uses `redis.Redis` directly (same as `RedisFlowStateStore`). Integrating with `KVStore` is a follow-up. |

### 10.4 Recommended Improvements — Status

| Original Recommendation | Status in v3 |
|------------------------|-------------|
| Don't store `SecretRef` markers — use "Vault as replication" | **Adopted** — `VaultCredentialStore` replicates to Vault, Mongo keeps encrypted copy |
| Extract `_FieldCipher` to shared utility | **Deferred** — Section 9.4 |
| Use fixed TTL, not sliding | **Adopted** — 5-minute fixed TTL |
| Batch secret writes per resource | **N/A** — each credential is one Vault secret (no multi-field batching needed) |
| Define `SecretField` domain marker separate from `SecretHint` | **N/A** — not scanning fields; `StoredCredential` has known structure |
| Address write-retry in v1 | **Resolved** — Mongo fallback in `vault+mongo` mode eliminates data-loss risk |
| Make Redis encryption mandatory | **Adopted** — `CachedCredentialStore` refuses to start without `encryption_key` |

### 10.5 Codebase Verification Evidence

| Claim | File Verified | Result |
|-------|--------------|--------|
| `CredentialStore` port defines `upsert`, `find_by_server`, `delete`, `update_status` | `multi-agent/lib/mas/core/auth/credentials/ports.py` | **Verified** |
| `MongoCredentialStore` is the only `CredentialStore` adapter | `multi-agent/adapters/outbound/mongo/auth_token_repository.py` | **Verified** |
| `AuthService` uses `self._store` (a `CredentialStore`) for all persistence | `multi-agent/lib/mas/core/auth/service.py` | **Verified** — `upsert` on lines 127, 235, 272 |
| `AuthService.attempt_recovery` persists refreshed tokens via `self._store.upsert` | `multi-agent/lib/mas/core/auth/service.py:222-235` | **Verified** |
| `AppContainer` wires `MongoCredentialStore` as `self.credential_store` | `multi-agent/bootstrap/container.py:134-142` | **Verified** |
| Redis is available in multi-agent (used for `RedisFlowStateStore` and `RedisChannelFactory`) | `multi-agent/bootstrap/container.py:144-152, 283-291` | **Verified** |
| `SecretHint` is a UI hint, not a security marker | `multi-agent/lib/mas/core/field_hints.py:168-197` | **Verified** |
| `ResourcesService.resolve()` hydrates Pydantic directly from `raw_config` | `multi-agent/lib/mas/resources/service.py:126-129` | **Verified** |
| `MongoCredentialStore` uses Fernet (`_FieldCipher`), NOT MongoDB CSFLE | `multi-agent/adapters/outbound/mongo/auth_token_repository.py:24-45` | **Verified** |
| No CSFLE usage anywhere in repo | Grep for `AutoEncryptionOpts`, `ClientEncryption`, `mongocryptd` | **Verified** — zero matches |
| `RedisFlowStateStore` already encrypts with Fernet | `multi-agent/adapters/outbound/redis/auth_pending_store.py:28-44` | **Verified** |
| `on_pre_save` moves MCP `bearer_token` to `credentials` via `AuthService` | `multi-agent/lib/mas/elements/providers/mcp_server_client/config.py:91-115` | **Verified** |
| A2A `bearer_token` has `SecretHint` but no `on_pre_save` | `multi-agent/lib/mas/elements/nodes/a2a_agent/config.py:32-38` | **Verified** |
| Vault is already used in CI for deploy-time secrets | `ci/pipeline-deploy-vault.groovy:37, 51-78` | **Verified** |
| `resources.cfg_dict` stores `api_key` as plaintext | `multi-agent/adapters/outbound/mongo/resource_repository.py:24-26` | **Verified** |
| `server_configs.client_secret` is NOT encrypted | `multi-agent/adapters/outbound/mongo/client_config_repository.py` | **Verified** |
| OAuth token refresh persists via `CredentialStore.upsert` | `multi-agent/lib/mas/core/auth/service.py:222-235` | **Verified** |
| No existing credential store selection flag | `multi-agent/config/app_config.py` | **Verified** — only `credential_encryption_key` |

---

## Appendix A: Current Secret Storage Audit

| Secret Type | MongoDB Location | Encrypted? | Method | In Scope (v3)? |
|-------------|------------------|------------|--------|----------------|
| OAuth access/refresh tokens | `credentials` collection | Yes (if key set) | Fernet (`_FieldCipher`) | **Yes** |
| MCP bearer/API key (after save) | `credentials` collection (via `on_pre_save`) | Yes (if key set) | Fernet (`_FieldCipher`) | **Yes** |
| OAuth client id/secret | `server_configs` collection | **No** — plaintext | None | No (Section 9.3) |
| LLM `api_key` | `resources.cfg_dict` | **No** — plaintext | None | No (Section 9.2) |
| A2A `bearer_token` | `resources.cfg_dict` | **No** — plaintext | None | No (Section 9.2) |
| SSH `password` | `resources.cfg_dict` | **No** — plaintext | None | No (Section 9.2) |
| OC `token` | `resources.cfg_dict` | **No** — plaintext | None | No (Section 9.2) |
| OAuth pending state (Redis) | `auth_pending:*` keys | Yes (if key set) | Fernet | No (unchanged) |

**Key takeaway:** Only `credentials.access_token` and `credentials.refresh_token` are encrypted at rest. Everything else — including LLM API keys, A2A tokens, SSH passwords, and OAuth client secrets — is stored in plaintext. This story addresses the `credentials` collection path; the plaintext `cfg_dict` fields are deferred to a follow-up story (Section 9.2).

---

## Appendix B: Related Stories

### GENIE-948 — Migrate UnifAI Secrets to HashiCorp Vault (Deploy-Time Injection)

**Ticket:** [GENIE-948](https://redhat.atlassian.net/browse/GENIE-948)
**Design:** [`docs/designs/GENIE-948-pipeline-design.md`](GENIE-948-pipeline-design.md)

**What it does:** Migrates all deploy-time infrastructure secrets (Redis password, RabbitMQ credentials, Keycloak client secret, encryption keys, Slack tokens, cluster access tokens) from the `UnifAI-secrets` Git repository into HashiCorp Vault. Jenkins fetches secrets at deploy time and injects them into pods via K8s Secrets mounted at `/vault/secrets/`.

**Relationship to GENIE-1576:**

| Aspect | GENIE-948 (Deploy-Time) | GENIE-1576 (Runtime) |
|--------|------------------------|---------------------|
| **What secrets** | Infrastructure credentials (Redis password, RabbitMQ, Keycloak, encryption keys) | User-managed credentials (OAuth tokens, MCP API keys/bearer tokens) |
| **When injected** | At deploy time — pods receive secrets at startup via file mount | At runtime — app reads/writes secrets via `CredentialStore` port during user operations |
| **Who manages them** | DevOps / Jenkins pipeline | Application code / end users via UI |
| **Vault interaction** | Jenkins → Vault (AppRole) → K8s Secret → pod file mount | App → Vault (AppRole) → Redis cache → response |

**Dependencies:**
- GENIE-948 should land first — it establishes the Vault KV path structure and Jenkins `withVault` integration
- GENIE-1576's `VaultCredentialStore` can reuse the same Vault instance and potentially the same AppRole, but needs a separate policy granting read/write access to runtime credential paths
- The `credential_encryption_key` used by `MongoCredentialStore` and `CachedCredentialStore` is itself a deploy-time secret managed by GENIE-948

### Proposed: TLS for Internal Service Connections

**Problem:** All internal connections between UnifAI services are currently unencrypted:

| Connection | Current Protocol | TLS Enabled? |
|------------|-----------------|--------------|
| App → MongoDB | `mongodb://{ip}:{port}/` (plain) | No |
| App → Redis | `redis://{ip}:{port}` (plain) | No |
| App → RabbitMQ | AMQP port 5672 (plain) | No |
| App → Vault (proposed) | HTTPS with CA verification | **Yes** |

**Recommended priority:**
1. **Redis TLS** — highest priority, credential cache lives here
2. **MongoDB TLS** — high priority, fallback credential store
3. **RabbitMQ TLS** — medium priority

None block GENIE-1576, but Redis TLS and MongoDB TLS should be fast-follow stories.

### Proposed: Vault AppRole Credential Injection for Runtime Pods

**Problem:** GENIE-1576 requires pods to authenticate to Vault at runtime using AppRole (`vault_role_id` + `vault_secret_id`). These must reach the pods securely.

**v1 approach (aligned with GENIE-948 Option A):** Jenkins fetches AppRole creds from Vault at deploy time, creates a K8s Secret, pods mount it.

**Future upgrade:** Vault Kubernetes auth method — pods authenticate using their K8s ServiceAccount JWT. Zero credentials to inject.

---

## Appendix C: Note on MongoDB Encryption (Fernet vs. CSFLE)

The Jira ticket mentions "MongoDB using Client-Side Field Level Encryption (CSFLE)" for the fallback path. A thorough audit reveals:

**Current state:**
- The **only** encryption in the codebase is application-level Fernet wrapping via `_FieldCipher` in `MongoCredentialStore`.
- The same Fernet pattern is used in `RedisFlowStateStore` for OAuth pending state.
- There is **zero usage** of MongoDB's native CSFLE APIs (`AutoEncryptionOpts`, `ClientEncryption`, `mongocryptd`, `crypt_shared`, `pymongo.encryption`) anywhere in the repository.
- `MongoClient` connections are plain (`mongodb://{host}:{port}/`) with no TLS or encryption options.

**What CSFLE would require:**
- `mongocryptd` daemon or `crypt_shared` library deployed alongside the application
- A KMS provider (could be Vault itself, AWS KMS, Azure Key Vault, GCP KMS, or a local key file)
- JSON schema declarations specifying which fields to encrypt and with what algorithm
- Data Encryption Keys (DEKs) stored in a `__keyVault` collection, wrapped by the KMS Customer Master Key
- Changes to all `MongoClient` instantiations to pass `AutoEncryptionOpts`
- Re-encryption of all existing data

**This is a significant infrastructure change** orthogonal to Vault integration. The design keeps Fernet as the MongoDB encryption approach. CSFLE is deferred (Section 9.6) — and if Vault is the chosen KMS, it can't be properly designed until Vault integration is complete anyway.

---

## Appendix D: Revision Log

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2026-05-07 | Initial design: standalone `SecretProvider` port in `multi-agent`, separate from `CredentialStore` |
| v2 | 2026-05-10 | Moved all components to `global_utils` for cross-service reuse |
| v3 | 2026-05-11 | **Major rescope:** scoped to `CredentialStore` path only; aligned with existing `CredentialStore` ABC; everything stays in `multi-agent`; added Out of Scope section; added refresh/token lifecycle section; added config flag for backend selection |
