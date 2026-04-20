# Redis in `global_utils`: migration plan

This document describes a step-by-step migration to centralize Redis configuration and client construction in **`global_utils`**, so **identity**, **multi-agent**, and other services share one definition of host, port, database, password, and related options.

A follow-on step is to add Flask **`before_request`** (or equivalent) hooks that load session context from Redis; that work assumes this migration is done so Redis access is consistent everywhere.

---

## Progress

| Step | Description | Status |
|------|-------------|--------|
| **1** | Inventory (current state) | **Done** |
| **2** | Extend `SharedConfig` | **Done** (`redis_password`, `redis_db`, `redis_decode_responses`, `config.json` wiring) |
| **3** | Small Redis module in `global_utils` | **Done** — `global_utils.redis.client.build_redis_client()` (singleton via `lru_cache(maxsize=1)`) |
| **4** | KV store adapter placement | Pending |
| **5–10** | Wire identity, multi-agent, cleanup, packaging, ops, verification | Pending |

---

## 1. Inventory (current state) — **done**

- **`global_utils`:** `SharedConfig` includes **`redis_ip`**, **`redis_port`**, **`redis_password`**, **`redis_db`**, **`redis_decode_responses`**; **`config.json`** maps env vars.
- **`get_redis_url()`** may still be minimal (`redis://ip:port`); password/db for URL-based callers can be a follow-up or replaced by **`build_redis_client()`**.
- **Identity:** **`RedisKVStore`** + **`AppConfig`** for Redis connection; **`AuthManager`** stores session hashes in Redis keyed by **`session_id`** from Flask **`session`**.
- **Multi-agent:** **`RedisChannelFactory`** uses **`get_redis_url()`** + **`ConnectionPool.from_url`**.

**Goal:** one canonical way to build Redis settings and clients from shared config / environment variables.

---

## 2. Extend `SharedConfig` (single source of truth) — **done**

Implemented fields include:

- **`redis_password`** (optional)
- **`redis_db`**
- **`redis_decode_responses`**
- Optional later: **`redis_ssl`**, **`redis_username`** (ACL / TLS)

---

## 3. Add a small Redis module in `global_utils` — **done**

- **`global_utils.redis.client.build_redis_client()`** → returns a shared **`redis.Redis`** instance per process, built from **`SharedConfig`** (`host`, `port`, `db`, `password`, `decode_responses`). Singleton pattern: **`@functools.lru_cache(maxsize=1)`**.
- Optionally revise **`get_redis_url()`** for callers that require a URL string (password URL-encoding, `/db` path).

**Multi-agent note:** it still uses **`ConnectionPool.from_url(get_redis_url())`** until step **6** switches it to a password-aware URL **or** a pool built from the same config as **`build_redis_client()`**.

---

## Identity module: what stays vs what can move to `global_utils`

This split guides step **4** (KV adapter) and later wiring. **No OAuth or route logic belongs in `global_utils`.**

### Identity-specific (stay in identity or a dedicated auth service)

- **`AuthManager`:** Keycloak via Authlib (**`authorize_redirect`**, **`authorize_access_token`**, **`userinfo`**, refresh), redirects, **`state`** with the UI, **`AppConfig`** Keycloak/frontend/admin fields.
- **HTTP routes:** `/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/user`, `/api/auth/refresh`.
- **Rules:** **`is_authenticated`**, **`_check_admin_permission`**, **`get_user_info`** field selection, **`_ttl_seconds_until_session_expires`** tied to the app session model.
- **Protocol:** Flask **`session['session_id']`** → Redis hash key; **hash field layout** is the **contract** other services must respect if they read the same Redis data.

### Generic / reusable (candidates for `global_utils`)

- **`RedisKVStore`:** thin **`redis.Redis`** wrapper (string + hash ops, TTL on hash keys). No Keycloak.
- **Using **`build_redis_client()`** inside that adapter** (or injecting the client) — wiring only.
- **Operational fix:** deleting a whole Redis key vs misusing **`HDEL`** — adapter concern, not identity business logic.

### Cross-service caveat

**“Other modules read the cookie and load the hash”** only works if:

- The **same Flask `session` cookie** is **sent to that backend’s origin**, which usually means **one API hostname** (reverse proxy) or **shared parent `Domain`** on the cookie — see **Sharing the session cookie across Flask backends** below; **or**
- Services **do not** decode Flask session themselves and instead **call identity** or use a **gateway**-issued token.

| Area | Identity-specific | Candidate for `global_utils` |
|------|-------------------|-------------------------------|
| Keycloak / OAuth / routes | Yes | No |
| Session TTL policy from `session_expires_at` | Identity policy | Math helper could be generic |
| **`RedisKVStore`** | Implementation is generic | Yes (optional move) |
| **`KVStore` port** | Hex boundary — your choice | Stay in identity or shared package |
| **`build_redis_client`** | No | Yes (already added) |
| Flask **`session` → `session_id` → Redis** | Identity session protocol | Shared middleware only if same app/cookie story |

---

## 4. KV store adapter placement (optional sub-step)

- **Option A:** Move **`RedisKVStore`** into `global_utils` if multiple services need the same hash/KV behavior.
- **Option B:** Keep **`RedisKVStore`** in **identity** but construct the underlying **`redis.Redis`** via **`global_utils.build_redis_client()`** to avoid duplicating connection logic.

Avoid pulling identity-only domain rules into `global_utils`.

---

## 5. Wire identity to `global_utils`

- Replace ad-hoc **`RedisKVStore(host=..., port=..., ...)`** with **`build_redis_client()`**-driven wiring (or **`SharedConfig`**-only construction) — avoid two competing Redis sections long term.
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

## Multiple Redis databases (e.g. multi-agent: DB 0 + identity: DB 1)

Today multi-agent may use **Redis DB 0** for streams; **identity** may use **DB 1** for sessions. After centralizing config, avoid hard-coding **`0`** vs **`1`** in code.

### Generic patterns

1. **Config-only separation** — e.g. **`redis_db_streams`** and **`redis_db_sessions`**, or **`build_redis_client(db=...)`** with explicit indices.
2. **Single `redis_db` + key prefixes** — one DB; namespaces like `session:`, `stream:`.
3. **Separate Redis instances** — only if you need hard isolation.

---

## Sharing the session cookie across Flask backends (browser behavior)

The UI does **not** manually send **`session_id`**; it sends **whatever cookies** the browser has for **that request’s origin**. The Flask **`session`** cookie (containing **`session_id`** inside the signed payload) is set by **whoever handled login** — usually the **identity** service.

For **multiple Flask apps** (different hosts/ports) to receive the **same** session cookie:

1. **Single API origin (recommended)**  
   Put all backends behind **one public URL** (reverse proxy / ingress), e.g. `https://api.example.com/identity/...`, `https://api.example.com/agent/...`. The browser sees **one origin**; **`withCredentials`** sends the **`session`** cookie on every request to that origin.

2. **Shared parent domain**  
   Set **`SESSION_COOKIE_DOMAIN=.example.com`** (and consistent **`Path`**, **`Secure`**, **`SameSite`**) so **`app1.example.com`** and **`app2.example.com`** both receive the cookie. Requires **HTTPS** in production for **`SameSite=None`** cross-site flows.

3. **Different origins (e.g. `localhost:3000` UI + `localhost:5000` API)**  
   Different **host:port** = different origins. The cookie is tied to the **API** origin that set it; another Flask on **`localhost:8000`** will **not** get that cookie unless you **proxy** so the browser only talks to **one** API origin.

4. **Alternative to cookie fan-out**  
   **API gateway** validates the session once, or clients send a **Bearer token**; downstream services trust the gateway or validate the token — avoids every Flask decoding the same cookie.

**Summary:** To have “the same session” everywhere, align on **one browser origin for API calls** or **shared cookie domain**; otherwise use **tokens** or **identity introspection**.

---

## Follow-on: `before_request` (implementation TBD)

- Instantiate **one** Redis client/pool at **app startup**, not per request.
- In **`before_request`**: decode Flask **`session`**, read **`session_id`**, **`HGETALL`** from the **sessions** Redis db, attach **`g.session_data`** / **`g.current_user`** or return **401**.

This plan stops at **shared Redis wiring** for steps 1–3; the hook layer depends on it.
