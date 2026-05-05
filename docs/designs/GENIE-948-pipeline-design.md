# GENIE-948: Migrate UnifAI Secrets to HashiCorp Vault — Technical Design

**Ticket:** [GENIE-948](https://redhat.atlassian.net/browse/GENIE-948)
**Lead Developer:** Saar Fireshtein | **Date:** 2026-05-05 | **Priority:** High

> **Option Guidance:** This design presents two integration options. **Option A (Jenkins-Managed Injection) is the recommended primary path** — it has no cluster-side operator dependency and builds on the already-proven `withVault` Jenkins plugin (`ci/test-vault.groovy`). **Option B (OpenShift Vault Operator)** is the higher-security target architecture but is contingent on operator availability on the target clusters. Both options share the same Vault KV structure, `VaultFileSource` application adapter, and credential rotation process.

---

## 1. Overview

**Problem statement:** UnifAI stores all sensitive credentials (Keycloak client secrets, encryption keys, Redis/RabbitMQ passwords, Slack tokens, OpenShift access tokens) in plaintext inside a private Git repository (`UnifAI-secrets`) and injects them via Kubernetes ConfigMaps — not Kubernetes Secrets — through presync shell scripts. This leaves secrets exposed in Git history, in etcd unencrypted, and visible to anyone with cluster ConfigMap read access.

**Proposed solution:** Migrate all UnifAI secrets to the company's existing HashiCorp Vault instance (`vault.corp.redhat.com:8200`). Two integration options are provided:

- **Option A — Jenkins-Managed Injection (RECOMMENDED PRIMARY):** Jenkins fetches all secrets from Vault at deploy time using the HashiCorp Vault Jenkins Plugin, writes them to temporary `.env` files, passes them to the helmfile container, and presync scripts create Kubernetes Secrets. Pods consume secrets via volume mounts at `/vault/secrets/`. No cluster-side operator required.
- **Option B — OpenShift Vault Operator (Agent Injector):** The Vault Agent Injector operator runs on the cluster and injects secrets directly into pods at startup via init-container and in-memory `tmpfs`. Jenkins only fetches the cluster access token from Vault. Requires the Vault Operator to be installed on the cluster.

Both options share: the same Vault KV path layout, the same `VaultFileSource` application config adapter, and the same credential rotation/cleanup process.

**Success metrics / acceptance criteria:**

- All secrets currently in `UnifAI-secrets/.env*` files are stored in Vault under `apps/automation-and-tools/unifai/{env}/{service}`
- Pods receive secrets via the chosen option (A: K8s Secrets from Jenkins, or B: Vault Agent init-container)
- Application code reads secrets from injected files via the new `VaultFileSource` in `SharedConfig`
- Presync scripts no longer create ConfigMaps containing plaintext credentials (non-secret ConfigMaps are preserved)
- Jenkins pipeline uses the Vault plugin instead of `UnifAI-secrets` Git checkout
- Old secrets in GitHub, ConfigMaps, and plaintext `.env` files are removed and rotated
- Existing functionality is unchanged — all services start and operate normally
- Vault audit logs capture every secret access

---

## 2. Affected Components

### 2.1 Shared Components (Both Options)

| Layer | Component | Action | File Path |
|-------|-----------|--------|-----------|
| Adapter (Config) | `VaultFileSource` | **New** | `global_utils/src/global_utils/config/sources.py` |
| Adapter (Config) | `SharedConfig` | **Modified** | `global_utils/src/global_utils/config/config.py` |
| Adapter (CI) | Jenkins deploy pipeline | **Modified** | `ci/pipeline-deploy.groovy` |
| Adapter (Scripts) | Identity presync | **Modified** | `helm/scripts/identity-presync.sh` |
| Adapter (Scripts) | Multiagent presync | **Modified** | `helm/scripts/multiagent-presync.sh` |
| Adapter (Scripts) | RAG presync | **Modified** | `helm/scripts/rag-presync.sh` |
| Adapter (Scripts) | Redis presync | **Modified** | `helm/scripts/redis-presync.sh` |
| Adapter (Scripts) | Backend presync | **Unchanged** | `helm/scripts/backend-presync.sh` |
| External | Vault KV paths & policies | **New** | HashiCorp Vault (external) |

### 2.2 Option A Only — Jenkins-Managed Injection

| Layer | Component | Action | File Path |
|-------|-----------|--------|-----------|
| Adapter (Scripts) | Shared Vault presync | **New** | `helm/scripts/shared-vault-presync.sh` |
| Adapter (Helm) | Identity deployment | **Modified** — add Secret volume mount | `helm/shared-resources/identity/templates/deployment.yaml` |
| Adapter (Helm) | Multiagent BE deployment | **Modified** | `helm/multiagent/be/templates/be-deployment.yaml` |
| Adapter (Helm) | Multiagent Temporal Worker | **Modified** | `helm/multiagent/temporal-worker/templates/be-deployment.yaml` |
| Adapter (Helm) | Backend deployment | **Modified** | `helm/backend/unifai-backend/templates/deployment.yaml` |
| Adapter (Helm) | RAG server deployment | **Modified** | `helm/rag/unifai-rag-server/templates/deployment.yaml` |
| Adapter (Helm) | RAG celery deployment | **Modified** | `helm/rag/unifai-rag-celery/templates/deployment.yaml` |
| Adapter (Helm) | Redis StatefulSet | **Modified** | `helm/shared-resources/redis/templates/statefulset.yaml` |

### 2.3 Option B Only — OpenShift Vault Operator

| Layer | Component | Action | File Path |
|-------|-----------|--------|-----------|
| Adapter (Helm) | Vault annotations helper | **New** | `helm/shared-resources/vault-annotations/_helpers.tpl` |
| Adapter (Helm) | Identity deployment | **Modified** — add Vault annotations | `helm/shared-resources/identity/templates/deployment.yaml` |
| Adapter (Helm) | Multiagent BE deployment | **Modified** | `helm/multiagent/be/templates/be-deployment.yaml` |
| Adapter (Helm) | Multiagent Temporal Worker | **Modified** | `helm/multiagent/temporal-worker/templates/be-deployment.yaml` |
| Adapter (Helm) | Backend deployment | **Modified** | `helm/backend/unifai-backend/templates/deployment.yaml` |
| Adapter (Helm) | RAG server deployment | **Modified** | `helm/rag/unifai-rag-server/templates/deployment.yaml` |
| Adapter (Helm) | RAG celery deployment | **Modified** | `helm/rag/unifai-rag-celery/templates/deployment.yaml` |
| Adapter (Helm) | Redis StatefulSet | **Modified** | `helm/shared-resources/redis/templates/statefulset.yaml` |
| Adapter (Helm) | Per-service values files | **Modified** | `helm/values/{identity,multiagent-resource,backend-resource,rag-resource,shared-resource}-values.yaml` |

---

## 3. Technical Design

### 3.1 `VaultFileSource` — New Config Source (Both Options)

**Purpose:** Read secrets from `.env`-formatted files at a configurable directory. In Option A these files are mounted from K8s Secrets. In Option B they are injected by the Vault Agent init-container. Either way, the files land at `/vault/secrets/`.

**Interfaces/Ports:**

```python
class VaultFileSource(ConfigSource):
    """
    Reads secret files from a configurable directory (Vault Agent tmpfs or
    K8s Secret volume mount). Falls back gracefully to empty dict when the
    path does not exist (local dev, tests, non-Vault environments).
    """
    def __init__(self, base_path: str = "/vault/secrets", file_pattern: str = "*.env"):
        ...

    def load(self) -> Dict[str, Any]:
        ...
```

**Dependencies:** `pathlib.Path`, `dotenv.dotenv_values` (already a dependency via `DotEnvSource`).

**Key logic:**
- Check if `base_path` directory exists; if not, return `{}` silently (graceful no-op for local dev)
- Glob for all files matching `file_pattern` under `base_path`
- Sort files alphabetically so `shared.env` loads before service-specific files (e.g., `identity.env`) — service keys override shared (last-writer-wins)
- Parse each file using `dotenv_values` (same KEY=VALUE format as existing `.env` files)
- Merge all parsed dicts into one; return the merged result
- Log a debug message listing which files were loaded

### 3.2 `SharedConfig` Modification (Both Options)

**Purpose:** Insert `VaultFileSource` into the pydantic-settings source chain, after environment variables.

**Modified source chain in `global_utils/src/global_utils/config/config.py`:**

```
(init, env, VaultFileSource().load, DotEnvSource().load, YamlSource().load, JsonSource().load, fs)
```

Vault-injected files take precedence over `.env`/yaml/json but are still overridden by explicit environment variables (set via `envFrom` from non-secret ConfigMaps). This means existing `envFrom` ConfigMap values for non-secret config continue to work, while secrets come from Vault files.

### 3.3 Vault Secret Structure (Both Options)

**Purpose:** Organize all UnifAI secrets in Vault KV v2 under the existing `apps/automation-and-tools` AppRole.

**Path layout:**

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

**Authentication:**
- **Option A (Jenkins):** AppRole auth (`automation-and-tools`), 20-min non-renewable tokens. Already configured as global Jenkins Vault plugin credentials (confirmed via `ci/test-vault.groovy` which uses empty `vaultUrl`/`vaultCredentialId` to pick up global config).
- **Option B (Pods):** Kubernetes Service Account (KSA) auth method bound to namespace `tag-ai--pipeline`. Each service's existing `ServiceAccount` gets a Vault role scoped to `shared` + its own service path.

---

## OPTION A: Jenkins-Managed Injection (RECOMMENDED PRIMARY)

### A.1 Concept

Jenkins becomes the single point of Vault contact for secrets. At deploy time, the pipeline fetches ALL service secrets from Vault using the `withVault` plugin, writes them to temporary `.env` files on the Jenkins agent, and passes those files to the helmfile `podman` container via `--env-file` (the same mechanism used today for `UnifAI-secrets` `.env` files). Presync scripts then create proper Kubernetes `Secret` resources (replacing current plaintext ConfigMaps for secret data). Pods mount these K8s Secrets as volumes at `/vault/secrets/` so `VaultFileSource` can read them.

**Key advantages:**
- No cluster-side operator dependency — works on any Kubernetes cluster
- Builds on proven Jenkins `withVault` integration (already tested via `ci/test-vault.groovy`)
- Simpler debugging — secrets are standard K8s Secrets visible via `oc get secret`
- Minimal Jenkins pipeline change — replaces `UnifAI-secrets` checkout with `withVault` block, same `--env-file` pattern

**Key disadvantages:**
- Secrets pass through Jenkins as environment variables (in-memory, but broader blast radius)
- Secrets stored as K8s Secrets in etcd (encrypted at rest if etcd encryption enabled, but accessible to anyone with Secret read RBAC)
- No Vault audit trail for pod-level access (only Jenkins access is logged)
- Secret rotation requires a re-deploy

### A.2 Secret Passing Mechanism — Jenkins to Helmfile Container

The current pipeline passes secrets from `UnifAI-secrets` to the helmfile container via `--env-file` args on `podman run` (line 305 of `ci/pipeline-deploy.groovy`). Option A replaces the source of those `.env` files but keeps the same delivery mechanism:

```groovy
def vaultEnv = (params.deploy_location == 'PRODUCTION') ? 'production' : 'staging'
def vaultBasePath = "apps/automation-and-tools/unifai/${vaultEnv}"

withVault(
    configuration: [vaultUrl: '', vaultCredentialId: ''],
    vaultSecrets: [
        [path: "${vaultBasePath}/cluster",
         secretValues: [[envVar: 'VAULT_access_token', vaultKey: 'access_token']]],
        [path: "${vaultBasePath}/shared",
         secretValues: [
             [envVar: 'VAULT_redis_password', vaultKey: 'redis_password'],
             [envVar: 'VAULT_rmq_username', vaultKey: 'rmq_username'],
             [envVar: 'VAULT_rmq_password', vaultKey: 'rmq_password'],
             [envVar: 'VAULT_HF_TOKEN', vaultKey: 'HF_TOKEN'],
             [envVar: 'VAULT_secret_key', vaultKey: 'secret_key'],
             [envVar: 'VAULT_umami_app_secret', vaultKey: 'umami_app_secret'],
             [envVar: 'VAULT_umami_password', vaultKey: 'umami_password'],
         ]],
        [path: "${vaultBasePath}/identity",
         secretValues: [
             [envVar: 'VAULT_client_secret', vaultKey: 'client_secret'],
         ]],
        [path: "${vaultBasePath}/multiagent",
         secretValues: [
             [envVar: 'VAULT_CREDENTIAL_ENCRYPTION_KEY', vaultKey: 'CREDENTIAL_ENCRYPTION_KEY'],
             [envVar: 'VAULT_MCP_AUTH_STATE_SECRET', vaultKey: 'MCP_AUTH_STATE_SECRET'],
         ]],
        [path: "${vaultBasePath}/rag",
         secretValues: [
             [envVar: 'VAULT_default_slack_bot_token', vaultKey: 'default_slack_bot_token'],
             [envVar: 'VAULT_default_slack_user_token', vaultKey: 'default_slack_user_token'],
         ]],
        [path: "${vaultBasePath}/redis",
         secretValues: [
             [envVar: 'VAULT_redis_password_redis', vaultKey: 'redis_password'],
         ]],
    ]
) {
    // Step 1: Login to cluster using Vault-sourced token
    sh("oc login --token=${VAULT_access_token} --server=${ClusterAddress}")
    sh("oc project ${NameSpace}")

    // Step 2: Write secrets to temp .env files ON THE JENKINS AGENT
    // These replace the UnifAI-secrets .env files
    writeFile file: './vault-shared.env', text: [
        "redis_password=${VAULT_redis_password}",
        "rmq_username=${VAULT_rmq_username}",
        "rmq_password=${VAULT_rmq_password}",
        "HF_TOKEN=${VAULT_HF_TOKEN}",
        "secret_key=${VAULT_secret_key}",
        "umami_app_secret=${VAULT_umami_app_secret}",
        "umami_password=${VAULT_umami_password}",
    ].join('\n')

    writeFile file: './vault-identity.env', text: [
        "client_secret=${VAULT_client_secret}",
    ].join('\n')

    writeFile file: './vault-multiagent.env', text: [
        "CREDENTIAL_ENCRYPTION_KEY=${VAULT_CREDENTIAL_ENCRYPTION_KEY}",
        "MCP_AUTH_STATE_SECRET=${VAULT_MCP_AUTH_STATE_SECRET}",
    ].join('\n')

    writeFile file: './vault-rag.env', text: [
        "default_slack_bot_token=${VAULT_default_slack_bot_token}",
        "default_slack_user_token=${VAULT_default_slack_user_token}",
    ].join('\n')

    writeFile file: './vault-redis.env', text: [
        "redis_password=${VAULT_redis_password_redis}",
    ].join('\n')

    // Step 3: Pass .env files to helmfile container via --env-file (SAME MECHANISM AS TODAY)
    sh("""podman run --replace -dt \
        --env-file=./vault-shared.env \
        --env-file=./vault-identity.env \
        --env-file=./vault-multiagent.env \
        --env-file=./vault-rag.env \
        --env-file=./vault-redis.env \
        --workdir /helm/charts \
        -v .:/helm/charts:Z \
        -v ~/.kube/:/helm/.kube:Z \
        --name helmfile ghcr.io/helmfile/helmfile:latest bash""")

    // Step 4: Deploy modules (unchanged)
    // ... deployModules() calls as before ...

    // Step 5: Clean up temp files
    sh("rm -f ./vault-*.env")
}
```

**What is removed from the pipeline:**
- `UnifAI-secrets` SCM checkout (lines 254–266)
- `updateDeployerEnv()` function (lines 122–140)
- `updateEnvFile()` function (lines 143–153)
- All `--env-file=./UnifAI-secrets/...` references

**What is unchanged:**
- `buildParams.CredMainRepoProject` / `CredCredentialsId` definitions (can be removed or kept for reference)
- `updateChartVersions()`, `updateValuesYaml()`, `updateGlobalConfigYaml()` — these handle non-secret config
- Module deployment logic (`deployModules()`)

### A.3 Presync Script Changes (Option A)

**Strategy:** Presync scripts are split into two responsibilities:
1. **Non-secret ConfigMaps** — continue to be created as today (no change for these keys)
2. **Secret data** — removed from ConfigMaps and moved to new K8s `Secret` resources containing `.env`-formatted files

Each service gets a K8s Secret where the data key is a `.env`-formatted file. This Secret is volume-mounted at `/vault/secrets/<service>.env` in the deployment.

**Pattern (e.g., `identity-presync.sh`):**

```bash
#!/bin/bash
source "$(dirname "$0")/postsync-lib.sh"

# Non-secret config stays in ConfigMap (UNCHANGED)
create_or_update_configmap identity-config \
  --from-literal=admin_allowed_users="$admin_allowed_users" \
  --from-literal=keycloak_base_url="$keycloak_base_url" \
  --from-literal=client_id="$client_id" \
  --from-literal=keycloak_realm="$keycloak_realm"
  # REMOVED: --from-literal=client_secret="$client_secret"
  # REMOVED: --from-literal=secret_key="$secret_key"

# Secret data → K8s Secret with .env-formatted file content
kubectl create secret generic identity-vault-files \
    --from-literal=identity.env="$(printf '%s\n' \
        "client_secret=${client_secret}" \
        "secret_key=${secret_key}" \
    )" \
    --dry-run=client -o yaml | kubectl apply -f -
```

**Complete presync change summary:**

| Script | Secrets Removed from ConfigMap | K8s Secret Created | Non-Secret ConfigMap Preserved |
|--------|-------------------------------|-------------------|-------------------------------|
| `identity-presync.sh` | `client_secret`, `secret_key` | `identity-vault-files` (contains `identity.env`) | `identity-config` with `admin_allowed_users`, `keycloak_base_url`, `client_id`, `keycloak_realm` |
| `multiagent-presync.sh` | `CREDENTIAL_ENCRYPTION_KEY`, `MCP_AUTH_STATE_SECRET` | `multiagent-vault-files` (contains `multiagent.env`) | `multiagent-be-security` with `admin_allowed_users` |
| `rag-presync.sh` | `default_slack_bot_token`, `default_slack_user_token` | `rag-vault-files` (contains `rag.env`) | Old `unifai-rag-secrets` Secret is deleted entirely |
| `redis-presync.sh` | `REDIS_PASSWORD`, `RI_REDIS_PASSWORD` | `redis-vault-files` (contains `redis.env`) | `redis-config` with `REDIS_PORT`, `REDIS_USERNAME`, `RI_APP_PORT`, `RI_REDIS_PORT`, `RI_REDIS_USERNAME` |
| `backend-presync.sh` | None | None | `backend-be-security` with `admin_allowed_users` — **UNCHANGED** |
| `shared-vault-presync.sh` (**NEW**) | N/A | `shared-vault-files` (contains `shared.env`) | N/A |

### A.4 Helm Deployment Changes (Option A)

Each deployment template gets a projected volume mount combining the shared K8s Secret and the service-specific K8s Secret at `/vault/secrets/`:

```yaml
spec:
  containers:
    - name: {{ .Chart.Name }}
      volumeMounts:
        {{- if .Values.vaultSecretName }}
        - name: vault-secrets
          mountPath: /vault/secrets
          readOnly: true
        {{- end }}
      envFrom:
        # Non-secret ConfigMaps STAY (unchanged)
        - configMapRef:
            name: {{ .Values.globalConfigMapName }}
        - configMapRef:
            name: {{ .Values.IdentityConfigMapName }}  # still has non-secret keys
        # REMOVED: any configMapRef/secretRef that contained secrets
  volumes:
    {{- if .Values.vaultSecretName }}
    - name: vault-secrets
      projected:
        sources:
          - secret:
              name: shared-vault-files
          - secret:
              name: {{ .Values.vaultSecretName }}
    {{- end }}
```

**Per-service envFrom changes:**

| Service | Remove from `envFrom` | Keep in `envFrom` | New `vaultSecretName` value |
|---------|----------------------|-------------------|-----------------------------|
| Identity | Nothing removed — `{{ .Values.IdentityConfigMapName }}` ConfigMap stays (only non-secret keys remain after presync change) | `{{ .Values.globalConfigMapName }}`, `{{ .Values.IdentityConfigMapName }}` | `identity-vault-files` |
| Multiagent BE | Nothing removed — `multiagent-be-security` ConfigMap stays (only `admin_allowed_users` remains) | `multiagent-be-configmap`, `multiagent-be-security`, `{{ .Values.globalConfigMapName }}` | `multiagent-vault-files` |
| Multiagent Worker | Same as Multiagent BE | Same as Multiagent BE | `multiagent-vault-files` |
| Backend | No changes | `{{ .Values.globalConfigMapName }}`, `backend-be-security` | `shared-vault-files` (shared only, no service secrets) |
| RAG Server | Remove `secretRef: unifai-rag-secrets` | `{{ .Values.globalConfigMapName }}` | `rag-vault-files` |
| RAG Celery | Same as RAG Server | Same as RAG Server | `rag-vault-files` |
| Redis | Nothing removed — `redis-config` stays (only non-password keys remain) | `{{ .Values.redisConfigMapName }}` (conditional) | `redis-vault-files` |

### A.5 Jenkins Build Pipeline (Option A)

The `ci/pipeline-build.groovy` currently checks out `UnifAI-secrets` for UI build-time assets (TLS certificates at `UnifAI-secrets/certificates/`). Since certificates are out of scope for this migration, the build pipeline remains **unchanged**.

---

## OPTION B: OpenShift Vault Operator (Agent Injector)

### B.1 Concept

The Vault Agent Injector operator (installed on the cluster as a mutating webhook) intercepts pod creation events. When it detects `vault.hashicorp.com/agent-inject` annotations, it injects a Vault Agent init-container that authenticates to Vault using the pod's ServiceAccount JWT, fetches secrets, and writes them as `.env`-formatted files to an in-memory `tmpfs` at `/vault/secrets/`. The app container reads these files via `VaultFileSource`.

**Key advantages:**
- Secrets never pass through Jenkins (only cluster access token does)
- Secrets exist only in-memory `tmpfs` (never on disk, never in etcd as K8s Secrets)
- Vault audit log captures every pod-level secret access
- Industry standard pattern for Vault + Kubernetes
- Future path to dynamic secret rotation (switch from init to sidecar mode)

**Key disadvantages:**
- Requires OpenShift Vault Operator to be installed on the cluster (may need cluster-admin request)
- Adds 2-5 seconds to pod startup (init-container) and ~30MB memory overhead
- Harder to debug (must exec into pod to inspect — no `oc get secret`)
- KSA auth method must be configured in Vault (requires Vault admin)

### B.2 Vault Authentication (KSA)

Kubernetes Service Account auth method bound to namespace `tag-ai--pipeline`. Each service's existing `ServiceAccount` gets a Vault role scoped to `shared` + its own path.

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

### B.3 Helm Vault Annotations

**New named template** `vault.annotations` in `helm/shared-resources/vault-annotations/_helpers.tpl`:

**Values structure per service (added to `helm/values/<service>-values.yaml`):**

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

### B.4 Deployment Template Modifications (Option B)

Conditional Vault annotations on `podAnnotations`:

```yaml
{{- if .Values.vault.enabled }}
annotations:
  {{- include "vault.annotations" .Values.vault | nindent 8 }}
{{- end }}
```

**Presync Script Strategy (Option B):** Presync scripts simply remove secret-bearing `--from-literal` arguments. Non-secret ConfigMaps are preserved. No new K8s Secrets are created — Vault Agent handles injection.

| Script | Secrets Removed | Non-Secret ConfigMap Preserved |
|--------|----------------|-------------------------------|
| `identity-presync.sh` | `client_secret`, `secret_key` | `identity-config` with `admin_allowed_users`, `keycloak_base_url`, `client_id`, `keycloak_realm` |
| `multiagent-presync.sh` | `CREDENTIAL_ENCRYPTION_KEY`, `MCP_AUTH_STATE_SECRET` | `multiagent-be-security` with `admin_allowed_users` |
| `rag-presync.sh` | `default_slack_bot_token`, `default_slack_user_token` | `unifai-rag-secrets` Secret deleted entirely — tokens from Vault |
| `redis-presync.sh` | `REDIS_PASSWORD`, `RI_REDIS_PASSWORD` | `redis-config` with `REDIS_PORT`, `REDIS_USERNAME`, `RI_APP_PORT`, `RI_REDIS_PORT`, `RI_REDIS_USERNAME` |
| `backend-presync.sh` | None | `backend-be-security` with `admin_allowed_users` — **UNCHANGED** |

**Per-service envFrom changes (Option B):**

| Service | Remove from `envFrom` | Keep in `envFrom` |
|---------|----------------------|-------------------|
| Identity | Nothing — `{{ .Values.IdentityConfigMapName }}` stays (only non-secret keys after presync change) | `{{ .Values.globalConfigMapName }}`, `{{ .Values.IdentityConfigMapName }}` |
| Multiagent BE | Nothing — `multiagent-be-security` stays (only `admin_allowed_users`) | `multiagent-be-configmap`, `multiagent-be-security`, `{{ .Values.globalConfigMapName }}` |
| Multiagent Worker | Same as Multiagent BE | Same as Multiagent BE |
| Backend | No changes | `{{ .Values.globalConfigMapName }}`, `backend-be-security` |
| RAG Server | Remove `secretRef: unifai-rag-secrets` | `{{ .Values.globalConfigMapName }}` |
| RAG Celery | Same as RAG Server | Same as RAG Server |
| Redis | Nothing — `{{ .Values.redisConfigMapName }}` stays (only non-password keys) | `{{ .Values.redisConfigMapName }}` (conditional) |

### B.5 Jenkins Pipeline Changes (Option B)

Minimal — only the cluster access token is fetched from Vault:

```groovy
// REMOVE: UnifAI-secrets checkout (lines 254-266)
// REMOVE: updateDeployerEnv(), updateEnvFile() functions
// REMOVE: --env-file args from podman run (line 305)

def vaultEnv = (params.deploy_location == 'PRODUCTION') ? 'production' : 'staging'

withVault(
    configuration: [vaultUrl: '', vaultCredentialId: ''],
    vaultSecrets: [
        [path: "apps/automation-and-tools/unifai/${vaultEnv}/cluster",
         secretValues: [[envVar: 'CLUSTER_ACCESS_TOKEN', vaultKey: 'access_token']]]
    ]
) {
    sh("oc login --token=${CLUSTER_ACCESS_TOKEN} --server=${ClusterAddress}")
    sh("oc project ${NameSpace}")

    // Launch helmfile WITHOUT --env-file (secrets handled by Vault Operator)
    sh("""podman run --replace -dt \
        --workdir /helm/charts \
        -v .:/helm/charts:Z \
        -v ~/.kube/:/helm/.kube:Z \
        --name helmfile ghcr.io/helmfile/helmfile:latest bash""")

    // Deploy modules (unchanged)
}
```

---

## 4. Data Flow

### 4.1 Current Flow (Both Options Replace This)

```
Jenkins Pipeline
  → Checkout UnifAI-secrets repo (SSH key: jenkins_agent_deploy_key)
  → Select env-specific .env files (staging/.env_identity, etc.)
  → updateDeployerEnv() returns [identity_env_file, redis_env_file, multiagent_env_file]
  → podman run --env-file=${identity_env_file} --env-file=${redis_env_file}
              --env-file=${multiagent_env_file} --env-file=./UnifAI-secrets/.env helmfile:latest
  → helmfile apply triggers presync hooks
  → Presync scripts create ConfigMaps/Secrets from env vars
  → Deployments reference ConfigMaps/Secrets via envFrom
```

### 4.2 Option A Flow — Jenkins-Managed Injection

```
Jenkins Pipeline
  → withVault: authenticates via AppRole (global Jenkins config), fetches ALL secrets
  → Writes secrets to temp .env files on Jenkins agent workspace
  → oc login --token=<cluster_token_from_vault> --server=<cluster>
  → podman run --env-file=./vault-shared.env --env-file=./vault-identity.env ... helmfile:latest
  → helmfile apply triggers presync hooks
  → Presync scripts create:
    - Non-secret ConfigMaps (same as today, minus secret literals)
    - New K8s Secrets containing .env-formatted files (e.g., identity-vault-files)
  → Deployments:
    - envFrom: non-secret ConfigMaps (unchanged)
    - volumeMount: K8s Secrets projected to /vault/secrets/
  → VaultFileSource reads /vault/secrets/*.env
  → Application gets merged config
```

### 4.3 Option B Flow — OpenShift Vault Operator

```
Jenkins Pipeline
  → withVault: fetches ONLY cluster access token
  → oc login --token=<from_vault> --server=<cluster>
  → podman run helmfile:latest (no --env-file, no secret passing)
  → helmfile apply triggers presync hooks
  → Presync scripts create ONLY non-secret ConfigMaps

Pod Startup (handled by Vault Operator):
  1. Pod created by Deployment controller
  2. Vault Operator mutating webhook detects vault.hashicorp.com/agent-inject annotation
  3. Webhook injects Vault Agent init-container into the pod spec
  4. Agent authenticates to Vault using pod's ServiceAccount JWT (KSA auth)
  5. Agent reads secrets from Vault KV paths
  6. Agent renders secrets as .env-formatted files at /vault/secrets/
  7. Files are written to in-memory tmpfs (never touch disk/etcd)
  8. Agent exits (agent-pre-populate-only: true)
  9. App container starts
  10. VaultFileSource reads /vault/secrets/*.env
  11. Application gets merged config
```

### 4.4 Local Development Flow (Both Options — Unchanged)

```
1. No /vault/secrets/ directory exists on developer machine
2. VaultFileSource.load() returns {} (graceful no-op)
3. SharedConfig falls through to DotEnvSource (.env file), YamlSource, JsonSource
4. Developer uses local .env file as before — zero friction
```

---

## 5. Edge Cases & Risks

### 5.1 Shared Risks (Both Options)

| Edge Case / Risk | Handling |
|-----------------|----------|
| **Git history exposure** | Even after removing `UnifAI-secrets`, Git history retains all secrets. All credentials must be rotated to new values in Vault during Phase G. |
| **UI Dockerfile copies TLS certificates** | `ui/deployment/Dockerfile` copies certs from `UnifAI-secrets/certificates/`. Out of scope — stay as build-time artifacts. `UnifAI-secrets` repo cannot be fully deleted until certificates are migrated (separate story). |
| **Key naming conflicts** | `VaultFileSource` loads files alphabetically: `shared.env` before service-specific. Service keys override shared (last-writer-wins). Mirrors current `envFrom` ordering. |
| **MongoDB authentication** | Codebase uses MongoDB without auth. Out of scope for this ticket. |
| **Secret value migration** | Weak passwords (e.g., `rmq_password=genie123`, `redis_password=Mc10vin!!`) should be rotated to strong random values during Phase G. Requires coordinated maintenance window. |
| **Environment-specific Vault paths** | Helm values use a `vault.environment` parameter derived from Jenkins `deploy_location`, not from the namespace (since `tag-ai--pipeline` is shared between staging and production). |
| **Backward compatibility during rollout** | Phased rollout (Section 6) ensures no pod ever lacks secrets. At each phase, either old ConfigMap or new Vault-sourced method provides them. |
| **Non-secret config stays in ConfigMaps** | ConfigMaps like `identity-config`, `multiagent-be-security`, `redis-config` continue to exist with non-secret keys only. Existing `envFrom` references are preserved. |

### 5.2 Option A Specific Risks

| Edge Case / Risk | Handling |
|-----------------|----------|
| **Jenkins as secret bottleneck** | All secrets flow through Jenkins. If Jenkins is compromised, all secrets are exposed. Mitigated: Jenkins is already a trusted component holding cluster tokens via `withCredentials`. |
| **K8s Secrets in etcd** | Secrets stored in etcd as base64-encoded K8s Secrets. Better than ConfigMaps but not as secure as in-memory tmpfs. Verify etcd encryption at rest is enabled on clusters. |
| **No pod-level audit trail** | Vault audit only logs Jenkins access, not which pod consumed which secret. Acceptable trade-off if Vault Operator is unavailable. |
| **Temp .env files on Jenkins agent** | Written inside `withVault` block, deleted after deploy. Jenkins workspace cleanup also removes them. Risk: if Jenkins agent is compromised during deploy, files are readable. Mitigated: same risk as current `UnifAI-secrets` checkout, which also writes secrets to disk. |
| **withVault single failure domain** | If one Vault path fails, the entire `withVault` block fails and no service deploys. Acceptable: partial deploys would be worse (some services with secrets, others without). |
| **Presync script timing** | K8s Secrets must exist before deployments reference them. Presync hooks already run before deployments — no timing change. |

### 5.3 Option B Specific Risks

| Edge Case / Risk | Handling |
|-----------------|----------|
| **Vault unavailable at pod startup** | Vault Agent init-container blocks pod startup. Pod enters `Init:CrashLoopBackOff`. Desired behavior (fail loud). Existing pod health monitoring catches this. |
| **OpenShift Vault Operator not installed** | Requires cluster-admin to install from OperatorHub. If unavailable, fall back to Option A. |
| **Secret rotation** | With `agent-pre-populate-only: true`, pods get secrets only at startup. Dynamic rotation requires sidecar mode (future iteration). |
| **Pod startup latency** | Vault Agent init-container adds 2-5 seconds to pod startup. ~30MB memory overhead in init-only mode. |
| **KSA auth configuration** | Requires Vault admin to set up `auth/kubernetes/` roles. Submit request to Harel Hadad's team if the UnifAI team lacks write access. |
| **ServiceAccount reuse** | Reuse existing ServiceAccounts from Helm charts. Bind them to Vault roles rather than creating new ones. |
| **Vault token TTL** | KSA auth uses auto-renewed K8s JWTs, not AppRole. The 20-min TTL in `vault.txt` only affects Jenkins CLI usage. |

### 5.4 Comparison Matrix

| Criterion | Option A (Jenkins) | Option B (Vault Operator) |
|-----------|-------------------|--------------------------|
| **Cluster dependency** | None (standard K8s) | Vault Operator mutating webhook |
| **Secret storage on cluster** | K8s Secrets in etcd | In-memory tmpfs only |
| **Vault audit coverage** | Jenkins access only | Every pod access logged |
| **Jenkins changes** | Major (fetch all secrets, write temp files) | Minimal (cluster token only) |
| **Helm changes** | Volume mounts for K8s Secrets | Vault annotations on all deployments |
| **Presync changes** | Major (create K8s Secrets) | Minor (remove secret literals) |
| **Pod startup overhead** | None | 2-5 seconds + 30MB RAM |
| **Secret rotation** | Re-deploy required | Re-deploy (init) or automatic (sidecar) |
| **Debugging ease** | `oc get secret` works | Must exec into pod |
| **Security posture** | Medium (etcd + Jenkins) | High (in-memory only + audit) |
| **Implementation complexity** | Medium | Medium-High |
| **Portability** | Any K8s cluster | Requires Vault Operator |

**Recommendation:** Start with **Option A** as the immediate implementation. Plan **Option B** as a Phase 2 upgrade once Vault Operator availability is confirmed. The `VaultFileSource` and Vault KV structure are identical — switching from A to B is an infrastructure change with no application code modifications.

---

## 6. Phased Rollout Plan

| Phase | Option A | Option B | Rollback |
|-------|----------|----------|----------|
| **A** | Add `VaultFileSource` to `SharedConfig` (no-op). Deploy to all services. | Same | Remove source from chain. |
| **B** | Jenkins `withVault` for cluster token only. Validate with `test-vault.groovy`. | Same | Revert to `withCredentials` for cluster token. |
| **C** | Jenkins fetches Identity secrets from Vault. Presync creates K8s Secret `identity-vault-files`. Identity deployment mounts Secret at `/vault/secrets/`. Validate SSO login works. | Enable Vault annotations on Identity (staging). Validate SSO login. | Option A: delete K8s Secret, restore old presync literals. Option B: remove annotations. |
| **D** | Roll out to all remaining services (staging). | Same | Per-service rollback. |
| **E** | Production rollout. | Same | Same as staging rollback. |
| **F** | Remove old secret literals from presync scripts. Delete secret-bearing ConfigMaps (`unifai-rag-secrets`, secret keys in `identity-config`, etc.). | Same | Re-run presync from backed-up env files. |
| **G** | Rotate all credentials to new strong values in Vault. Archive `UnifAI-secrets` repo. | Same | N/A — point of no return after rotation. |

---

## 7. Open Questions

1. **OpenShift Vault Operator availability** — Are clusters `stc-ai-e1-pp` and `stc-ai-e1-prod` running the `vault.hashicorp.com` mutating webhook? This determines whether Option B is viable now or requires a cluster-admin request. **Deciding factor between Option A and B.**

2. **Vault policy creation** — Who provisions KSA auth roles and policies? Does the UnifAI team have write access to `auth/kubernetes/` and `sys/policy/`? If not, submit request to Harel Hadad's team.

3. **Jenkins Vault Plugin status** — The `ci/test-vault.groovy` pipeline uses `withVault` with empty `vaultUrl`/`vaultCredentialId` (global config). Confirm: is the plugin fully functional today, or does GENIE-1526 (Jenkins upgrade) need to complete first?

4. **etcd encryption at rest** — For Option A, are the target clusters configured with etcd encryption? Affects security posture of K8s Secrets.

5. **Secret value rotation timing** — Should weak passwords be rotated during migration (Phase G) or in a separate maintenance window?

6. **Certificates follow-up** — The UI Dockerfile bakes TLS certs from `UnifAI-secrets/certificates/`. Should cert migration be tracked as a separate story?

7. **Non-secret config placement** — Design keeps non-secret values (like `keycloak_base_url`, `client_id`, `keycloak_realm`) in ConfigMaps. Should any of these also move to Vault for single-source-of-truth simplicity?
