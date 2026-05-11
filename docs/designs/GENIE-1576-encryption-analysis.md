# GENIE-1576 — Encryption Analysis: MongoDB, Redis, and Application-Level Options

**Ticket:** GENIE-1576  
**Date:** 2026-05-07  
**Purpose:** Evaluate encryption options across the storage layers relevant to the Vault secret management story.

---

## 1. Current State of Encryption in the Codebase

| Secret Type | Storage Location | Encrypted? | Method | Notes |
|-------------|-----------------|------------|--------|-------|
| OAuth access/refresh tokens | `credentials` collection (MongoDB) | Yes (if key set) | App-level Fernet (`_FieldCipher`) | Only `access_token` and `refresh_token` |
| MCP bearer/API key (after save) | `credentials` collection (MongoDB) | Yes (if key set) | App-level Fernet (`_FieldCipher`) | Moved via `on_pre_save` hook |
| OAuth client id/secret | `server_configs` collection (MongoDB) | **No** | Plaintext | — |
| LLM `api_key` | `resources.cfg_dict` (MongoDB) | **No** | Plaintext | — |
| A2A `bearer_token` | `resources.cfg_dict` (MongoDB) | **No** | Plaintext | No `on_pre_save` hook |
| SSH `password` | `resources.cfg_dict` (MongoDB) | **No** | Plaintext | — |
| OC `token` | `resources.cfg_dict` (MongoDB) | **No** | Plaintext | — |
| OAuth pending state | `auth_pending:*` keys (Redis) | Yes (if key set) | App-level Fernet | In `RedisFlowStateStore` |
| Session stream events | Redis Streams | **No** | Plaintext | — |

**Key finding:** Only `credentials.access_token`, `credentials.refresh_token`, and Redis OAuth pending state are encrypted. Everything else — including LLM API keys, A2A tokens, SSH passwords, and OAuth client secrets — is stored in plaintext.

---

## 2. MongoDB Encryption Options

### 2a. Application-Level Fernet (Current Approach)

**How it works:** Application code calls `Fernet.encrypt(value)` before writing to MongoDB and `Fernet.decrypt(value)` after reading. The database sees opaque blobs. Implemented in `_FieldCipher` within `MongoCredentialStore` (`multi-agent/adapters/outbound/mongo/auth_token_repository.py`).

**Advantages:**
- Dead simple — `_FieldCipher` is ~20 lines of code
- Database-agnostic — works on any MongoDB deployment (Atlas, self-hosted, DocumentDB, local dev) with no infrastructure dependencies
- Selective and flexible — each adapter chooses which fields to encrypt
- No schema coupling — no JSON schema declarations or encryption metadata on collections
- Portable — the same Fernet key works for Redis, Mongo, files, anything. `credential_encryption_key` is already shared across `MongoCredentialStore` and `RedisFlowStateStore`

**Disadvantages:**
- You own the entire lifecycle — key rotation, re-encryption, error handling, the "is this already encrypted?" prefix check (`gAAAAAB`), all on you
- Cannot query on encrypted fields — you can't filter by `access_token` value (not typically needed for secrets, but it's a constraint)
- Easy to forget — nothing prevents a new adapter from storing secrets in plaintext. It's opt-in, not enforced. This is evidenced by the fact that `MongoResourceRepository`, `MongoServerConfigStore`, and everything in `resources.cfg_dict` currently skips encryption
- No audit trail — if someone reads the raw Mongo document they see the blob, but there's no record of who decrypted it or when

### 2b. MongoDB Native CSFLE (Client-Side Field Level Encryption)

**How it works:** The MongoDB driver encrypts/decrypts transparently using a JSON schema that declares which fields are encrypted. A local process (`mongocryptd` or `crypt_shared` library) handles the cryptography. Data Encryption Keys (DEKs) are stored in a `__keyVault` collection, wrapped by a Customer Master Key (CMK) from a KMS provider (HashiCorp Vault, AWS KMS, Azure Key Vault, GCP KMS, or a local key file).

**Advantages:**
- **Enforced at the driver level** — if a field is declared encrypted, it's *always* encrypted. No one can accidentally write plaintext. This is the primary benefit.
- **Transparent to application code** — services read and write normal Python dicts. Encryption/decryption is invisible. No `_FieldCipher`, no prefix checks.
- **Supports deterministic encryption** — encrypted fields can still be used in equality queries (e.g. `find_by_server` on `access_token` would work if needed).
- **Key hierarchy** — DEK → CMK separation means you can rotate the CMK without re-encrypting all data. The KMS provider controls the CMK.
- **Server-side enforcement** — even with raw `mongosh` access or a compromised backup, the encrypted fields are opaque. The server never sees plaintext.
- **Audit via KMS** — every CMK unwrap operation goes through Vault (or whichever KMS), providing an audit trail of decryption events.

**Disadvantages:**
- **Significant infrastructure overhead** — requires `mongocryptd` (Enterprise-only) OR `crypt_shared` (Community, but a native library that must be deployed alongside every service). Every pod that talks to Mongo needs this binary.
- **KMS dependency at startup** — the driver must unwrap the DEK at connection time. If Vault/KMS is down, Mongo connections fail entirely. With Fernet, you just can't decrypt — you can still connect and read unencrypted fields.
- **Schema rigidity** — encrypted fields must be declared upfront in a JSON schema per collection. The `cfg_dict: Dict[str, Any]` pattern (arbitrary JSON blobs with secret fields varying per element type) is a **poor fit** for CSFLE, because the schema engine needs to know exact field paths. A field at `cfg_dict.api_key` in one document and `cfg_dict.bearer_token` in another means you'd need a schema covering every possible element config — or restructure how configs are stored.
- **Not all field types work** — CSFLE has restrictions (no arrays of encrypted values, no encrypted fields inside arrays, etc.)
- **Adds ~15-30ms to connection setup** — DEK cache warmup and KMS round-trip on first use
- **Testing complexity** — local dev and CI need a `crypt_shared` library or a mock KMS, complicating the test harness

### 2c. Assessment for This Codebase

The main advantage of native CSFLE is **enforcement** — you can't accidentally skip it.

The main disadvantage is that **the current data model fights it.** The `cfg_dict: Dict[str, Any]` pattern — where every element type stores different secret fields at different paths in an untyped dict — is fundamentally at odds with CSFLE's requirement for a fixed JSON schema declaring encrypted field paths. To use CSFLE, you would need one of:

1. **Enumerate every possible secret field path** across every element type in a single schema — fragile, breaks when new elements are added.
2. **Restructure storage** so secrets are pulled out of `cfg_dict` into a normalized structure with known paths — a significant refactor.
3. **Encrypt the entire `cfg_dict` as a blob** — loses all queryability and defeats the "field-level" purpose of CSFLE.

None of these are cheap. And option 2 is essentially what the Vault integration already accomplishes — externalizing secrets out of `cfg_dict`.

**Recommendation:** If Vault integration proceeds (the point of GENIE-1576), CSFLE becomes less compelling because secrets won't live in MongoDB in the primary path. For the fallback/local-dev path, app-level Fernet is pragmatic and sufficient — as long as it is **extended to cover `resources.cfg_dict` and `server_configs.client_secret`**, which are the gaps today. The risk of "forgetting to encrypt" can be mitigated by a shared `SecretField` marker + a pre-save hook that enforces encryption, without the infrastructure cost of CSFLE.

CSFLE makes more sense as a follow-up story *if* the team later decides MongoDB should be a long-term secret store (not just a fallback), *and if* the `cfg_dict` schema issue is resolved first. Notably, if Vault is the chosen KMS for CSFLE, it can't be properly designed until Vault integration is complete anyway.

---

## 3. Redis Encryption Options

### 3a. At-Rest Encryption

**Redis does not provide native at-rest encryption.** Data in memory and in RDB/AOF persistence dumps is plaintext. This is by design — Redis optimizes for speed, and encrypting the memory store would defeat its purpose.

Available options:

| Option | What It Covers | Limitations |
|--------|---------------|-------------|
| **Application-level Fernet** (current for OAuth state, proposed for secret cache) | Values are encrypted before `SETEX`, decrypted after `GET`. Redis sees opaque blobs. | You manage the lifecycle. Must be done consistently. |
| **Disk-level encryption** (dm-crypt, LUKS, EBS encryption) | Protects RDB/AOF dumps on disk | Data in memory is still plaintext. A `DEBUG OBJECT` or memory inspection could expose values. |
| **Redis Enterprise encryption-at-rest** | Covers persistence files | Paid product. Still only covers disk, not in-memory data. |

**For secrets, application-level Fernet is the only real option.** The existing `RedisFlowStateStore` already implements this pattern — Fernet-encrypt before `SETEX`, decrypt after `GET`. The proposed `CachedSecretProvider` must follow the same pattern, with the additional constraint that **encryption must be mandatory** (not optional as it is for `RedisFlowStateStore`).

### 3b. In-Transit Encryption (TLS)

Redis 6+ supports TLS connections. The client connects via `rediss://` (double `s`) instead of `redis://`.

**Current state:** The codebase does not use TLS for Redis connections. `get_redis_url()` in `global_utils/src/global_utils/utils/util.py` builds plain `redis://` URLs. All Redis clients — `RedisKVStore`, `RedisFlowStateStore`, `RedisChannelFactory` — connect over unencrypted channels.

**What's needed:** Add `redis_tls: bool` and `redis_ca_cert: str` to `SharedConfig`, update `get_redis_url()` to emit `rediss://` URLs when TLS is enabled, and pass SSL parameters to the `redis.Redis` / `ConnectionPool` constructors.

This is a separate, smaller story but should be flagged as a dependency for production-grade secret management — even Fernet-encrypted blobs shouldn't traverse the network in plaintext if avoidable.

### 3c. Access Control (ACLs)

Redis 6+ supports per-user ACLs with key-pattern restrictions. For example, the secret cache keys (`secret:*`) could be restricted to a specific Redis user that only the multi-agent service authenticates as, while session stream keys remain accessible to a different user.

**Current state:** The codebase uses a single `redis_password` with no per-user ACLs.

**Relevance:** ACLs add defense-in-depth but are not a substitute for encryption. They prevent unauthorized Redis clients from reading secret keys, but anyone with the allowed credentials (or network access to an unauthed Redis) can still see the raw values. Worth considering in a hardening pass, but not a blocker for this story.

---

## 4. Summary Comparison

| Concern | MongoDB | Redis |
|---------|---------|-------|
| Native field-level encryption | CSFLE (exists, but poor fit for `cfg_dict` schema) | Does not exist |
| In-transit encryption | TLS (not currently used in codebase) | TLS via `rediss://` (not currently used in codebase) |
| At-rest encryption (server-side) | Encrypted Storage Engine (Enterprise only) | Enterprise only, disk-level only, not in-memory |
| At-rest encryption (application) | Fernet (`_FieldCipher`) — partial coverage | Fernet (`RedisFlowStateStore`) — partial coverage |
| **Best option for secrets in this codebase** | **App-level Fernet** (pragmatic, extend to cover gaps) | **App-level Fernet** (only real option, make mandatory) |

---

## 5. Recommendations for GENIE-1576

1. **Keep application-level Fernet** as the encryption method for both MongoDB fallback and Redis cache. Extend coverage to all secret fields (currently only `credentials.access_token`/`refresh_token` and Redis OAuth state are encrypted).

2. **Make Redis encryption mandatory** for the secret cache. Unlike `RedisFlowStateStore` where Fernet is optional, the `CachedSecretProvider` must refuse to start without an encryption key.

3. **Extract `_FieldCipher` to a shared utility** (`global_utils/crypto/field_cipher.py`) so it can be reused across `MongoCredentialStore`, `RedisFlowStateStore`, `CachedSecretProvider`, and future adapters without duplication.

4. **Add TLS for Redis connections** (`rediss://`) as a separate but related story. Secrets — even encrypted — should not traverse the network in plaintext.

5. **Add TLS for MongoDB connections** similarly. Current `MongoClient` calls use plain `mongodb://{host}:{port}/` with no TLS options.

6. **Defer CSFLE** to a future story. It cannot be effectively designed until (a) Vault integration is complete (Vault would serve as the KMS), and (b) the `cfg_dict` schema issue is addressed. The `cfg_dict: Dict[str, Any]` pattern is fundamentally incompatible with CSFLE's fixed-schema requirement.

7. **Introduce a `SecretField` domain marker** (distinct from `SecretHint`, which is a UI concern) to explicitly declare which config fields contain secrets. Use this marker in a pre-save hook to enforce encryption, closing the gap where new adapters could accidentally store secrets in plaintext.
