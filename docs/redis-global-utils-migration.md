# Redis in `global_utils`: migration plan

This document describes a step-by-step migration to centralize Redis configuration and client construction in **`global_utils`**, so **identity**, **multi-agent**, and other services share one definition of host, port, database, password, and related options.

A follow-on step is to add Flask **`before_request`** (or equivalent) hooks that load session context from Redis; that work assumes this migration is done so Redis access is consistent everywhere.

---

## 1. Inventory (current state)

- **`global_utils`:** `SharedConfig` exposes **`redis_ip`** and **`redis_port`** only. **`get_redis_url()`** builds `redis://ip:port` with **no password** and **no database index**.
- **Identity:** Uses **`RedisKVStore`** with **`AppConfig`** fields such as **`redis_password`**, **`redis_db`**, **`decode_responses`** — richer than `SharedConfig` today.
- **Multi-agent:** **`RedisChannelFactory`** uses **`get_redis_url()`** → no password path; assumes a single URL.

**Goal:** one canonical way to build Redis settings and clients from shared config / environment variables.

---

## 2. Extend `SharedConfig` (single source of truth)

Add fields that identity (and other services) need, for example:

- **`redis_db`** (default aligned with current behavior per service, or a sensible global default)
- **`redis_password`** (optional / `None`)
- **`redis_decode_responses`** (bool, if used project-wide)
- Optional later: **`redis_ssl`**, **`redis_username`** (ACL / TLS)

Define **environment variable names** once and map them in the existing `SharedConfig` loading path.

**Checkpoint:** services stop hard-coding Redis connection details in multiple places.

---

## 3. Add a small Redis module in `global_utils`

Keep the surface **small** (no business logic):

- **`build_redis_client()`** → returns **`redis.Redis(...)`** from host, port, db, password, `decode_responses`, etc.
- Optionally revise **`get_redis_url()`**:
  - Either support **password + db** in the URL (mind **URL-encoding** special characters in passwords), **or**
  - Deprecate URL-only usage for components that need auth and standardize on **`build_redis_client()`**.

**Decision (multi-agent):** it currently uses **`ConnectionPool.from_url(redis_url)`**. Choose one approach:

- **A)** Enrich **`get_redis_url()`** to include credentials and db when present, **or**
- **B)** Switch multi-agent to a **pool built from the same parameters as `build_redis_client`** (phase 2 if minimizing churn in phase 1).

---

## 4. KV store adapter placement (optional sub-step)

- **Option A:** Move **`RedisKVStore`** (or a thin wrapper) into `global_utils` if multiple services need the same hash/KV behavior.
- **Option B:** Keep **`RedisKVStore`** in **identity** but construct the underlying **`redis.Redis`** via **`global_utils.build_redis_client()`** to avoid duplicating connection logic.

Avoid pulling identity-only domain rules into `global_utils`.

---

## 5. Wire identity to `global_utils`

- Replace ad-hoc **`RedisKVStore(host=..., port=..., ...)`** with config driven by **`SharedConfig`** (or **`AppConfig`** that **inherits or composes** shared Redis fields — avoid two competing Redis sections long term).
- Run smoke tests: ping, session read/write, TTL behavior unchanged.

---

## 6. Wire multi-agent to `global_utils`

- Replace **`get_redis_url()`** with the chosen password-aware URL **or** shared pool/client builder.
- Validate Redis Streams and monitors against the same Redis instance (or document separate DBs — see below).

---

## 7. Remove duplication

- Remove or deprecate duplicate helpers in identity/bootstrap.
- Document whether **`get_redis_url()`** is legacy vs **`build_redis_client()`**.

---

## 8. Packaging

- Ensure **`pyproject.toml` / Docker** for **identity** and **multi-agent** declare dependency on **`global_utils`** and install path is correct in CI.

---

## 9. Ops / secrets

- Document env vars per environment (staging/prod).
- Align Helm / `.env` so all consumers that **must share the same logical store** use the same **host, password, and db** where intended.

---

## 10. Verification checklist

- [ ] Identity: login, `/auth/user`, refresh, logout; Redis keys and TTL as before.
- [ ] Multi-agent: stream read/write / monitor paths still work.
- [ ] No service still uses a bare **`redis://ip:port`** when Redis requires a password.

---

## Multiple Redis databases (e.g. multi-agent: DB 0 + DB 1)

Today multi-agent may use **Redis DB 0** for streams; **identity** may use **DB 1** for sessions. After centralizing config, avoid hard-coding **`0`** vs **`1`** in code.

### Generic patterns

1. **Config-only separation (recommended for clarity)**  
   - **`REDIS_DB_STREAMS`** (or `redis_db_streams`) and **`REDIS_DB_SESSIONS`** (or `redis_db_sessions`), each defaulting sensibly.  
   - **`build_redis_client(db=...)`** or two thin factories: **`get_redis_streams_client()`** / **`get_redis_sessions_client()`** that read the right integer from config.

2. **Single `redis_db` + key prefixes**  
   - One database index; isolate streams vs session keys with **prefixes** (`session:`, `stream:`). Fewer DB switches; one connection pool sometimes simpler.

3. **Separate Redis instances**  
   - Only if you need hard isolation (different clusters); usually overkill for “db 0 vs 1” on the same server.

### Practical recommendation

- Put **defaults in `SharedConfig`** (e.g. `redis_db_default=0`, `redis_db_sessions=1`) and let **multi-agent** explicitly request **`db=config.redis_db_streams`** vs identity **`db=config.redis_db_sessions`**, both via **`build_redis_client(db=...)`**.  
- Document that **changing DB indices** is an **ops** change, not scattered literals in adapters.

---

## Follow-on: `before_request` (not part of this migration file’s implementation)

- Instantiate **one** Redis client/pool at **app startup**, not per request.
- In **`before_request`**: decode Flask **`session`**, read **`session_id`**, **`HGETALL`** from the **sessions** Redis db, attach **`g.session_data`** / **`g.current_user`** or return **401**.

This plan stops at **shared Redis wiring**; the hook layer depends on it.
