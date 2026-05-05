# ---

**🏗️ Architecture Design Review (ADR)**

**Feature Name:** Migrate UnifAI Secrets to HashiCorp Vault via OpenShift Vault Operator — [GENIE-948](https://redhat.atlassian.net/browse/GENIE-948)

**Lead Developer:** Saar Fireshtein | **Date:** 2026-05-04 | **Priority:** High

### ---

**1. Executive Summary**

| Section | Developer Input |
| :---- | :---- |
| **Problem Statement** | UnifAI stores all sensitive credentials (Keycloak client secrets, encryption keys, Redis/RabbitMQ passwords, Slack tokens, OpenShift access tokens) in a private Git repository (`UnifAI-secrets`) and injects them via Kubernetes ConfigMaps through presync shell scripts. Secrets are exposed in Git history permanently, stored as plaintext ConfigMaps in etcd, and readable by anyone with cluster ConfigMap access. |
| **High-Level Solution** | Migrate all application secrets to the company's existing HashiCorp Vault instance (`vault.corp.redhat.com:8200`) using the OpenShift Vault Operator for pod-side injection and the HashiCorp Vault Jenkins Plugin for CI/CD-side access. Secrets will be injected as in-memory files at `/vault/secrets/` and consumed by a new `VaultFileSource` plugged into the existing `SharedConfig` pydantic-settings chain. |
| **Success Metrics** | Zero plaintext secrets in Git repositories or ConfigMaps. All pods start successfully using Vault-injected secrets. Vault audit logs capture every secret access. No downtime during migration (phased rollout). Old credentials rotated and revoked post-migration. |

### ---

**2. The "Where": Code & Data Changes**

| Area | Targeted Repositories / Files / Modules |
| :---- | :---- |
| **Frontend** | No changes. The UI does not handle secrets — it uses cookie-based auth via the Identity service proxy. |
| **Backend/APIs** | `global_utils/src/global_utils/config/sources.py` — new `VaultFileSource` class. `global_utils/src/global_utils/config/config.py` — add `VaultFileSource` to the `SharedConfig` source chain. No changes to `AppConfig` subclasses (`identity/config/app_config.py`, `multi-agent/config/app_config.py`, `backend/config/app_config.py`, `rag/config/app_config.py`) — they inherit the new source automatically. |
| **Database** | No schema changes. MongoDB is accessed without authentication today; adding Mongo auth is out of scope (separate story). |
| **Config/Infra** | **Helm charts** (13 deployment templates): add Vault Agent Injector annotations, remove `envFrom` references to security ConfigMaps/Secrets. **Presync scripts** (5 files): remove secret-bearing `--from-literal` args, keep non-secret config. **Jenkins pipeline** (`ci/pipeline-deploy.groovy`): replace `UnifAI-secrets` checkout with Vault Jenkins Plugin bindings. **Vault** (external): new KV paths under `apps/automation-and-tools/unifai/`, KSA auth roles, scoped policies. **New env vars**: none for application code. **Removed env sources**: `UnifAI-secrets/.env*` files, `identity-config` ConfigMap (secrets portion), `multiagent-be-security` ConfigMap (secrets portion), `unifai-rag-secrets` Secret. |

### ---

**3. Architecture & AI Strategy**

| Component | Design Details |
| :---- | :---- |
| **System Diagram** | See Data Flow section below. |
| **LLM / Model** | Not applicable — this is an infrastructure/security change with no AI/LLM component. |
| **Context Strategy** | Not applicable. |
| **Output Validation** | Not applicable. |

**3.1 Vault Secret Structure**

Secrets are organized under the existing `apps/automation-and-tools` AppRole in Vault KV v2:

```
apps/automation-and-tools/unifai/
├── staging/
│   ├── shared          # redis_password, rmq_username, rmq_password, HF_TOKEN,
│   │                   # admin_allowed_users, secret_key, umami_*
│   ├── identity        # keycloak_base_url, client_id, client_secret, keycloak_realm
│   ├── multiagent      # CREDENTIAL_ENCRYPTION_KEY, MCP_AUTH_STATE_SECRET
│   ├── rag             # default_slack_bot_token, default_slack_user_token
│   ├── redis           # redis_username, redis_password, redis_port, redis_insight_port
│   └── cluster         # preprod_access_token (Jenkins-only, not pod-injected)
└── production/
    ├── shared
    ├── identity
    ├── multiagent
    ├── rag
    ├── redis
    └── cluster
```

**3.2 Authentication**

Kubernetes Service Account (KSA) auth method bound to the UnifAI namespace `tag-ai--pipeline`. Each service's existing Helm `ServiceAccount` is bound to a Vault role scoped to `shared` + its own service path.

**3.3 Application Config Integration**

New `VaultFileSource` in `global_utils/src/global_utils/config/sources.py`:

```
class VaultFileSource(ConfigSource):
    def __init__(self, base_path: str = "/vault/secrets", file_pattern: str = "*.env")
    def load(self) -> Dict[str, Any]
        # If base_path does not exist → return {} (graceful no-op for local dev)
        # Read all matching files, parse as KEY=VALUE (dotenv format)
        # Return merged dict (service-specific overrides shared)
```

Inserted into `SharedConfig.settings_customise_sources` between `env` and `DotEnvSource`:

```
init → env → VaultFileSource → DotEnvSource → YamlSource → JsonSource → fs
```

**3.4 Pod Injection Flow**

```
Pod created → Vault Agent init-container starts (injected by Operator via annotations)
→ Agent authenticates to Vault using pod ServiceAccount JWT (KSA auth)
→ Agent reads secrets from KV paths (e.g., .../staging/shared, .../staging/identity)
→ Agent writes .env-formatted files to /vault/secrets/ (in-memory tmpfs)
→ Agent exits (agent-pre-populate-only: true)
→ App container starts
→ SharedConfig loads: env (ConfigMaps) → VaultFileSource (/vault/secrets/) → .env → yaml → json
→ Application runs with merged config
```

**3.5 Helm Annotation Pattern**

Each deployment gets Vault annotations via `podAnnotations` in values:

```yaml
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/role: "unifai-<service>"
vault.hashicorp.com/agent-inject-secret-shared.env: "apps/automation-and-tools/unifai/<env>/shared"
vault.hashicorp.com/agent-inject-secret-<service>.env: "apps/automation-and-tools/unifai/<env>/<service>"
vault.hashicorp.com/agent-pre-populate-only: "true"
vault.hashicorp.com/preserve-secret-case: "true"
```

**3.6 Jenkins Pipeline Changes**

Replace `UnifAI-secrets` Git checkout + `--env-file` injection with the HashiCorp Vault Jenkins Plugin:

```groovy
withVault(
    configuration: [vaultUrl: 'https://vault.corp.redhat.com:8200', engineVersion: 2],
    vaultSecrets: [
        [path: 'apps/automation-and-tools/unifai/<env>/cluster',
         secretValues: [[envVar: 'token', vaultKey: 'access_token']]]
    ]
) {
    sh("oc login --token=${token} --server=${ClusterAddress}")
}
```

**3.7 Presync Script Changes**

| Script | Secrets Removed | Remaining Non-Secret Config |
| :----- | :-------------- | :-------------------------- |
| `identity-presync.sh` | `client_secret`, `secret_key` | `admin_allowed_users`, `keycloak_base_url`, `client_id`, `keycloak_realm` (or move all to Vault) |
| `multiagent-presync.sh` | `CREDENTIAL_ENCRYPTION_KEY`, `MCP_AUTH_STATE_SECRET` | `admin_allowed_users` |
| `rag-presync.sh` | `default_slack_bot_token`, `default_slack_user_token` | Entire Secret removed — tokens from Vault |
| `redis-presync.sh` | `REDIS_PASSWORD`, `RI_REDIS_PASSWORD` | `REDIS_PORT`, `REDIS_USERNAME`, `RI_APP_PORT`, `RI_REDIS_PORT`, `RI_REDIS_USERNAME` |
| `backend-presync.sh` | None (only `admin_allowed_users` today) | `admin_allowed_users` stays |

**3.8 Phased Rollout Plan**

| Phase | Scope | Rollback |
| :---- | :---- | :------- |
| **Phase A** | Add `VaultFileSource` to `SharedConfig` (no-op when `/vault/secrets/` absent). Deploy to all services. | Remove source from chain. |
| **Phase B** | Enable Vault annotations on Identity (staging). Validate SSO login works. | Remove annotations; old ConfigMap still exists. |
| **Phase C** | Enable Vault for all remaining services (staging). | Remove annotations per-service. |
| **Phase D** | Enable Vault on production. | Same as staging rollback. |
| **Phase E** | Remove old presync secret literals, delete `identity-config` secrets portion, `multiagent-be-security` secrets, `unifai-rag-secrets`. | Re-run presync scripts from backed-up env files. |
| **Phase F** | Rotate all credentials to new values in Vault. Remove/archive `UnifAI-secrets` repo. | N/A — point of no return after rotation. |

### ---

**4. Risk & Reliability (AI-Era Checklist)**

| Risk | Mitigation Plan |
| :---- | :---- |
| **LLM Failure** | Not applicable — no LLM component in this change. |
| **Data Privacy** | This change *improves* data privacy by removing plaintext secrets from Git and ConfigMaps. Vault provides audit logging for every secret access. |
| **Cost Control** | HashiCorp Vault is already provisioned and paid for by the company. No additional cost. The Vault Agent sidecar adds ~30MB memory per pod (init-only mode). |
| **Performance** | Vault Agent runs as an init-container (`agent-pre-populate-only: true`), adding 2-5 seconds to pod startup. No runtime performance impact after startup. |

**Additional Infrastructure Risks:**

| Risk | Mitigation Plan |
| :---- | :---- |
| **Vault unavailable at pod startup** | Vault Agent init-container blocks pod startup — pod enters `Init:CrashLoopBackOff`. This is desired (fail loud). Monitor with existing pod health alerts. |
| **Secret rotation** | Phase 1 uses `agent-pre-populate-only: true` (secrets loaded once at startup). For dynamic rotation, a future iteration can switch to sidecar mode. Acceptable since current secrets are also static. |
| **Backward compatibility during rollout** | Phased rollout (A→F above). At no point does a pod lose access to secrets — either Vault or old ConfigMap provides them. |
| **UI Dockerfile copies TLS certificates** | `ui/deployment/Dockerfile` copies certs from `UnifAI-secrets/certificates/`. Certificates are out of scope — they stay as build-time artifacts until a separate cert-manager story. |
| **Key naming conflicts across Vault paths** | `VaultFileSource` loads `shared.env` first, then service-specific `.env`. Service-specific keys override shared (last-writer-wins). Mirrors current `envFrom` ordering. |
| **Git history exposure** | Even after removing `UnifAI-secrets`, Git history retains old secrets. All exposed credentials must be rotated to new values in Vault (Phase F). |
| **Jenkins upgrade dependency** | Vault Jenkins Plugin requires Jenkins version upgrade (GENIE-1526). Pod-side Vault injection is independent — decouple if Jenkins upgrade is delayed. |

### ---

**5. Reviewer's Feedback**

| Status | Feedback / Required Changes |
| :---- | :---- |
| **[ ] Approved** | |
| **[ ] Revise** | |
