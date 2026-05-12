# GENIE-1576 — Integrate HashiCorp Vault for Secret Management with Redis Caching and MongoDB Fallback

**Ticket:** GENIE-1576  
**Status:** In Progress  
**Author:** Pipeline Designer Agent  
**Date:** 2026-05-07  

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

| Layer | Component | Action | File Path |
|-------|-----------|--------|-----------|
| **Domain** | `SecretProvider` port | **New** | `multi-agent/lib/mas/core/secrets/ports.py` |
| **Domain** | `SecretRef` model | **New** | `multi-agent/lib/mas/core/secrets/models.py` |
| **Adapter (outbound)** | `VaultSecretProvider` | **New** | `multi-agent/adapters/outbound/vault/secret_provider.py` |
| **Adapter (outbound)** | `CachedSecretProvider` | **New** | `multi-agent/adapters/outbound/cache/cached_secret_provider.py` |
| **Adapter (outbound)** | `MongoSecretProvider` | **New** | `multi-agent/adapters/outbound/mongo/secret_provider.py` |
| **Application** | `ResourcesService` | **Modified** | `multi-agent/lib/mas/resources/service.py` |
| **Application** | `AuthService` | **Modified** | `multi-agent/lib/mas/core/auth/service.py` |
| **Adapter (outbound)** | `MongoCredentialStore` | **Modified** | `multi-agent/adapters/outbound/mongo/auth_token_repository.py` |
| **Adapter (outbound)** | `MongoResourceRepository` | **Modified** | `multi-agent/adapters/outbound/mongo/resource_repository.py` |
| **Infra** | `AppConfig` | **Modified** | `multi-agent/config/app_config.py` |
| **Infra** | `AppContainer` | **Modified** | `multi-agent/bootstrap/container.py` |
| **Infra** | `secret_map.yaml` | **Modified** | `ci/secret_map.yaml` |

### 3. Technical Design

#### 3.1 `SecretProvider` Port (Domain)

**Purpose:** Unified contract for storing and retrieving secrets, regardless of backend.

**Interfaces/Ports:**

```python
# multi-agent/lib/mas/core/secrets/ports.py
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

**Dependencies:** None (pure domain port).

#### 3.2 `SecretRef` Model (Domain)

**Purpose:** Marker that a secret value has been externalized. Stored in MongoDB in place of the plaintext value.

```python
# multi-agent/lib/mas/core/secrets/models.py
class SecretRef(BaseModel):
    provider: str  # "vault" | "mongo"
    path: str
    key: str
```

When a secret is externalized to Vault, MongoDB stores `{"$secret_ref": {"provider": "vault", "path": "...", "key": "..."}}` instead of the plaintext. This allows the system to resolve secrets at read time.

#### 3.3 `VaultSecretProvider` Adapter

**Purpose:** Implements `SecretProvider` using HashiCorp Vault KV v2 engine with AppRole auth.

**Dependencies:** `hvac` library (official Vault Python client).

**Key logic:**
- On init: Authenticate via AppRole (`role_id` + `secret_id`) → obtain a Vault token
- Token renewal: Track `token_ttl`, renew proactively when TTL < 30% remaining
- `get_secret(path, key)` → `client.secrets.kv.v2.read_secret_version(path=path)["data"]["data"][key]`
- `set_secret(path, key, value)` → read-modify-write via `create_or_update_secret`
- TLS: Accept `vault_ca_cert` path; `hvac.Client(url, verify=ca_cert_path)`
- All operations wrapped in try/except: `VaultError` → raise domain `SecretStoreUnavailableError`

**Config fields (on `AppConfig`):**

```python
use_vault: bool = False
vault_addr: str = ""
vault_role_id: str = ""
vault_secret_id: str = ""
vault_ca_cert: str = ""
vault_mount_point: str = "secret"
vault_base_path: str = "unifai"
```

#### 3.4 `CachedSecretProvider` Adapter (Decorator)

**Purpose:** Wraps any `SecretProvider` with a Redis sliding-TTL cache. All cached values are Fernet-encrypted at rest in Redis.

**Dependencies:** `redis.Redis` instance, wrapped `SecretProvider`, Fernet encryption key.

**Key logic:**
- On init: Create `_FieldCipher` (Fernet) from the encryption key. Refuse to start if no encryption key is provided.
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
- TTL configurable: `vault_cache_ttl_seconds: int = 300` on `AppConfig`

**Redis encryption follows existing pattern** from `RedisFlowStateStore` in `multi-agent/adapters/outbound/redis/auth_pending_store.py`, which already Fernet-encrypts OAuth state payloads before `SETEX`.

#### 3.5 `MongoSecretProvider` Adapter (Fallback)

**Purpose:** Implements `SecretProvider` using the existing MongoDB + Fernet pattern, formalized as a proper adapter.

**Dependencies:** `pymongo` collection, `_FieldCipher`.

**Key logic:**
- Collection: dedicated `secrets` collection (not reusing `credentials` or `resources`)
- Document schema: `{path: str, key: str, value: str (Fernet-encrypted), updated_at: datetime}`
- Unique index on `(path, key)`
- Uses existing `_FieldCipher` for encryption/decryption

**Note on MongoDB encryption:** This adapter uses application-level Fernet encryption, **not** MongoDB native CSFLE. See the "Note on MongoDB Encryption" section below for details.

#### 3.6 `AppContainer` Wiring (Modified)

**Key logic (pseudocode):**

```
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

#### 3.7 Service Modifications

**`ResourcesService` changes:**
- Constructor receives `SecretProvider`
- In `create()` / `update()`: after `_run_pre_save_hook()`, scan `cfg_dict` for sensitive fields (identified by `SecretHint` annotation on the Pydantic model) → extract values → write to `SecretProvider` → replace values in `cfg_dict` with `SecretRef` markers → persist to MongoDB
- In `get()` / `list()`: after loading from MongoDB → scan for `SecretRef` markers → resolve via `SecretProvider` → return populated model

**`AuthService` / `MongoCredentialStore` changes:**
- `MongoCredentialStore` receives `SecretProvider` as an optional dependency
- When present: `upsert()` writes `access_token`/`refresh_token` to `SecretProvider` instead of encrypting inline → stores `SecretRef` in MongoDB
- `find_by_server()` resolves `SecretRef` from `SecretProvider`
- When absent (fallback): current Fernet behavior is preserved unchanged

### 4. Data Flow

**Write path (Vault mode):**
1. Inbound adapter (Flask endpoint) → `ResourcesService.create(user_id, category, type, name, config={"api_key": "sk-xxx", ...})`
2. `ResourcesService` builds the config model, calls `on_pre_save()`
3. For each sensitive field (annotated with `SecretHint`):
   - `secret_provider.set_secret("users/{user_id}/resources/{rid}", "api_key", "sk-xxx")`
   - `CachedSecretProvider` → writes to Vault → Fernet-encrypts → caches in Redis (`SETEX secret:users/admin/resources/abc123:api_key <encrypted_blob> 300`)
   - Replace `cfg_dict["api_key"]` with `{"$secret_ref": {"provider": "vault", "path": "...", "key": "api_key"}}`
4. `MongoResourceRepository.save()` persists the document with the `SecretRef` marker (no plaintext)

**Read path (Vault mode):**
1. `ResourcesService.get(rid)` → loads `Resource` from MongoDB
2. Detects `$secret_ref` in `cfg_dict["api_key"]`
3. `secret_provider.get_secret("users/{user_id}/resources/abc123", "api_key")`
4. `CachedSecretProvider` → Redis `GET` → hit: Fernet-decrypt, reset TTL, return; miss: fetch from Vault → Fernet-encrypt, cache, return
5. Return populated `Resource` to caller

**Read path (Vault unreachable, cache miss):**
1. Same as above, but `VaultSecretProvider.get_secret()` raises `SecretStoreUnavailableError`
2. `CachedSecretProvider` catches it, Redis `GET` returns `None` (cache miss)
3. Returns `None` → service raises HTTP 503

### 5. Edge Cases & Risks

**Edge cases:**
- **Vault unavailable during write:** `CachedSecretProvider` caches (encrypted) in Redis + logs a warning. Retry/reconciliation is a follow-up story.
- **Redis unavailable:** `CachedSecretProvider` degrades to direct Vault access (catch `redis.ConnectionError`, log, delegate straight through).
- **Both Vault and Redis down during read:** Return 503 with clear error message.
- **Mixed mode migration:** During migration, MongoDB may contain both plaintext values and `SecretRef` markers. The resolve logic must handle both (if field is a dict with `$secret_ref` → resolve; else → treat as plaintext).
- **Secret rotation:** Vault KV v2 supports versioned secrets natively. Rotation can update the Vault path; Redis cache invalidates naturally via TTL expiry.
- **Token refresh race conditions:** `MongoCredentialStore.upsert` is already atomic (MongoDB `update_one` with `upsert=True`). The Vault write + Redis cache update is not atomic — if the process crashes between Vault write and Redis update, the next read will simply cache-miss and re-fetch from Vault.

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
6. **Scope of "all credential fields":** Should this also cover `identity` service secrets (`client_secret`, `keycloak` creds) and `rag` service secrets (`slack_bot_token`), or only `multi-agent`?
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

The `MongoSecretProvider` proposes using `_FieldCipher` — which already lives in `MongoCredentialStore`. If this cipher is needed in multiple places (and it now is — `MongoCredentialStore`, `RedisFlowStateStore`, and the new `CachedSecretProvider` all need Fernet), it should be extracted to a shared utility (e.g. `global_utils/crypto/field_cipher.py`), not duplicated.

### Risks to Existing System

**1. `ResourcesService.resolve()` is on the hot path**

Every LLM call, MCP tool invocation, and A2A agent interaction resolves resources. Adding a secret-resolution step (Redis/Vault lookup) to this path increases latency and introduces a new failure mode. If the secret provider is down, previously working workflows break.

**Mitigation:** The current system works with secrets inline in `cfg_dict`. If Vault mode is enabled, the resolution must have a sensible fallback (e.g. local cache with long TTL, or graceful degradation).

**2. Migration script must handle idempotency**

If the migration script runs twice (or crashes mid-run), it must not corrupt data. The design doesn't specify whether the migration is idempotent or what happens if a `SecretRef` marker is already present.

**3. `on_pre_save` hooks interact unpredictably**

MCP's `on_pre_save` (`multi-agent/lib/mas/elements/providers/mcp_server_client/config.py:91`) already moves `bearer_token` to the `credentials` collection. The design adds *another* interception layer in `ResourcesService` that scans for `SecretHint` fields. The order of operations matters — if the `SecretHint` scan runs before `on_pre_save`, the bearer token is externalized to Vault from `cfg_dict`; if after, it's already been moved to `credentials`. This interaction is not addressed.

### Recommended Improvements

1. **Don't store `SecretRef` markers in MongoDB.** Instead, always store the encrypted value in MongoDB (using existing Fernet), AND replicate to Vault when enabled. Read from cache → Vault → MongoDB (encrypted fallback). This avoids schema changes, Pydantic validation issues, and migration headaches.

2. **Extract `_FieldCipher` to `global_utils/crypto/field_cipher.py`** for reuse across `MongoCredentialStore`, `RedisFlowStateStore`, `CachedSecretProvider`, and any new secret-handling adapter.

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
6. **Clarify `on_pre_save` interaction** — document the order of operations for MCP tokens and whether Vault externalization happens before or after `on_pre_save`.
7. **Drop CSFLE from this story** — it's orthogonal infrastructure work that can't be properly designed until Vault is in place (if Vault serves as KMS).
8. **Resolve race condition on Vault read-modify-write** — use single-field paths or CAS.
9. **Make Redis encryption mandatory** — `CachedSecretProvider` must require an encryption key and refuse to start without one.
10. **Extract `_FieldCipher` to shared utility** — eliminate duplication across `MongoCredentialStore`, `RedisFlowStateStore`, and the new cache adapter.
11. **Acknowledge that current MongoDB encryption is app-level Fernet, not native CSFLE** — the design and ticket should be explicit about this distinction to avoid confusion about the security guarantees provided.

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
