## PHASE 1: DESIGN

**Ticket:** [GENIE-948](https://redhat.atlassian.net/browse/GENIE-948) — Migrate UnifAI Secrets to HashiCorp Vault via OpenShift Vault Operator

---

### 1. Overview

**Problem statement:** UnifAI stores all sensitive credentials (Keycloak client secrets, encryption keys, Redis/RabbitMQ passwords, Slack tokens, OpenShift access tokens) in plaintext inside a private Git repository (`UnifAI-secrets`) and injects them via Kubernetes ConfigMaps — not even Kubernetes Secrets — through presync shell scripts. This leaves secrets exposed in Git history, in etcd unencrypted, and visible to anyone with cluster read access to ConfigMaps.

**Proposed solution:** Migrate all UnifAI secrets to the company's existing HashiCorp Vault instance (`vault.corp.redhat.com:8200`) using the OpenShift Vault Operator (Agent Injector). Secrets will be stored under `apps/automation-and-tools/unifai/` in Vault, injected into pods as in-memory files at `/vault/secrets/`, and loaded by the application through a new `VaultFileSource` plugged into the existing `SharedConfig` pydantic-settings chain. The Jenkins deploy pipeline will use the HashiCorp Vault Jenkins Plugin to pull deploy-time secrets instead of the `UnifAI-secrets` Git checkout.

**Success metrics / acceptance criteria:**

- All secrets currently in `UnifAI-secrets/.env*` files are stored in Vault under `apps/automation-and-tools/unifai/{env}/{service}`
- Pods receive secrets via Vault Agent sidecar injection (in-memory `tmpfs` volume at `/vault/secrets/`)
- Application code reads secrets from injected files via the new `VaultFileSource` in `SharedConfig`
- Presync scripts (`identity-presync.sh`, `multiagent-presync.sh`, `rag-presync.sh`, `redis-presync.sh`, `backend-presync.sh`) no longer create ConfigMaps/Secrets containing credentials
- Jenkins pipeline uses the Vault plugin instead of `UnifAI-secrets` Git checkout for deploy-time secrets
- Old secrets in GitHub, ConfigMaps, and plaintext `.env` files are removed and rotated
- Existing functionality is unchanged — all services start and operate normally
- Vault audit logs capture every secret access

---

### 2. Affected Components

| Layer | Component | Action (New/Modified) | File Path |
|-------|-----------|----------------------|-----------|
| Adapter (Config) | `VaultFileSource` | **New** | `global_utils/src/global_utils/config/sources.py` |
| Adapter (Config) | `SharedConfig` | **Modified** | `global_utils/src/global_utils/config/config.py` |
| Adapter (Helm) | Identity deployment | **Modified** | `helm/shared-resources/identity/templates/deployment.yaml` |
| Adapter (Helm) | Multiagent BE deployment | **Modified** | `helm/multiagent/be/templates/be-deployment.yaml` |
| Adapter (Helm) | Multiagent Temporal Worker deployment | **Modified** | `helm/multiagent/temporal-worker/templates/be-deployment.yaml` |
| Adapter (Helm) | Backend deployment | **Modified** | `helm/backend/unifai-backend/templates/deployment.yaml` |
| Adapter (Helm) | RAG server deployment | **Modified** | `helm/rag/unifai-rag-server/templates/deployment.yaml` |
| Adapter (Helm) | RAG celery deployment | **Modified** | `helm/rag/unifai-rag-celery/templates/deployment.yaml` |
| Adapter (Helm) | Redis StatefulSet | **Modified** | `helm/shared-resources/redis/templates/statefulset.yaml` |
| Adapter (Helm) | Vault annotations helper | **New** | `helm/shared-resources/vault-annotations/_helpers.tpl` |
| Adapter (Helm) | Per-service values files | **Modified** | `helm/values/identity-values.yaml`, `helm/values/multiagent-resource-values.yaml`, `helm/values/backend-resource-values.yaml`, `helm/values/rag-resource-values.yaml`, `helm/values/shared-resource-values.yaml` |
| Adapter (Scripts) | Identity presync | **Modified** | `helm/scripts/identity-presync.sh` |
| Adapter (Scripts) | Multiagent presync | **Modified** | `helm/scripts/multiagent-presync.sh` |
| Adapter (Scripts) | RAG presync | **Modified** | `helm/scripts/rag-presync.sh` |
| Adapter (Scripts) | Redis presync | **Modified** | `helm/scripts/redis-presync.sh` |
| Adapter (Scripts) | Backend presync | **Modified** | `helm/scripts/backend-presync.sh` |
| Adapter (CI) | Jenkins deploy pipeline | **Modified** | `ci/pipeline-deploy.groovy` |
| External (Vault) | Vault KV paths & policies | **New** | (HashiCorp Vault — not in repo) |

---

### 3. Technical Design

#### 3.1 `VaultFileSource` — New Config Source

**Purpose:** Read secrets injected by the Vault Agent sidecar from the in-memory volume at `/vault/secrets/`.

**Interfaces/Ports:**

```python
class VaultFileSource(ConfigSource):
    """
    Reads Vault Agent-injected secret files from an in-memory volume.
    Falls back gracefully to empty dict when the path does not exist
    (local development, tests, non-Vault environments).
    """
    def __init__(self, base_path: str = "/vault/secrets", file_pattern: str = "*.env"):
        ...

    def load(self) -> Dict[str, Any]:
        ...
```

**Dependencies:** `pathlib.Path`, `dotenv.dotenv_values` (already a dependency via `DotEnvSource`).

**Key logic:**
- Check if `base_path` directory exists; if not, return `{}` silently
- Glob for all files matching `file_pattern` under `base_path`
- Sort files alphabetically so `shared.env` loads before `identity.env` (service-specific overrides shared)
- Parse each file using `dotenv_values` (same format as existing `.env` files)
- Merge all parsed dicts into one; return the merged result
- Log a debug message listing which files were loaded (for troubleshooting)

#### 3.2 `SharedConfig` Modification

**Purpose:** Insert `VaultFileSource` as the highest-priority file source, after environment variables.

**Interfaces/Ports:** No new interfaces — modification to the `settings_customise_sources` lambda.

**Dependencies:** `VaultFileSource` from `sources.py`.

**Key logic:**

Modified source chain:
```
(init, env, VaultFileSource().load, DotEnvSource().load, YamlSource().load, JsonSource().load, fs)
```

Vault-injected files take precedence over `.env`/yaml/json but are still overridden by explicit environment variables. This means existing `envFrom` ConfigMap values for non-secret config continue to work, while secrets come from Vault files.

#### 3.3 Vault Secret Structure (External)

**Purpose:** Organize all UnifAI secrets in Vault KV v2 under the existing `apps/automation-and-tools` AppRole.

**Dependencies:** Company Vault instance at `vault.corp.redhat.com:8200`, existing `automation-and-tools` AppRole.

**Key logic — Path layout:**

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

**Authentication:** Kubernetes Service Account (KSA) auth method, bound to namespace `tag-ai--pipeline`. Each service's existing `ServiceAccount` (from Helm charts) gets a Vault role scoped to `shared` + its own path.

**Vault policies (per service):**

```hcl
# Example: unifai-identity policy
path "apps/data/automation-and-tools/unifai/{{identity.meta.environment}}/shared" {
  capabilities = ["read"]
}
path "apps/data/automation-and-tools/unifai/{{identity.meta.environment}}/identity" {
  capabilities = ["read"]
}
```

#### 3.4 Helm Vault Annotations

**Purpose:** Provide Vault Agent Injector annotations for each deployment so the Operator injects secrets at pod startup.

**Interfaces/Ports:** Helm named template `vault.annotations`.

**Dependencies:** OpenShift Vault Operator (mutating webhook) installed on the cluster.

**Key logic — Values structure per service:**

```yaml
vault:
  enabled: true
  role: "unifai-identity"
  environment: "staging"
  paths:
    - name: "shared.env"
      path: "apps/automation-and-tools/unifai/staging/shared"
    - name: "identity.env"
      path: "apps/automation-and-tools/unifai/staging/identity"
```

**Rendered annotations:**

```yaml
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/role: "unifai-identity"
vault.hashicorp.com/agent-inject-secret-shared.env: "apps/automation-and-tools/unifai/staging/shared"
vault.hashicorp.com/agent-inject-template-shared.env: |
  {{- with secret "apps/automation-and-tools/unifai/staging/shared" -}}
  {{- range $k, $v := .Data.data }}
  {{ $k }}={{ $v }}
  {{- end }}
  {{- end }}
vault.hashicorp.com/agent-inject-secret-identity.env: "apps/automation-and-tools/unifai/staging/identity"
vault.hashicorp.com/agent-inject-template-identity.env: |
  {{- with secret "apps/automation-and-tools/unifai/staging/identity" -}}
  {{- range $k, $v := .Data.data }}
  {{ $k }}={{ $v }}
  {{- end }}
  {{- end }}
vault.hashicorp.com/agent-pre-populate-only: "true"
vault.hashicorp.com/preserve-secret-case: "true"
```

#### 3.5 Deployment Template Modifications

**Purpose:** Add Vault annotations; remove `envFrom` references to secret-bearing ConfigMaps/Secrets.

**Key logic per service:**

| Service | Remove from `envFrom` | Keep in `envFrom` |
|---------|----------------------|-------------------|
| Identity | `configMapRef: identity-config` (contains `client_secret`, `secret_key`) | `configMapRef: {{ .Values.globalConfigMapName }}` |
| Multiagent BE | `configMapRef: multiagent-be-security` (contains encryption keys) | `configMapRef: multiagent-be-configmap`, `configMapRef: {{ .Values.globalConfigMapName }}` |
| Multiagent Worker | Same as Multiagent BE | Same as Multiagent BE |
| Backend | No secret ConfigMaps to remove | `configMapRef: {{ .Values.globalConfigMapName }}`, `configMapRef: backend-be-security` (only has `admin_allowed_users`) |
| RAG Server | `secretRef: unifai-rag-secrets` (contains Slack tokens) | `configMapRef: {{ .Values.globalConfigMapName }}` |
| RAG Celery | Same as RAG Server | Same as RAG Server |
| Redis | `configMapRef: redis-config` password entries | Non-password entries stay |

Conditional rendering when `vault.enabled` is true:

```yaml
{{- if .Values.vault.enabled }}
annotations:
  {{- include "vault.annotations" .Values.vault | nindent 8 }}
{{- end }}
```

#### 3.6 Presync Script Modifications

**Purpose:** Remove secret-bearing `--from-literal` arguments from presync hooks. Keep only non-secret configuration.

**Key logic:**

| Script | Secrets Removed | Remaining Non-Secret Config |
|--------|----------------|---------------------------|
| `helm/scripts/identity-presync.sh` | `client_secret`, `secret_key` | `admin_allowed_users`, `keycloak_base_url`, `client_id`, `keycloak_realm` (or move all to Vault) |
| `helm/scripts/multiagent-presync.sh` | `CREDENTIAL_ENCRYPTION_KEY`, `MCP_AUTH_STATE_SECRET` | `admin_allowed_users` |
| `helm/scripts/rag-presync.sh` | `default_slack_bot_token`, `default_slack_user_token` | Entire Secret removed — tokens from Vault |
| `helm/scripts/redis-presync.sh` | `REDIS_PASSWORD`, `RI_REDIS_PASSWORD` | `REDIS_PORT`, `REDIS_USERNAME`, `RI_APP_PORT`, `RI_REDIS_PORT`, `RI_REDIS_USERNAME` |
| `helm/scripts/backend-presync.sh` | None (only `admin_allowed_users` today) | `admin_allowed_users` stays |

#### 3.7 Jenkins Pipeline Modifications

**Purpose:** Replace `UnifAI-secrets` Git checkout with HashiCorp Vault Jenkins Plugin.

**Dependencies:** Jenkins version upgrade (GENIE-1526), HashiCorp Vault Jenkins Plugin.

**Key logic:**

1. Remove SCM checkout of `UnifAI-secrets` (lines 254–266 of `ci/pipeline-deploy.groovy`)
2. Remove `--env-file` arguments from `podman run` Helmfile container (line 305)
3. Remove `updateDeployerEnv()` function and related `.env` file manipulation
4. Add `withVault` credential bindings:

```groovy
withVault(
    configuration: [
        vaultUrl: 'https://vault.corp.redhat.com:8200',
        engineVersion: 2
    ],
    vaultSecrets: [
        [path: "apps/automation-and-tools/unifai/${env}/cluster",
         secretValues: [[envVar: 'token', vaultKey: 'access_token']]]
    ]
) {
    sh("oc login --token=${token} --server=${ClusterAddress}")
}
```

5. Non-secret Helm values (image tags, versions, tolerations) continue through `values/*.yaml` and Groovy logic — unchanged.

---

### 4. Data Flow

**Deployment-time flow (Jenkins → Cluster):**

```
[CURRENT]
Jenkins Pipeline
  → Checkout UnifAI-secrets repo (SSH key: jenkins_agent_deploy_key)
  → Select env-specific .env files (staging/.env_identity, etc.)
  → podman run --env-file=... helmfile:latest
  → helmfile apply triggers presync hooks
  → Presync scripts create ConfigMaps/Secrets from env vars
  → Deployments reference ConfigMaps/Secrets via envFrom

[PROPOSED]
Jenkins Pipeline
  → Vault Jenkins Plugin authenticates (AppRole)
  → Reads cluster access token from Vault
  → oc login --token=... (from Vault, not from .env file)
  → helmfile apply (no --env-file needed for secrets)
  → Vault annotations on Deployments tell the Operator what to inject
  → Presync scripts create ONLY non-secret ConfigMaps
```

**Pod startup flow (Vault Agent → Application):**

```
1. Pod created by Deployment controller
2. Vault Operator mutating webhook detects vault.hashicorp.com/agent-inject annotation
3. Webhook injects Vault Agent init-container into the pod spec
4. Agent authenticates to Vault using pod's ServiceAccount JWT (KSA auth)
5. Agent reads secrets from Vault KV paths:
   - apps/automation-and-tools/unifai/<env>/shared
   - apps/automation-and-tools/unifai/<env>/<service>
6. Agent renders secrets as .env-formatted files:
   - /vault/secrets/shared.env
   - /vault/secrets/<service>.env
7. Files are written to in-memory tmpfs (never touch disk/etcd)
8. Agent exits (agent-pre-populate-only: true)
9. App container starts
10. SharedConfig loads sources in order:
    init → env (from non-secret ConfigMaps via envFrom)
         → VaultFileSource(/vault/secrets/shared.env, <service>.env)
         → DotEnvSource(.env)
         → YamlSource(config.yaml)
         → JsonSource(config.json)
         → fs
11. Application gets merged config: non-secret config from ConfigMaps + secrets from Vault files
```

**Local development flow (unchanged):**

```
1. No /vault/secrets/ directory exists on developer machine
2. VaultFileSource.load() returns {} (graceful no-op)
3. SharedConfig falls through to DotEnvSource (.env file), YamlSource, JsonSource
4. Developer uses local .env file as before — zero friction
```

---

### 5. Edge Cases & Risks

| Edge Case / Risk | Handling |
|-----------------|----------|
| **Vault unavailable at pod startup** | Vault Agent init-container blocks pod startup if it can't authenticate. Pod enters `Init:CrashLoopBackOff`. This is desired behavior (fail loud, not silent). Existing pod health monitoring catches this. |
| **Secret rotation** | With `agent-pre-populate-only: true`, pods get secrets only at startup. For dynamic rotation, a future iteration can switch to sidecar mode (`agent-pre-populate-only: false`). Acceptable for Phase 1 since current secrets are also static per pod lifetime. |
| **Backward compatibility during rollout** | Deploy in phases: (A) add `VaultFileSource` to `SharedConfig` — no-op when `/vault/secrets/` absent; (B) add Vault annotations to one service (identity), validate; (C) roll out to remaining services; (D) remove old presync secrets; (E) rotate credentials. At no point does a pod break — it either gets secrets from Vault or from the old ConfigMap. |
| **UI Dockerfile copies TLS certificates** | `ui/deployment/Dockerfile` copies certs from `UnifAI-secrets/certificates/`. Certificates are out of scope for Vault migration — they stay as build-time artifacts until a separate cert-manager story. This means the `UnifAI-secrets` repo cannot be fully deleted until certificates are also migrated. |
| **Multiple Vault paths per pod** | The Vault Agent supports multiple `agent-inject-secret-*` annotations. Each service gets `shared.env` + `{service}.env`. Well-tested pattern in production Vault deployments. |
| **Key naming conflicts** | `VaultFileSource` loads files in alphabetical order: `identity.env` after `shared.env`. Service-specific keys override shared keys (last-writer-wins dict merge). This mirrors the current `envFrom` ordering where service-specific ConfigMaps come after `shared-config`. |
| **ServiceAccount proliferation** | Reuse existing ServiceAccounts already defined in Helm charts (e.g., via `identity.serviceAccountName`). Bind them to Vault roles rather than creating new ones. |
| **Vault token TTL** | KSA auth uses auto-renewed Kubernetes JWTs, not AppRole. The 20-min AppRole TTL noted in `vault.txt` only affects manual/Jenkins CLI usage, not pod injection. |
| **Git history exposure** | Even after removing secrets from `UnifAI-secrets`, Git history retains them permanently. All currently exposed credentials (Keycloak client secrets, encryption keys, Redis password `Mc10vin!!`, RabbitMQ password `genie123`, Slack tokens, OpenShift SA tokens) must be rotated to new values in Vault. |
| **MongoDB authentication** | The codebase uses MongoDB without authentication (`mongodb://host:port/`). Adding Mongo auth is out of scope for this ticket. |
| **Jenkins upgrade dependency (GENIE-1526)** | The Vault Jenkins Plugin requires a Jenkins version upgrade. Pod-side Vault injection is independent of Jenkins and can proceed first. Decouple if Jenkins upgrade is delayed. |

**Phased Rollout Plan:**

| Rollout Phase | Scope | Rollback Strategy |
|:-------------|:------|:-----------------|
| **A** | Add `VaultFileSource` to `SharedConfig` (no-op). Deploy to all services. | Remove source from chain. |
| **B** | Enable Vault annotations on Identity (staging only). Validate SSO login. | Remove annotations; old ConfigMap still exists. |
| **C** | Enable Vault for all remaining services (staging). | Remove annotations per-service. |
| **D** | Enable Vault on production. | Same as staging rollback. |
| **E** | Remove old presync secret literals, delete secret-bearing ConfigMaps/Secrets. | Re-run presync scripts from backed-up env files. |
| **F** | Rotate all credentials to new values in Vault. Archive `UnifAI-secrets` repo. | N/A — point of no return after rotation. |

---

### 6. Open Questions

1. **Vault policy creation** — Who creates the KSA auth roles and policies in Vault? Does Harel Hadad's team provision these, or does the UnifAI team have write access to `auth/kubernetes/` and `sys/policy/`? This determines whether we need to submit a request or can self-serve.

2. **OpenShift Vault Operator availability** — The ticket specifies the "OpenShift Vault Operator." Need to confirm whether the Red Hat-managed clusters (`stc-ai-e1-pp`, `stc-ai-e1-prod`) already have the `vault.hashicorp.com` mutating webhook installed, or if a separate OperatorHub subscription is required. This affects timeline and may require a cluster-admin request.

3. **Jenkins upgrade timeline (GENIE-1526)** — The Vault Jenkins Plugin integration is blocked on the Jenkins version upgrade. What is the current ETA? Can we decouple pod-side Vault injection (which doesn't need Jenkins changes) from CI-side Vault usage?

4. **MongoDB credentials** — The current codebase uses MongoDB without authentication. Is there a plan to add MongoDB auth credentials to Vault as part of this ticket, or is that a separate story?

5. **Environment-specific Vault paths** — The design assumes `staging` and `production` path segments. Should the Helm values use a dedicated `vault.environment` value, or derive it from `{{ .Release.Namespace }}` / deploy parameters? The namespace `tag-ai--pipeline` is shared between environments.

6. **Secret value migration** — Several secrets in `UnifAI-secrets/.env` use weak passwords (e.g., `rmq_password=genie123`, `redis_password=Mc10vin!!`, `umami_password=umami`). Should these be rotated to strong random values during the Vault migration? This may require a coordinated maintenance window.

7. **Certificates** — The UI Dockerfile bakes TLS certs from `UnifAI-secrets/certificates/`. Should certificate migration (to Vault PKI engine or cert-manager) be tracked as a follow-up story?

8. **Non-secret config in `identity-config` ConfigMap** — Should non-secret values like `keycloak_base_url`, `client_id`, `keycloak_realm` also move to Vault for simplicity (single source of truth), or stay in ConfigMaps to keep Vault scope minimal? Both approaches are valid.
