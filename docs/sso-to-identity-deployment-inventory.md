# SSO → identity: deployment inventory

Generated as a working checklist for renaming deployment / CI / UI / Helm surfaces from `sso` / `sso-backend` to **identity** (or your chosen names). The application code is already under `shared-resources/identity/`; this list is everything else that still used **sso** naming in the repo (and related secrets).

**Note:** `ci/pipeline-deploy.groovy` `deployModules(module)` runs `helmfile -f ${module}.yaml.gotmpl apply`, so the Helmfile basename, `case '...':` branches, and `MODULES_TO_DEPLOY` string values must match.

---

## 1. Folders to visit (suggested order)

1. `helm/shared-resources/sso/` — Helm chart (Chart name, `sso.*` helpers, values, `SSOConfigMapName`, images).
2. `helm/values/` — `sso-values.yaml`, `global-config.yaml` (`SSO_BACKEND_HOST`, `SSO_NGINX_HOST` comment).
3. `helm/` (root) — `sso.yaml.gotmpl`, `scripts/sso-presync.sh`, `scripts/redis-presync.sh` (misleading echo), `helm/ARCHITECTURE.md`, `helm/README.md`.
4. `ci/` — `pipeline-build.groovy`, `pipeline-deploy.groovy`, `ci/ARCHITECTURE.md`, `ci/README.md`.
5. `.github/workflows/` — `security-container-vulerability-scanning.yaml`, `security-pip-auditing.yaml`.
6. `ui/deployment/` — `nginx.conf.template`, `archive/nginx.conf.template.http`, optional `ui/deployment/README.md`.
7. `ui/` — `vite.config.ts` (`SSO_HOST`), `.env`, `ui.env`.
8. Repository root — `README.md`.
9. **Related: `UnifAI-secrets` repo (not in this tree)** — `production/.env_sso`, `staging/.env_sso`, Keycloak / client JSON under `production/` and `staging/` (URLs with `unifai-sso-backend-*` etc.).

**No matches** in `backend/`, `multiagent/`, `shared-resources/identity` (beyond comments), `helm/ui`, or `shared-resources.yaml.gotmpl` for the patterns that were searched.

---

## 2. File-by-file: `helm/shared-resources/sso/` - Done

| File | What to align |
|------|----------------|
| `Chart.yaml` | `name: sso` | - done
| `values.yaml` | “sso” in header comment; `SSOConfigMapName: sso-config`; `repository: .../unifai/sso/sso-backend`; `backend.service.name: sso-backend`; TODOs `sso-nginx` | - done
| `templates/_helpers.tpl` | All `define` blocks: `sso.name`, `sso.fullname`, `sso.chart`, `sso.labels`, `sso.selectorLabels`, `sso.serviceAccountName` | - done
| `templates/deployment.yaml` | `include "sso.…"`, `SSOConfigMapName` | - Done
| `templates/service.yaml` | `include "sso.…"` | - Done
| `templates/ingress.yaml` | `include "sso.…"` | - Done
| `templates/hpa.yaml` | `include "sso.…"` | - Done
| `templates/route.yaml` | `include "sso.…"`, name suffix `...-backend` | - Done

If the chart directory is renamed (e.g. to `identity`), update every path that reference `helm/shared-resources/sso/`.

---

## 3. `helm/values/` - Done

| File | Notes |
|------|--------|
| `sso-values.yaml` | Filename; commented `ssobackend` / `ssonginx`; `name: sso-backend`; `sso-nginx` TODOs | - Done
| `global-config.yaml` | `SSO_BACKEND_HOST` (URL `unifai-sso-backend-...`); commented `SSO_NGINX_HOST` / `unifai-sso-nginx-...` — if env var names change, keep UI + nginx + ConfigMap in sync | - Done

---

## 4. `helm/` root and `helm/scripts/`

| File | Notes |
|------|--------|
| `sso.yaml.gotmpl` | `./values/sso-values.yaml`; release `name: unifai-sso`; `chart: ./shared-resources/sso`; `scripts/sso-presync.sh` | - Done
| `scripts/sso-presync.sh` | Filename; echo; `create_or_update_configmap sso-config` (align with `SSOConfigMapName` / new name) | - Done
| `scripts/redis-presync.sh` | Echo line incorrectly says “sso-presync” | - Done
| `helm/ARCHITECTURE.md` | `sso/`, `sso-values`, `sso.yaml.gotmpl`, `SSO_BACKEND_HOST`, `helmfile -f sso.yaml` | - Done
| `helm/README.md` | Same patterns | - Done

---

## 5. `ci/`

| File | What references sso/SSO |
|------|-------------------------|
| `pipeline-build.groovy` | `build_sso_image`, `stage('build_sso_image')`, description (sso-backend / sso-nginx), `modules << 'sso'` (body may already use `shared-resources/identity` for the image) | - done
| `pipeline-deploy.groovy` | `SSO_VERSION`, `MODULES_TO_DEPLOY` help (`…,sso`); `values.env.SSO_BACKEND_HOST` URL; `sso_env_file`, `UnifAI-secrets/.../env_sso` paths; `charts` list `"sso"`; `case 'sso':` — paths `helm/shared-resources/sso/`, `helm/values/sso-values.yaml`, `deployModules('sso')` |
| `ci/ARCHITECTURE.md` | `ssobackend`, `build_sso_image`, `SSO_VERSION`, `sso.yaml.gotmpl`, `shared-resources/sso-backend/`, `SSO_BACKEND_HOST`, `ssoUrl` | - Done
| `ci/README.md` | `build_sso_image`, examples with `rag,ui,sso` | - Done

---

## 6. `.github/workflows/` - DONE 

| File | Notes |
|------|--------|
| `security-container-vulerability-scanning.yaml` | `component: ssobackend`, `shared-resources/sso-backend/Dockerfile` |  - done
| `security-pip-auditing.yaml` | `scan_sso` job, step names “(sso)”, `shared-resources/sso-backend/requirements.txt`, `needs: [..., scan_sso]` and commented `needs` | - done

Point these at `shared-resources/identity/` and rename jobs/ids if you drop the “sso” label.

---

## 7. `ui/deployment/` - DONE

| File | Notes |
|------|--------|
| `nginx.conf.template` | `${SSO_BACKEND_HOST}/api/...` | - done
| `archive/nginx.conf.template.http` | Same | - done
| `entrypoint.sh` | Only `DOLLAR` / template vars, no sso in name | - nothing there
| `README.md` | If it documents `SSO_BACKEND_HOST`, update |  - nothing there

---

## 8. `ui/` (dev) - DONE

| File | Notes |
|------|--------|
| `vite.config.ts` | `process.env.SSO_HOST` (dev proxy) |
| `.env` / `ui.env` | `SSO_HOST=...` |

---

## 9. Repository root - DONE

| File | Notes |
|------|--------|
| `README.md` | Link to `shared-resources/sso-backend/README.md` (stale path) |

---

## 10. App modules and external systems

- **In-repo app code:** No other Python/TS “sso-backend” service name strings were found; routing is via public URL env (`SSO_BACKEND_HOST`) and K8s route names from the Helm chart.
- **UnifAI-secrets:** Paths `.env_sso` used by pipeline; consider `.env_identity` and pipeline variable renames. Keycloak/client JSON: redirect URIs and web origins for `unifai-sso-backend-*` / `unifai-sso-nginx-*` must match the new public routes after you change release/chart and route hostnames.
- **Container registry / image name:** `values` use `.../unifai/sso/sso-backend` — update if the image path changes with the rename.

---

## Quick grep helpers (for later)

```bash
# From UnifAI repo root
rg -l 'sso-backend|unifai-sso|shared-resources/sso|SSO_|build_sso|/sso' helm ci .github ui vite.config.ts .env ui.env README.md
```

Re-run as needed after renames; adjust patterns if you only rename some layers.
