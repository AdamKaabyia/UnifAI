# GENIE-1576 — Integrate HashiCorp Vault for Secret Management with Redis Caching and MongoDB Fallback

**Ticket:** GENIE-1576  
**Status:** In Progress  
**Author:** Pipeline Designer Agent  
**Date:** 2026-05-07  
**Last Updated:** 2026-05-11 — Full CRUD lifecycle coverage (create, update, delete) with UI behavior verification.

---

> ### Revision Log
>
> **v3 (2026-05-11):** Expanded section 3.7 and section 4 to cover the full CRUD
> lifecycle — create, read, update, and delete. Verified UI secret field behavior
> (UI sends original plaintext on unchanged fields, not placeholders). Clarified
> `on_pre_save` interaction order. Confirmed `save_resource()` bypass is not a
> user-facing risk (only used by template materialization). Added explicit delete
> cleanup for Vault and Redis. Added edge cases for optional field removal and
> delete-with-Vault-down scenarios.
>
> **v2 (2026-05-10):** Moved `SecretProvider` port, adapters (`VaultSecretProvider`,
> `CachedSecretProvider`, `MongoSecretProvider`), models, exceptions, and `FieldCipher`
> into `global_utils` so that any service (multi-agent, backend, RAG, identity) can
> import and use the secret management module. Vault/Redis config fields moved from
> `multi-agent/config/app_config.py` to `global_utils/config/config.py` (`SharedConfig`).
>
> **v1 (2026-05-07):** Initial design with all components in `multi-agent`.

---

## PHASE 1: DESIGN

### 1. Overview

**Problem statement:**
Sensitive credentials (LLM API keys, MCP bearer tokens, A2A agent secrets, OAuth client secrets) are stored across two MongoDB collections (`credentials` and `resources`) with inconsistent encryption. `credentials.access_token`/`refresh_token` use application-level Fernet wrapping when a key is set, but `resources.cfg_dict` (LLM `api_key`, A2A `bearer_token`) and `server_configs.client_secret` are stored in **plaintext**. Notably, the Fernet encryption is purely application-level — the codebase does not use MongoDB's native Client-Side Field Level Encryption (CSFLE) anywhere. This means there is no schema-enforced encryption, no automatic encryption of query results, and the encryption is entirely opt-in per-adapter. This does not meet enterprise requirements for centralized secret lifecycle management, auditing, and rotation.

**Proposed solution:**
Introduce a `SecretProvider` port (interface) in the domain layer with three adapter implementations: `VaultSecretProvider` (HashiCorp Vault KV v2 via AppRole), `CachedSecretProvider` (Redis sliding-TTL cache decorator with Fernet encryption at rest), and `MongoSecretProvider` (MongoDB with Fernet — the current approach, formalized as fallback). The system selects the provider at composition time based on a `USE_VAULT` config flag. All secret read/write paths are routed through this single port, replacing the current scattered approach. Secrets cached in Redis are encrypted with Fernet before storage, following the same pattern already established by `RedisFlowStateStore`.

**Acceptance criteria:**
- System authenticates to Vault using AppRole and reads/writes to KV v2 engine
- Secrets (LLM tokens, MCP credentials, A2A tokens, OAuth client secrets) are written to Vault and cached in Redis upon creation
- Redis keys expire after configurable minutes of inactivity (sliding TTL)
- Secrets stored in Redis are Fernet-encrypted at rest (not plaintext)
- When `USE_VAULT=false`, secrets are stored in MongoDB with Fernet encryption (existing behavior, formalized)
- System returns 503 if Vault is unreachable and secret is not in Redis cache
- TLS verification is active for Vault connections; fails on invalid CA bundles
- Existing `_FieldCipher` / Fernet encryption in `MongoCredentialStore` is preserved for the fallback path

### 2. Affected Components

> **v2 change:** The port, adapters, models, exceptions, and `FieldCipher` now live in
> `global_utils` so that **any service** (multi-agent, backend, RAG, identity) can use
> them. Vault/Redis config fields live on `SharedConfig`. Per-service `AppContainer`s
> wire the provider from `global_utils` imports — no service-specific secret code needed.

| Layer | Component | Action | File Path (v2) | Previous Path (v1) |
|-------|-----------|--------|----------------|-------------------|
| **Shared Port** | `SecretProvider` port | **New** | `global_utils/src/global_utils/ports/secret_provider.py` | `multi-agent/lib/mas/core/secrets/ports.py` |
| **Shared Port** | `SecretRef` model | **New** | `global_utils/src/global_utils/ports/secret_models.py` | `multi-agent/lib/mas/core/secrets/models.py` |
| **Shared Port** | `SecretStoreUnavailableError` | **New** | `global_utils/src/global_utils/ports/secret_provider.py` | (inline in adapter) |
| **Shared Utility** | `FieldCipher` | **New** (extracted) | `global_utils/src/global_utils/crypto/field_cipher.py` | `multi-agent/adapters/outbound/mongo/auth_token_repository.py` (as `_FieldCipher`) |
| **Shared Adapter** | `VaultSecretProvider` | **New** | `global_utils/src/global_utils/secrets/vault_provider.py` | `multi-agent/adapters/outbound/vault/secret_provider.py` |
| **Shared Adapter** | `CachedSecretProvider` | **New** | `global_utils/src/global_utils/secrets/cached_provider.py` | `multi-agent/adapters/outbound/cache/cached_secret_provider.py` |
| **Shared Adapter** | `MongoSecretProvider` | **New** | `global_utils/src/global_utils/secrets/mongo_provider.py` | `multi-agent/adapters/outbound/mongo/secret_provider.py` |
| **Shared Infra** | `SharedConfig` | **Modified** | `global_utils/src/global_utils/config/config.py` | `multi-agent/config/app_config.py` |
| **Shared Infra** | `requirements.txt` | **Modified** | `global_utils/requirements.txt` | — |
| **Application** | `ResourcesService` | **Modified** | `multi-agent/lib/mas/resources/service.py` | (same) |
| **Application** | `AuthService` | **Modified** | `multi-agent/lib/mas/core/auth/service.py` | (same) |
| **Adapter** | `MongoCredentialStore` | **Modified** | `multi-agent/adapters/outbound/mongo/auth_token_repository.py` | (same — now imports `FieldCipher` from `global_utils`) |
| **Adapter** | `RedisFlowStateStore` | **Modified** | `multi-agent/adapters/outbound/redis/auth_pending_store.py` | (same — now imports `FieldCipher` from `global_utils`) |
| **Infra** | `AppContainer` (multi-agent) | **Modified** | `multi-agent/bootstrap/container.py` | (same — wires provider from `global_utils`) |
| **Infra** | `AppContainer` (backend) | **Modified** | `backend/core/app_container.py` | (not in v1 scope) |
| **Infra** | `AppContainer` (RAG) | **Modified** | `rag/bootstrap/app_container.py` | (not in v1 scope) |
| **Infra** | Factories (identity) | **Modified** | `shared-resources/identity/bootstrap/factories.py` | (not in v1 scope) |
| **Infra** | `secret_map.yaml` | **Modified** | `ci/secret_map.yaml` | (same) |

### 3. Technical Design

#### 3.1 `SecretProvider` Port (Shared)

> **v2 change:** Moved from `multi-agent/lib/mas/core/secrets/ports.py` to
> `global_utils/src/global_utils/ports/secret_provider.py`. Lives alongside
> the existing `KVStore` port. Re-exported from `global_utils.ports`.

**Purpose:** Unified contract for storing and retrieving secrets, regardless of backend. Importable by any service.

**Interfaces/Ports:**

```python
# global_utils/src/global_utils/ports/secret_provider.py
class SecretStoreUnavailableError(Exception):
    """Raised when the backing secret store (Vault, etc.) is unreachable."""

class SecretProvider(ABC):
    @abstractmethod
    def get_secret(self, path: str, key: str) -> Optional[str]: ...

    @abstractmethod
    def set_secret(self, path: str, key: str, value: str) -> None: ...

    @abstractmethod
    def delete_secret(self, path: str, key: str) -> None: ...

    @abstractmethod
    def list_keys(self, path: str) -> List[str]: ...
```

- `path` maps to a logical namespace (e.g. `users/{user_id}/credentials/{server_id}`, `users/{user_id}/resources/{rid}`).
- `key` is the field name (e.g. `access_token`, `api_key`, `bearer_token`, `client_secret`).
- Consumers import: `from global_utils.ports import SecretProvider, SecretStoreUnavailableError`

**Dependencies:** None (pure port, no external libraries).

#### 3.2 `SecretRef` Model (Shared)

> **v2 change:** Moved from `multi-agent/lib/mas/core/secrets/models.py` to
> `global_utils/src/global_utils/ports/secret_models.py`.

**Purpose:** Marker that a secret value has been externalized. Stored in MongoDB in place of the plaintext value.

```python
# global_utils/src/global_utils/ports/secret_models.py
class SecretRef(BaseModel):
    provider: str  # "vault" | "mongo"
    path: str
    key: str
```

When a secret is externalized to Vault, MongoDB stores `{"$secret_ref": {"provider": "vault", "path": "...", "key": "..."}}` instead of the plaintext. This allows the system to resolve secrets at read time.

#### 3.3 `VaultSecretProvider` Adapter

> **v2 change:** Moved from `multi-agent/adapters/outbound/vault/secret_provider.py`
> to `global_utils/src/global_utils/secrets/vault_provider.py`. Config fields moved
> from `multi-agent/config/app_config.py` to `SharedConfig`.

**Purpose:** Implements `SecretProvider` using HashiCorp Vault KV v2 engine with AppRole auth.

**Dependencies:** `hvac` library (added to `global_utils/requirements.txt`).

**Key logic:**
- On init: Authenticate via AppRole (`role_id` + `secret_id`) → obtain a Vault token
- Token renewal: Track `token_ttl`, renew proactively when TTL < 30% remaining
- `get_secret(path, key)` → `client.secrets.kv.v2.read_secret_version(path=path)["data"]["data"][key]`
- `set_secret(path, key, value)` → read-modify-write via `create_or_update_secret`
- TLS: Accept `vault_ca_cert` path; `hvac.Client(url, verify=ca_cert_path)`
- All operations wrapped in try/except: `VaultError` → raise `SecretStoreUnavailableError`
- Import: `from global_utils.secrets import VaultSecretProvider`

**Config fields (on `SharedConfig` — available to all services):**

```python
# global_utils/src/global_utils/config/config.py  (added to SharedConfig)
use_vault: bool = False
vault_addr: str = ""
vault_role_id: str = ""
vault_secret_id: str = ""
vault_ca_cert: str = ""
vault_mount_point: str = "secret"
vault_base_path: str = "unifai"
vault_cache_ttl_seconds: int = 300
```

#### 3.4 `CachedSecretProvider` Adapter (Decorator)

> **v2 change:** Moved from `multi-agent/adapters/outbound/cache/cached_secret_provider.py`
> to `global_utils/src/global_utils/secrets/cached_provider.py`. Now uses the shared
> `FieldCipher` from `global_utils.crypto.field_cipher`.

**Purpose:** Wraps any `SecretProvider` with a Redis sliding-TTL cache. All cached values are Fernet-encrypted at rest in Redis.

**Dependencies:** `redis.Redis` instance (already in `global_utils/requirements.txt`), wrapped `SecretProvider`, `FieldCipher`.

**Key logic:**
- On init: Create `FieldCipher` (Fernet) from the encryption key. Refuse to start if no encryption key is provided.
- `get_secret(path, key)`:
  1. Build Redis key: `secret:{path}:{key}`
  2. `GET` from Redis. If hit → Fernet-decrypt → reset TTL via `EXPIRE` (sliding window) → return plaintext value
  3. If miss → delegate to wrapped provider → Fernet-encrypt → `SETEX` in Redis with configured TTL → return plaintext value
  4. If wrapped provider raises `SecretStoreUnavailableError` → return `None` (caller gets 503)
- `set_secret(path, key, value)`:
  1. Try delegate to wrapped provider
  2. On success → Fernet-encrypt value → `SETEX` in Redis
  3. On `SecretStoreUnavailableError` → Fernet-encrypt → `SETEX` in Redis + enqueue retry (log warning; retry mechanism is a follow-up concern, out of scope for v1)
- `delete_secret(path, key)`:
  1. Delegate to wrapped provider
  2. `DEL` from Redis
- TTL configurable: `vault_cache_ttl_seconds: int = 300` on `SharedConfig`
- Import: `from global_utils.secrets import CachedSecretProvider`

**Redis encryption follows existing pattern** from `RedisFlowStateStore` in `multi-agent/adapters/outbound/redis/auth_pending_store.py`, which already Fernet-encrypts OAuth state payloads before `SETEX`.

#### 3.5 `MongoSecretProvider` Adapter (Fallback)

> **v2 change:** Moved from `multi-agent/adapters/outbound/mongo/secret_provider.py`
> to `global_utils/src/global_utils/secrets/mongo_provider.py`. Now uses the shared
> `FieldCipher` from `global_utils.crypto.field_cipher`.

**Purpose:** Implements `SecretProvider` using the existing MongoDB + Fernet pattern, formalized as a proper adapter.

**Dependencies:** `pymongo` (already in `global_utils/requirements.txt`), `FieldCipher`.

**Key logic:**
- Collection: dedicated `secrets` collection (not reusing `credentials` or `resources`)
- Document schema: `{path: str, key: str, value: str (Fernet-encrypted), updated_at: datetime}`
- Unique index on `(path, key)`
- Uses shared `FieldCipher` for encryption/decryption
- Import: `from global_utils.secrets import MongoSecretProvider`

**Note on MongoDB encryption:** This adapter uses application-level Fernet encryption, **not** MongoDB native CSFLE. See the "Note on MongoDB Encryption" section below for details.

#### 3.5a `FieldCipher` Shared Utility (New)

> **v2 addition:** Extracted from the private `_FieldCipher` class in
> `MongoCredentialStore` into a shared utility.

**Purpose:** Reusable Fernet encrypt/decrypt wrapper for any adapter that needs field-level encryption.

**File:** `global_utils/src/global_utils/crypto/field_cipher.py`

**Key logic:**
- Same implementation as current `_FieldCipher` — wraps `cryptography.fernet.Fernet`
- `encrypt(value: str) -> str` / `decrypt(value: str) -> str`
- Gracefully handles already-decrypted values (prefix check on `gAAAAAB`)
- Import: `from global_utils.crypto import FieldCipher`

**Consumers (after migration):**
- `MongoCredentialStore` — replaces inline `_FieldCipher`
- `RedisFlowStateStore` — replaces inline `Fernet` usage
- `CachedSecretProvider` — new
- `MongoSecretProvider` — new

**Dependency added to `global_utils/requirements.txt`:** `cryptography` (already an indirect dependency via the services that use Fernet today).

#### 3.6 `AppContainer` Wiring (Modified — per service)

> **v2 change:** The wiring logic is the same, but imports come from `global_utils`
> and config comes from `SharedConfig`. Each service's composition root wires its
> own `SecretProvider` instance using the shared components.

**Key logic (pseudocode — identical in every service's container):**

```python
from global_utils.secrets import VaultSecretProvider, CachedSecretProvider, MongoSecretProvider
from global_utils.config import SharedConfig

cfg = SharedConfig.get_instance()

if cfg.use_vault:
    base_provider = VaultSecretProvider(cfg.vault_addr, cfg.vault_role_id, ...)
    if redis_url:
        secret_provider = CachedSecretProvider(
            delegate=base_provider,
            redis_client=redis_client,
            encryption_key=cfg.credential_encryption_key,  # Fernet key for Redis at-rest
            ttl_seconds=cfg.vault_cache_ttl_seconds,
        )
    else:
        secret_provider = base_provider
else:
    secret_provider = MongoSecretProvider(mongo_client, cfg.credential_encryption_key)
```

**Affected containers:**
- `multi-agent/bootstrap/container.py` — primary consumer (resources, credentials)
- `backend/core/app_container.py` — can now use `SecretProvider` for admin config secrets
- `rag/bootstrap/app_container.py` — can now use `SecretProvider` for Slack tokens, broker passwords
- `shared-resources/identity/bootstrap/factories.py` — can now use `SecretProvider` for Keycloak client secrets

#### 3.7 Service Modifications — Full CRUD Lifecycle

> **v2 change:** Services import `SecretProvider` from `global_utils.ports`, not from
> an internal `mas.core.secrets` module. No change to the service-level logic itself.
>
> **v3 change (2026-05-11):** Expanded to cover the full CRUD lifecycle (create, read,
> update, delete) and clarified interactions with `on_pre_save`, template materialization,
> and UI secret field behavior.

**`ResourcesService` changes (multi-agent):**

The service has four write paths. The design must handle all of them:

| Method | Trigger | Runs `_run_pre_save_hook`? | Secret handling required? |
|--------|---------|---------------------------|--------------------------|
| `create()` | `POST /resource.save` (UI) | Yes | Yes — write secrets to provider |
| `update()` | `PUT /resource.update` (UI) | Yes | Yes — overwrite secrets in provider |
| `delete()` | `DELETE /resource.delete` (UI) | N/A | Yes — delete secrets from provider |
| `save_resource()` | Template materialization only | No | No — see note below |

**Constructor:** Receives `SecretProvider` (imported from `global_utils.ports`).

**`create()` path:**
- After `_run_pre_save_hook()`, scan `cfg_dict` for sensitive fields → extract values → write to `SecretProvider` via `set_secret()` → this writes to **both Vault and Redis** (via `CachedSecretProvider`) → replace values in `cfg_dict` with `SecretRef` markers → persist to MongoDB

**`update()` path:**
- Same flow as `create()`. The user's UI sends the **full config** including secret values (unchanged or new — see UI behavior note below). `set_secret()` is called for each sensitive field, which **overwrites** the value in **both Vault and Redis**. Since the Vault path is deterministic (`users/{user_id}/resources/{rid}`) and the `rid` doesn't change on update, the same Vault entry is updated in place.
- If a secret value changed: `set_secret()` overwrites in Vault and refreshes the Redis cache.
- If a secret value is unchanged: `set_secret()` still writes — this is a safe no-op (idempotent overwrite). Optimizing to skip unchanged values is a future enhancement, not a v1 requirement.

**`delete()` path:**
- After deleting the resource from MongoDB, call `secret_provider.delete_secret(path, key)` for each sensitive field. This **removes the secret from both Vault and Redis**.
- The existing `_cleanup_orphaned_credential()` logic for the `credentials` collection remains unchanged.
- The secret cleanup must happen **regardless** of whether `_cleanup_orphaned_credential` runs — they are independent paths (one cleans `credentials` collection entries keyed by `server_identifier`, the other cleans Vault/Redis entries keyed by `rid`).

**`save_resource()` path — no secret handling needed:**
- The only caller is `ResourceMaterializer._save_resources()` during template materialization. This is NOT triggered by direct user UI actions (normal create goes through `create()`).
- Template configs are pre-built from blueprint specs, which should not contain real secrets (templates are sharable). If a template includes a secret field, it would contain a placeholder or empty string, not a real credential.
- `save_resource()` skips schema validation and `_run_pre_save_hook()` by design. Adding secret externalization here is unnecessary and would complicate the materialization flow.

**UI secret field behavior (verified from codebase):**
- When editing a resource, the API returns the **actual secret value** in `cfg_dict` (no masking in the API response).
- The UI stores the real value in React state and masks it **for display only** (shows `•••••` via `maskSecretValue()`).
- When the user submits without changing the secret, the **original plaintext value** is sent back — not `null`, not `""`, not `"***"`.
- When the user clears an optional secret field, the field may be **omitted** from the submitted config (empty strings for optional fields are excluded by `handleSave`).
- Therefore: **no sentinel-value detection is needed**. The backend always receives either the real value or an omitted field.

**`AuthService` / `MongoCredentialStore` changes (multi-agent):**
- `MongoCredentialStore` receives `SecretProvider` as an optional dependency
- `MongoCredentialStore` replaces its private `_FieldCipher` with the shared `FieldCipher` from `global_utils.crypto`
- When present: `upsert()` writes `access_token`/`refresh_token` to `SecretProvider` instead of encrypting inline → stores `SecretRef` in MongoDB
- `find_by_server()` resolves `SecretRef` from `SecretProvider`
- When absent (fallback): current Fernet behavior is preserved unchanged

**`RedisFlowStateStore` changes (multi-agent):**
- Replaces its inline `Fernet` usage with the shared `FieldCipher` from `global_utils.crypto`
- No functional change — just import consolidation

**`on_pre_save` interaction (MCP bearer tokens):**
- MCP's `on_pre_save` moves `bearer_token` from `cfg_dict` into the `credentials` collection and clears it from config. This runs **before** the secret externalization step.
- Order of operations: `_run_pre_save_hook()` → `on_pre_save()` moves bearer to credentials → secret scan on `cfg_dict` → `bearer_token` is already `None` in `cfg_dict` → skipped by secret externalization.
- Therefore: MCP bearer tokens continue to flow through the `credentials` collection path (with Fernet encryption). The secret provider handles the remaining fields in `cfg_dict` (e.g. other config secrets). No conflict.

#### 3.8 New `global_utils` Directory Structure

The following new directories and files are added to `global_utils`:

```
global_utils/src/global_utils/
├── crypto/                          # NEW package
│   ├── __init__.py                  # exports: FieldCipher
│   └── field_cipher.py             # Fernet encrypt/decrypt (extracted from _FieldCipher)
├── ports/
│   ├── __init__.py                  # MODIFIED — adds: SecretProvider, SecretStoreUnavailableError, SecretRef
│   ├── kv_store.py                  # (existing, unchanged)
│   ├── secret_provider.py           # NEW — SecretProvider ABC + SecretStoreUnavailableError
│   └── secret_models.py            # NEW — SecretRef model
├── secrets/                         # NEW package
│   ├── __init__.py                  # exports: VaultSecretProvider, CachedSecretProvider, MongoSecretProvider
│   ├── vault_provider.py           # NEW — Vault KV v2 + AppRole adapter
│   ├── cached_provider.py          # NEW — Redis cache decorator with Fernet
│   └── mongo_provider.py           # NEW — MongoDB + Fernet fallback adapter
└── config/
    └── config.py                    # MODIFIED — SharedConfig gets vault_* and cache fields
```

This follows the existing `global_utils` conventions:
- Ports in `ports/` (alongside `KVStore`)
- Adapters in a dedicated package (`secrets/`, same pattern as `redis/`, `docling/`, `embedding/`)
- Shared utilities in a dedicated package (`crypto/`)
- Thin `__init__.py` files with `__all__` re-exports

### 4. Data Flow

> **v3 update (2026-05-11):** Expanded to cover all four CRUD operations, not just create/read.

**Create path (Vault mode):**
1. `POST /resource.save` → `ResourcesService.create(user_id, category, type, name, config={"api_key": "sk-xxx", ...})`
2. `ResourcesService` builds the config model, calls `_run_pre_save_hook()` (e.g. MCP moves `bearer_token` to `credentials`)
3. For each sensitive field remaining in `cfg_dict` (annotated with `SecretHint`):
   - `secret_provider.set_secret("users/{user_id}/resources/{rid}", "api_key", "sk-xxx")`
   - `CachedSecretProvider` → writes to **Vault** → Fernet-encrypts → caches in **Redis** (`SETEX secret:users/admin/resources/abc123:api_key <encrypted_blob> 300`)
   - Replace `cfg_dict["api_key"]` with `{"$secret_ref": {"provider": "vault", "path": "...", "key": "api_key"}}`
4. `MongoResourceRepository.save()` persists the document with the `SecretRef` marker (no plaintext)

**Update path (Vault mode):**
1. `PUT /resource.update` → `ResourcesService.update(rid, config={"api_key": "sk-new-key", ...})`
2. Load existing `Resource` from MongoDB
3. Build new config model from submitted config, call `_run_pre_save_hook()`
4. For each sensitive field in `cfg_dict`:
   - `secret_provider.set_secret("users/{user_id}/resources/{rid}", "api_key", "sk-new-key")`
   - `CachedSecretProvider` → **overwrites** in **Vault** → refreshes **Redis** cache
   - Replace in `cfg_dict` with `SecretRef` marker
5. `MongoResourceRepository.update()` persists the updated document
6. The Vault path (`users/{uid}/resources/{rid}`) is deterministic from the `rid`, which never changes on update — so the same Vault entry is updated in place, no orphan cleanup needed

**Read path (Vault mode):**
1. `ResourcesService.get(rid)` → loads `Resource` from MongoDB
2. Detects `$secret_ref` in `cfg_dict["api_key"]`
3. `secret_provider.get_secret("users/{user_id}/resources/abc123", "api_key")`
4. `CachedSecretProvider` → **Redis** `GET` → hit: Fernet-decrypt, reset TTL, return; miss: fetch from **Vault** → Fernet-encrypt, cache, return
5. Return populated `Resource` to caller

**Read path (Vault unreachable, cache miss):**
1. Same as above, but `VaultSecretProvider.get_secret()` raises `SecretStoreUnavailableError`
2. `CachedSecretProvider` catches it, Redis `GET` returns `None` (cache miss)
3. Returns `None` → service raises HTTP 503

**Delete path (Vault mode):**
1. `DELETE /resource.delete` → `ResourcesService.delete(rid)`
2. Load existing `Resource` from MongoDB
3. `MongoResourceRepository.delete(rid)` removes the document
4. For each sensitive field that was in `cfg_dict`:
   - `secret_provider.delete_secret("users/{user_id}/resources/{rid}", "api_key")`
   - `CachedSecretProvider` → deletes from **Vault** → `DEL` from **Redis**
5. Existing `_cleanup_orphaned_credential()` runs independently for the `credentials` collection (MCP bearer tokens keyed by `server_identifier`)
6. The two cleanup paths are independent: credential cleanup is by `(user_id, server_identifier)`, secret cleanup is by `(user_id, rid)` — no overlap, no conflict

### 5. Edge Cases & Risks

**Edge cases:**
- **Vault unavailable during write:** `CachedSecretProvider` caches (encrypted) in Redis + logs a warning. Retry/reconciliation is a follow-up story.
- **Redis unavailable:** `CachedSecretProvider` degrades to direct Vault access (catch `redis.ConnectionError`, log, delegate straight through).
- **Both Vault and Redis down during read:** Return 503 with clear error message.
- **Mixed mode migration:** During migration, MongoDB may contain both plaintext values and `SecretRef` markers. The resolve logic must handle both (if field is a dict with `$secret_ref` → resolve; else → treat as plaintext).
- **Secret rotation:** Vault KV v2 supports versioned secrets natively. Rotation can update the Vault path; Redis cache invalidates naturally via TTL expiry.
- **Token refresh race conditions:** `MongoCredentialStore.upsert` is already atomic (MongoDB `update_one` with `upsert=True`). The Vault write + Redis cache update is not atomic — if the process crashes between Vault write and Redis update, the next read will simply cache-miss and re-fetch from Vault.
- **Secret update (v3):** When a user updates a resource with a changed secret value, `set_secret()` is an idempotent overwrite on both Vault and Redis. The Vault path is deterministic from `rid` (which never changes), so no orphan entries are created.
- **Secret delete (v3):** When a resource is deleted, `delete_secret()` explicitly removes the entry from both Vault and Redis. This runs independently from `_cleanup_orphaned_credential()`, which handles the `credentials` collection.
- **Optional secret field cleared (v3):** If the user clears an optional secret field, the UI omits it from the submitted config. The backend should detect that a previously-present secret field is now absent and call `delete_secret()` for it.
- **Template materialization (v3):** `save_resource()` bypasses `_run_pre_save_hook()` but is only called by `ResourceMaterializer` for template instantiation, not by user UI actions. Template configs should not contain real secrets (templates are sharable), so no secret externalization is needed on this path.

**Migration/backward-compatibility risks:**
- **No breaking changes to MongoDB schema:** Existing plaintext values remain readable. `SecretRef` markers are additive.
- **Phased rollout:** `USE_VAULT=false` keeps 100% existing behavior. No code paths change unless the flag is on.
- **Migration script needed:** One-time job to read existing plaintext secrets from `resources.cfg_dict` and `server_configs.client_secret`, write them to Vault, and replace with `SecretRef` markers.

**Performance considerations:**
- Redis sliding-TTL cache ensures <1ms reads for frequently accessed secrets (vs. ~5-50ms for Vault network round-trip).
- Vault reads only on cache miss (~every 5 minutes per secret by default).
- The `read-modify-write` pattern for `set_secret` on Vault KV v2 is inherently non-atomic; acceptable for secret writes which are infrequent.

### 6. Open Questions

1. **Vault namespace / mount point:** The ticket mentions KV v2 — is the mount point `secret/` (default) or a custom path? Is there a namespace per environment?
2. **Redis DB isolation:** Should secret cache use a separate Redis DB index (e.g. `db=1`) from the session streams (`db=0`)?
3. **Secret TTL value:** The ticket says "X minutes" — what is the desired default? Design assumes 5 minutes (300s).
4. **Write retry mechanism:** The ticket specifies "cache in Redis and retry the Vault write" on write failure. Should this be a synchronous retry loop, a background task, or a Temporal workflow? Design defers to follow-up.
5. **MongoDB CSFLE:** The ticket mentions replacing "application-level encryption with MongoDB's native CSFLE" for the fallback. CSFLE requires `mongocryptd`/`crypt_shared`, a KMS provider setup, and schema changes. Is this a hard requirement for v1, or is the existing Fernet approach acceptable as the fallback? (See note below.)
6. ~~**Scope of "all credential fields":** Should this also cover `identity` service secrets (`client_secret`, `keycloak` creds) and `rag` service secrets (`slack_bot_token`), or only `multi-agent`?~~ **Resolved in v2:** By placing the module in `global_utils`, all services can adopt it. Multi-agent is the first consumer; other services wire it into their containers when ready.
7. **A2A `bearer_token`:** Currently stored in `resources.cfg_dict` with no `on_pre_save` hook (unlike MCP tokens). Should it get the same treatment?

---

### Note on MongoDB Encryption (Fernet vs. CSFLE)

The Jira ticket calls for "MongoDB using Client-Side Field Level Encryption (CSFLE)" for the fallback path. However, a thorough audit of the current codebase reveals:

**Current state:**
- The **only** encryption in the codebase is application-level Fernet wrapping via `_FieldCipher` in `MongoCredentialStore` (`multi-agent/adapters/outbound/mongo/auth_token_repository.py`).
- The same Fernet pattern is used in `RedisFlowStateStore` (`multi-agent/adapters/outbound/redis/auth_pending_store.py`) for OAuth pending state.
- There is **zero usage** of MongoDB's native CSFLE APIs (`AutoEncryptionOpts`, `ClientEncryption`, `mongocryptd`, `crypt_shared`, `pymongo.encryption`) anywhere in the repository.
- `MongoClient` connections are plain (`mongodb://{host}:{port}/`) with no TLS or encryption options.

**What CSFLE would require:**
- `mongocryptd` daemon or `crypt_shared` library deployed alongside the application
- A KMS provider (could be Vault itself, AWS KMS, Azure Key Vault, GCP KMS, or a local key file)
- JSON schema declarations specifying which fields to encrypt and with what algorithm (deterministic vs. random)
- Data Encryption Keys (DEKs) stored in a `__keyVault` collection, wrapped by the KMS Customer Master Key (CMK)
- Changes to all `MongoClient` instantiations to pass `AutoEncryptionOpts`
- Re-encryption of all existing data

**This is a significant infrastructure and code change** that is orthogonal to the Vault integration. The design keeps Fernet as the MongoDB encryption approach and flags CSFLE as a separate concern (see Open Question #5).

---

## PHASE 2: DESIGN REVIEW

### Critical Findings

**1. The `$secret_ref` marker pollutes the domain model (CRITICAL)**

The design proposes storing `{"$secret_ref": {"provider": "vault", "path": "...", "key": "api_key"}}` inside `cfg_dict` in MongoDB. But `ResourcesService.resolve()` (line 126-129 of `multi-agent/lib/mas/resources/service.py`) does `model_cls(**self._store.raw_config(rid))`. The Pydantic models (e.g. `BaseLLMConfig`) expect `api_key: str`, not a dict. The `SecretRef` marker would cause **Pydantic validation errors** on every read unless every config model is modified to accept `Union[str, dict]` — which is a massive, invasive change that leaks infrastructure concerns into every domain config model.

**Fix:** The secret resolution must happen *before* the Pydantic model is hydrated — inside `ResourcesRegistry.raw_config()` or as a pre-processing step in `ResourcesService.resolve()`. Or better: don't store markers at all (see alternative approach below).

**2. The `MongoSecretProvider` as a separate collection is unnecessary complexity**

The design proposes a new `secrets` MongoDB collection for the fallback path. But the current system already has working Fernet encryption in `MongoCredentialStore` and plaintext in `resources`. Creating yet another collection fragments secret storage further. The fallback should simply preserve the existing behavior — secrets stay in their current collections with Fernet — without introducing a third storage location.

**3. `CachedSecretProvider` write-retry on Vault failure is hand-waved**

The design says "enqueue retry (log warning; retry mechanism is a follow-up concern, out of scope for v1)." But the ticket's acceptance criteria explicitly require that write failures are handled. A Redis-only cache for a secret that *never makes it to Vault* means the secret is lost on Redis eviction/restart. This is a data-loss risk that cannot be deferred.

**4. No consideration for the `credentials` collection path**

The design focuses on `resources.cfg_dict` and mentions `MongoCredentialStore` briefly, but doesn't clearly define how `access_token`/`refresh_token` in the `credentials` collection — already Fernet-encrypted — migrate to Vault. The `MongoCredentialStore` has a well-established encrypt/decrypt flow. Introducing `SecretProvider` as a parallel dependency creates two encryption paths that could conflict.

**5. Redis encryption is correctly specified but not emphasized in the architecture**

The design (post-revision) correctly specifies Fernet encryption for Redis-cached secrets, following the existing `RedisFlowStateStore` pattern. However, the `CachedSecretProvider` constructor must **refuse to initialize** without an encryption key — unlike the current `RedisFlowStateStore` which treats it as optional. Secrets cached in Redis without encryption is a security regression.

### Architectural Violations

**1. `SecretRef` model in domain leaks infrastructure knowledge**

`SecretRef.provider` with values `"vault"` | `"mongo"` is infrastructure awareness in the domain layer. The domain shouldn't know *where* secrets are stored, only that they can be retrieved through a port. If the marker approach is kept, it should contain only `path` and `key` — the provider is selected at composition time, not embedded in the data.

**2. `ResourcesService` scanning `cfg_dict` for `SecretHint` annotations at save time**

The design proposes `ResourcesService` introspecting Pydantic `json_schema_extra` to identify secret fields. This couples the application service to UI hint metadata (`SecretHint` is documented as "UI should render this as a password field" in `multi-agent/lib/mas/core/field_hints.py:168-171`). Business logic should not depend on UI hints for security-critical decisions. A field being masked in the UI doesn't mean it must be externalized to Vault — and vice versa.

**Fix:** Define an explicit `SECRET_FIELDS` registry or use a dedicated domain marker (not a UI hint) to identify fields requiring externalization.

### Efficiency Concerns

**1. Read-modify-write on Vault KV v2 for `set_secret`**

The design notes that `set_secret` does a read-modify-write. If multiple secrets are written to the same Vault path concurrently (e.g. saving a resource with `api_key` + `bearer_token`), this creates a race condition where one write overwrites the other. Vault KV v2 supports `cas` (check-and-set) but the design doesn't mention it.

**Fix:** Either write one Vault secret per field (path=`users/{uid}/resources/{rid}/api_key`), or use CAS, or batch all fields for a resource into a single `set_secret` call.

**2. Sliding TTL adds Redis round-trip on every secret read**

The design's `get_secret` does: `GET` → if hit → `EXPIRE` (sliding TTL reset) → return. That's two Redis commands per read. For frequently accessed secrets (LLM `api_key` used on every chat message), this adds latency. A fixed TTL with a single `GET` is simpler and sufficient — the access pattern for secrets doesn't benefit from sliding vs. fixed window since they're always hot.

### Duplication & Reusability Issues

**1. Existing `KVStore` port is not leveraged**

The codebase already has a `KVStore` port (`global_utils/src/global_utils/ports/kv_store.py`) with `get`, `set`, `delete` and a `RedisKVStore` adapter. The `CachedSecretProvider` design creates a parallel Redis caching path instead of composing with the existing `KVStore`. The cache layer should delegate to `KVStore` for Redis operations.

**2. `_FieldCipher` is duplicated conceptually**

The `MongoSecretProvider` proposes using `_FieldCipher` — which already lives in `MongoCredentialStore`. If this cipher is needed in multiple places (and it now is — `MongoCredentialStore`, `RedisFlowStateStore`, and the new `CachedSecretProvider` all need Fernet), it should be extracted to a shared utility (e.g. `global_utils/crypto/field_cipher.py`), not duplicated. *(Addressed in v2 — see section 3.5a.)*

### Risks to Existing System

**1. `ResourcesService.resolve()` is on the hot path**

Every LLM call, MCP tool invocation, and A2A agent interaction resolves resources. Adding a secret-resolution step (Redis/Vault lookup) to this path increases latency and introduces a new failure mode. If the secret provider is down, previously working workflows break.

**Mitigation:** The current system works with secrets inline in `cfg_dict`. If Vault mode is enabled, the resolution must have a sensible fallback (e.g. local cache with long TTL, or graceful degradation).

**2. Migration script must handle idempotency**

If the migration script runs twice (or crashes mid-run), it must not corrupt data. The design doesn't specify whether the migration is idempotent or what happens if a `SecretRef` marker is already present.

**3. `on_pre_save` hooks interact unpredictably**

MCP's `on_pre_save` (`multi-agent/lib/mas/elements/providers/mcp_server_client/config.py:91`) already moves `bearer_token` to the `credentials` collection. The design adds *another* interception layer in `ResourcesService` that scans for `SecretHint` fields. The order of operations matters — if the `SecretHint` scan runs before `on_pre_save`, the bearer token is externalized to Vault from `cfg_dict`; if after, it's already been moved to `credentials`. *(Clarified in v3 — see section 3.7. The secret scan runs AFTER `_run_pre_save_hook()`, so `bearer_token` is already `None` in `cfg_dict` and is skipped. No conflict.)*

### Recommended Improvements

1. **Don't store `SecretRef` markers in MongoDB.** Instead, always store the encrypted value in MongoDB (using existing Fernet), AND replicate to Vault when enabled. Read from cache → Vault → MongoDB (encrypted fallback). This avoids schema changes, Pydantic validation issues, and migration headaches.

2. **Extract `_FieldCipher` to `global_utils/crypto/field_cipher.py`** for reuse across `MongoCredentialStore`, `RedisFlowStateStore`, `CachedSecretProvider`, and any new secret-handling adapter. *(Addressed in v2 — see section 3.5a.)*

3. **Use fixed TTL, not sliding TTL.** Simpler, one Redis op per read, and the behavioral difference is negligible for secrets that are accessed continuously.

4. **Batch secret writes per resource.** Write all secrets for a resource as a single Vault KV v2 secret (one path per resource) rather than one path per field. This avoids read-modify-write races and reduces Vault API calls.

5. **Define a `SecretField` domain marker** separate from `SecretHint` — a simple set or class-level attribute on config models that lists field names to externalize. Don't introspect UI hints for security decisions.

6. **Address the write-retry in v1.** At minimum, a synchronous retry with exponential backoff (3 attempts) before falling through to the "encrypted in Mongo" fallback. A background reconciliation job can be v2.

7. **Make Redis encryption mandatory for secrets.** The `CachedSecretProvider` must refuse to start without `credential_encryption_key`. This differs from `RedisFlowStateStore` where encryption is optional — for a secret cache, it must not be.

### Safer / Cleaner Alternative Approach

**"Vault as a replication target, not a replacement for MongoDB"**

Instead of replacing MongoDB as the secret store and introducing `SecretRef` markers, treat Vault as a **replication layer** that sits alongside existing storage:

1. **Write path:** On every secret save, write to MongoDB (with Fernet encryption, as today) AND replicate to Vault (if enabled). Redis cache is populated from the write (Fernet-encrypted in Redis).
2. **Read path:** Read from Redis cache (Fernet-decrypt) → on miss, read from Vault → on Vault failure, read from MongoDB (Fernet-decrypted).
3. **No schema changes.** MongoDB documents remain identical. No `SecretRef` markers. No Pydantic model changes.
4. **No migration script needed for v1.** Existing secrets stay in MongoDB. Vault is populated lazily (on next read/write) or via an optional background sync job.
5. **Gradual migration:** Over time, a background job can pre-populate Vault from MongoDB. Once Vault is fully populated and proven, a future story can optionally remove plaintext/Fernet from MongoDB.

This approach:
- Has **zero blast radius** — if Vault/Redis is down, the system falls back to exactly the behavior it has today
- Requires **no changes to Pydantic config models** or `SecretHint` introspection
- Requires **no migration script** for initial rollout
- Is **fully backward compatible** — `USE_VAULT=false` changes nothing
- The `SecretProvider` port still exists, but its contract is simpler (write-through + read-through cache, not a replacement)
- All three tiers (Redis, Vault, MongoDB) encrypt at rest — Redis with Fernet, Vault natively, MongoDB with Fernet

The `credentials` collection path remains entirely unchanged in v1 — it already has Fernet. Vault replication for OAuth tokens can be a separate, smaller follow-up story.

### Note on CSFLE

Dropping CSFLE from this story is recommended. It's orthogonal infrastructure work requiring `mongocryptd`/`crypt_shared`, a KMS provider, and schema changes. The current Fernet approach is simpler, proven, and works. CSFLE should be evaluated as its own story — and if Vault is the chosen KMS, it can't be designed until Vault integration is complete anyway.

### Adversarial Challenges Applied

**1. Dependency Inversion Test:**
"If I remove `VaultSecretProvider`, does the domain still compile?" — Yes, `SecretProvider` is a port in the domain, `VaultSecretProvider` is an adapter. However, `SecretRef` (with `provider: "vault"`) in the domain models breaks this — the domain now knows about Vault. **Revealed:** Architectural violation in `SecretRef.provider`.

**2. Blast Radius Test:**
Files touched: `ResourcesService`, `AuthService`, `MongoCredentialStore`, `MongoResourceRepository`, `AppContainer`, `AppConfig`. Dependents of `ResourcesService.resolve()`: `BlueprintResolver`, `SessionFactory`, `TemplateService`, `ShareCloner`, plus all inbound Flask endpoints. **Revealed:** The resolve path is deeply depended upon; any change there cascades to the entire workflow execution pipeline.

**3. Edge Case Injection:**
- *Empty `api_key` field:* The design doesn't address whether empty/default values (e.g. `api_key="EMPTY"` in `BaseLLMConfig`) should be externalized. They shouldn't, but the `SecretHint` scan would flag them.
- *Concurrent resource save:* Two users save the same resource simultaneously. The Vault read-modify-write is not atomic — last write wins, potentially losing a field.
- *Partial failure during save:* Secret written to Vault but MongoDB save fails → orphaned Vault entry. Or vice versa: MongoDB saved but Vault write fails → `SecretRef` marker points to nonexistent Vault entry.
- *(v3) Optional secret field cleared on update:* User removes an optional secret. The field is omitted from submitted config. The design must detect that a previously-present secret field is now absent and call `delete_secret()`.
- *(v3) Delete with Vault down:* Resource is deleted from MongoDB but `delete_secret()` fails for Vault. Orphan entry remains in Vault. Mitigation: best-effort delete with logging; a reconciliation job can clean orphans later.

### Codebase Verification Evidence

| Claim | File Verified | Result |
|-------|--------------|--------|
| `SecretHint` is a UI hint, not a security marker | `multi-agent/lib/mas/core/field_hints.py:168-197` | **Verified** — docstring says "UI should render this as a password field (masked)" |
| `ResourcesService.resolve()` hydrates Pydantic directly | `multi-agent/lib/mas/resources/service.py:126-129` | **Verified** — `model_cls(**self._store.raw_config(rid))` |
| `BaseLLMConfig.api_key` is `str` type | `multi-agent/lib/mas/elements/llms/common/base_config.py:16-19` | **Verified** — `api_key: str = Field("EMPTY", ...)` |
| `MongoCredentialStore` uses Fernet, NOT MongoDB native CSFLE | `multi-agent/adapters/outbound/mongo/auth_token_repository.py:24-45` | **Verified** — `_FieldCipher` wraps `cryptography.fernet.Fernet` |
| No CSFLE usage anywhere in repo | Grep for `AutoEncryptionOpts`, `ClientEncryption`, `mongocryptd`, `crypt_shared` | **Verified** — only match is `auth_token_repository.py` for app-level Fernet |
| `RedisFlowStateStore` already encrypts with Fernet | `multi-agent/adapters/outbound/redis/auth_pending_store.py:28-44` | **Verified** — `self._fernet = Fernet(encryption_key...)`, encrypts before `SETEX` |
| `KVStore` port exists with `get`/`set`/`delete` | `global_utils/src/global_utils/ports/kv_store.py:1-16` | **Verified** |
| `on_pre_save` moves MCP `bearer_token` to `credentials` | `multi-agent/lib/mas/elements/providers/mcp_server_client/config.py:91-115` | **Verified** |
| A2A `bearer_token` has `SecretHint` but no `on_pre_save` | `multi-agent/lib/mas/elements/nodes/a2a_agent/config.py:32-38` | **Verified** — no `on_pre_save` defined |
| `AppContainer` is the composition root with singleton pattern | `multi-agent/bootstrap/container.py:1-12, 68-79` | **Verified** |
| No existing `$secret_ref` pattern in codebase | Grep for `secret_ref` across entire repo | **Verified** — zero matches |
| Vault is already used in CI pipeline for deploy-time secrets | `ci/pipeline-deploy-vault.groovy:37, 51-78` | **Verified** — `VaultBasePath: "apps/automation-and-tools/unifai"` and `withVault` blocks |
| `resources.cfg_dict` stores `api_key` as plaintext | `multi-agent/adapters/outbound/mongo/resource_repository.py:24-26` | **Verified** — `insert_one({"_id": doc.rid, **doc.model_dump(mode="json")})` |
| `server_configs.client_secret` is NOT encrypted | `multi-agent/adapters/outbound/mongo/client_config_repository.py` | **Verified** — plain `model_dump()` with no encryption |
| SSH and OC tools store passwords/tokens in `cfg_dict` unencrypted | `multi-agent/lib/mas/elements/tools/ssh_exec/config.py:16-22`, `oc_exec/config.py:18-24` | **Verified** — `SecretHint` for UI only, no encryption |

### Verdict

**NEEDS REVISION**

The design must address these items before proceeding to implementation:

1. **Eliminate `SecretRef` markers** — the approach breaks Pydantic model hydration at `ResourcesService.resolve()` and leaks infrastructure into the domain. Adopt the "Vault as replication" alternative, or find another way to avoid storing markers in `cfg_dict`.
2. **Remove `SecretRef.provider` field** — if markers are kept despite the above, `provider` is an architectural violation.
3. **Stop relying on `SecretHint` for secret identification** — define an explicit, domain-level field registry for security-sensitive fields.
4. **Drop `MongoSecretProvider` as a separate collection** — the fallback should be the existing Fernet-encrypted storage in-place, not a third collection.
5. **Address write-failure retry in v1** — at minimum synchronous retries; the deferred approach risks data loss.
6. **Clarify `on_pre_save` interaction** — document the order of operations for MCP tokens and whether Vault externalization happens before or after `on_pre_save`. *(Addressed in v3 — see section 3.7. Secret scan runs after `_run_pre_save_hook()`.)*
7. **Drop CSFLE from this story** — it's orthogonal infrastructure work that can't be properly designed until Vault is in place (if Vault serves as KMS).
8. **Resolve race condition on Vault read-modify-write** — use single-field paths or CAS.
9. **Make Redis encryption mandatory** — `CachedSecretProvider` must require an encryption key and refuse to start without one.
10. **Extract `_FieldCipher` to shared utility** — eliminate duplication across `MongoCredentialStore`, `RedisFlowStateStore`, and the new cache adapter. *(Addressed in v2 — `FieldCipher` in `global_utils/crypto/field_cipher.py`.)*
11. **Acknowledge that current MongoDB encryption is app-level Fernet, not native CSFLE** — the design and ticket should be explicit about this distinction to avoid confusion about the security guarantees provided.
12. *(v2)* **Ensure `global_utils/requirements.txt` is updated** — must add `hvac` and `cryptography` as explicit dependencies.

---

## Appendix: Current Secret Storage Audit

| Secret Type | MongoDB Location | Encrypted in App? | Method | Native CSFLE? |
|-------------|------------------|--------------------|--------|---------------|
| OAuth access/refresh tokens | `credentials` collection | Yes (if key set) | Fernet (`_FieldCipher`) | No |
| MCP bearer/API key (after save) | `credentials` collection (via `on_pre_save`) | Yes (if key set) | Fernet (`_FieldCipher`) | No |
| OAuth client id/secret | `server_configs` collection | **No** | Plaintext | No |
| LLM `api_key` | `resources.cfg_dict` | **No** | Plaintext | No |
| A2A `bearer_token` | `resources.cfg_dict` | **No** | Plaintext | No |
| SSH `password` | `resources.cfg_dict` | **No** | Plaintext | No |
| OC `token` | `resources.cfg_dict` | **No** | Plaintext | No |
| OAuth pending state (Redis) | `auth_pending:*` keys | Yes (if key set) | Fernet | N/A |

**Key takeaway:** Only `credentials.access_token` and `credentials.refresh_token` are encrypted at rest. Everything else — including LLM API keys, A2A tokens, SSH passwords, and OAuth client secrets — is stored in plaintext in MongoDB. The encryption that does exist is application-level Fernet, not MongoDB native CSFLE.

---

## Appendix B: v1 → v2 Change Summary

The following table summarizes what moved from `multi-agent` to `global_utils` in v2. No logic, signatures, or architectural decisions changed — only locations and imports.

| What | v1 Location | v2 Location | Nature of Change |
|------|-------------|-------------|------------------|
| `SecretProvider` port | `multi-agent/lib/mas/core/secrets/ports.py` | `global_utils/src/global_utils/ports/secret_provider.py` | Moved file |
| `SecretStoreUnavailableError` | Inline in vault adapter | `global_utils/src/global_utils/ports/secret_provider.py` | Moved to shared port module |
| `SecretRef` model | `multi-agent/lib/mas/core/secrets/models.py` | `global_utils/src/global_utils/ports/secret_models.py` | Moved file |
| `VaultSecretProvider` | `multi-agent/adapters/outbound/vault/secret_provider.py` | `global_utils/src/global_utils/secrets/vault_provider.py` | Moved file |
| `CachedSecretProvider` | `multi-agent/adapters/outbound/cache/cached_secret_provider.py` | `global_utils/src/global_utils/secrets/cached_provider.py` | Moved file |
| `MongoSecretProvider` | `multi-agent/adapters/outbound/mongo/secret_provider.py` | `global_utils/src/global_utils/secrets/mongo_provider.py` | Moved file |
| `FieldCipher` | `multi-agent/adapters/outbound/mongo/auth_token_repository.py` (private `_FieldCipher`) | `global_utils/src/global_utils/crypto/field_cipher.py` | Extracted + moved |
| Vault config fields | `multi-agent/config/app_config.py` (`AppConfig`) | `global_utils/src/global_utils/config/config.py` (`SharedConfig`) | Moved fields to base class |
| `hvac` dependency | `multi-agent/requirements.txt` | `global_utils/requirements.txt` | Moved dependency |
| `cryptography` dependency | Implicit (via multi-agent) | `global_utils/requirements.txt` | Made explicit |

**Import changes in consuming code:**

```python
# v1 (multi-agent only)
from mas.core.secrets.ports import SecretProvider
from outbound.vault.secret_provider import VaultSecretProvider
from outbound.cache.cached_secret_provider import CachedSecretProvider

# v2 (any service)
from global_utils.ports import SecretProvider, SecretStoreUnavailableError
from global_utils.secrets import VaultSecretProvider, CachedSecretProvider, MongoSecretProvider
from global_utils.crypto import FieldCipher
```

**What did NOT change:** All Phase 2 review findings (SecretRef marker issues, SecretHint coupling, write-retry gaps, etc.) apply identically regardless of where the code lives. The verdict remains **NEEDS REVISION** for the same 11 structural items.

---

## Appendix C: Related Stories

### GENIE-948 — Migrate UnifAI Secrets to HashiCorp Vault (Deploy-Time Injection)

**Ticket:** [GENIE-948](https://redhat.atlassian.net/browse/GENIE-948)  
**Design:** [`docs/designs/GENIE-948-pipeline-design.md`](GENIE-948-pipeline-design.md)  
**Status:** In design  

**What it does:** Migrates all deploy-time infrastructure secrets (Redis password, RabbitMQ credentials, Keycloak client secret, encryption keys, Slack tokens, cluster access tokens) from the `UnifAI-secrets` Git repository into HashiCorp Vault. Jenkins fetches secrets at deploy time and injects them into pods via K8s Secrets mounted at `/vault/secrets/`. A new `VaultFileSource` config adapter in `global_utils` reads these files at application startup.

**Relationship to GENIE-1576:** The two stories address different layers of the same security initiative:

| Aspect | GENIE-948 (Deploy-Time) | GENIE-1576 (Runtime) |
|--------|------------------------|---------------------|
| **What secrets** | Infrastructure credentials (Redis password, RabbitMQ, Keycloak, encryption keys) | User-managed secrets (LLM API keys, MCP tokens, A2A bearer tokens, SSH passwords) |
| **When injected** | At deploy time — pods receive secrets at startup via file mount | At runtime — app reads/writes secrets via `SecretProvider` port during user operations |
| **Who manages them** | DevOps / Jenkins pipeline | Application code / end users via UI |
| **Vault interaction** | Jenkins → Vault (AppRole) → K8s Secret → pod file mount | App → Vault (AppRole) → Redis cache → response |
| **Changes to `global_utils`** | Adds `VaultFileSource` to config source chain | Adds `SecretProvider` port, `FieldCipher`, adapter packages |

**Dependencies:**
- GENIE-948 should land first — it establishes the Vault KV path structure (`apps/automation-and-tools/unifai/{env}/{service}`) and Jenkins `withVault` integration that GENIE-1576 builds on.
- GENIE-1576's `VaultSecretProvider` (runtime AppRole auth) can reuse the same Vault instance and potentially the same AppRole, but needs a separate policy granting read/write access to runtime secret paths (e.g. `apps/automation-and-tools/unifai/{env}/runtime/*`), whereas GENIE-948 policies are read-only for deploy-time paths.
- The `VaultFileSource` added by GENIE-948 and the `SecretProvider` added by GENIE-1576 are independent — they don't conflict in `SharedConfig` and solve different problems.

**Shared infrastructure work:**
- Both stories benefit from Vault AppRole being configured and tested.
- Both stories add content to `global_utils` (GENIE-948 adds `VaultFileSource` in `config/sources.py`; GENIE-1576 adds `ports/secret_provider.py`, `secrets/`, `crypto/`).

---

### Proposed: TLS for Internal Service Connections

**Proposed ticket — not yet created.**

**Problem:** All internal connections between UnifAI services are currently unencrypted:

| Connection | Current Protocol | TLS Enabled? |
|------------|-----------------|--------------|
| App → MongoDB | `mongodb://{ip}:{port}/` (plain) | **No** — `MongoClient` has no TLS options |
| App → Redis | `redis://{ip}:{port}` (plain) | **No** — `get_redis_url()` builds `redis://` not `rediss://` |
| App → RabbitMQ | AMQP port 5672 (plain) | **No** — TLS templates exist in Helm chart but disabled by default |
| App → Temporal | gRPC port 7233 (plain) | **No** |
| App → Qdrant | HTTP port 6333 (plain) | **No** |
| External → UI | HTTPS via OpenShift Route | **Yes** — `tls.termination: edge` |
| App → Vault (proposed) | HTTPS with CA verification | **Yes** — `hvac.Client(url, verify=ca_cert_path)` |

**Network Policies** exist for MongoDB, RabbitMQ, Temporal, and Docling (restricting which pods can connect), which limits *who* can talk, but the traffic itself is plaintext within the cluster.

**Why this matters for GENIE-1576:** Even with Fernet-encrypted secrets in Redis and Vault TLS, when the app fetches a decrypted secret from Redis and then passes it to an LLM client or stores it in MongoDB, those hops are unencrypted. If the cluster network is compromised (or compliance requires defense-in-depth), secrets are exposed in transit.

**Recommended scope (prioritized):**

1. **Redis TLS (highest priority)** — The secret cache lives here. Add `redis_tls: bool` and `redis_ca_cert: str` to `SharedConfig`, update `get_redis_url()` to emit `rediss://` URLs, enable TLS on the Redis Helm chart. This is the most impactful change because every cached secret transits this connection.

2. **MongoDB TLS (high priority)** — The fallback secret store and the `credentials` collection with Fernet-encrypted tokens. Add TLS options to all `MongoClient` instantiations, enable TLS on the MongoDB Helm chart.

3. **RabbitMQ TLS (medium priority)** — The Helm chart already has `tls-secrets.yaml` and `ingress-tls-secrets.yaml` templates; TLS just needs to be enabled and certs provisioned.

4. **Temporal / Qdrant TLS (lower priority)** — These don't carry user secrets directly, but defense-in-depth applies.

**Infrastructure requirements:**
- Certificate provisioning — either via cert-manager (if available on the cluster), manually provisioned CA + certs, or OpenShift service-serving certificates.
- Each service Helm chart needs TLS volume mounts and configuration.
- `SharedConfig` needs new fields for TLS parameters (CA cert paths, client cert paths if mTLS is desired).

**Relationship to GENIE-1576:** Not a blocker — GENIE-1576 can proceed without TLS on internal connections. However, Redis TLS and MongoDB TLS should be flagged as fast-follow stories within the same security initiative. The Vault connection (introduced by GENIE-1576) is the only one that will be TLS-encrypted from day one.

---

### Proposed: Vault AppRole Credential Injection for Runtime Pods

**Proposed ticket — not yet created.**

**Problem:** GENIE-1576 requires pods to authenticate to Vault at runtime using AppRole (`vault_role_id` + `vault_secret_id`). These credentials need to reach the running pods securely.

**Current approach (viable for v1):** Jenkins fetches the AppRole credentials from Vault at deploy time (same pattern as GENIE-948), creates a K8s Secret, and pods mount it. This works and is consistent with the existing deployment model.

**Future upgrade path:** Vault's **Kubernetes auth method** eliminates the need for `role_id`/`secret_id` entirely — pods authenticate using their K8s ServiceAccount JWT token. Vault trusts the cluster's TokenReview API to verify the pod's identity. This requires:
- Vault admin to configure the `auth/kubernetes` backend and bind policies to ServiceAccounts
- No Jenkins involvement for runtime credentials
- Per-ServiceAccount Vault policies scoping which secrets each service can access

**Options comparison:**

| Approach | How | Pros | Cons |
|----------|-----|------|------|
| **Jenkins injects AppRole creds as K8s Secret** (v1) | Jenkins `withVault` → K8s Secret → pod env/volume | Simple, consistent with GENIE-948 pattern | `secret_id` is long-lived; exists as K8s Secret; no pod-level audit |
| **Vault Kubernetes auth** (future) | Pod ServiceAccount JWT → Vault verifies → issues token | Zero credentials to inject; pod-level audit; automatic renewal | Requires Vault admin to configure K8s auth backend |
| **Vault Agent Injector** (if GENIE-948 Option B is adopted) | Sidecar auto-authenticates via K8s SA; injects runtime AppRole token | Pairs with GENIE-948 Option B; in-memory only | Requires Vault Operator on cluster |

**Recommendation:** Start with Jenkins-injected K8s Secrets for v1 (same as GENIE-948 Option A). Migrate to Kubernetes auth when/if GENIE-948 moves to Option B and the Vault Operator is available on clusters. The application code (`VaultSecretProvider`) doesn't change — only the source of `vault_role_id`/`vault_secret_id` config values changes.

**RBAC hardening for v1:** The K8s Secret containing `vault_role_id`/`vault_secret_id` should be scoped with RBAC so only the ServiceAccounts that need it can read it — not every SA in the namespace.
