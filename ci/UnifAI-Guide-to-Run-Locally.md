# UnifAI — Guide to Run Locally

## Project overview

UnifAI is an Agentic AI platform for knowledge retrieval across data sources. It has four components that need to run simultaneously locally on different terminals:

| # | Component | Directory | Port | Description |
|---|-----------|-----------|------|-------------|
| 1 | RAG Backend | `rag/` | 13457 | Flask API for data ingestion, chunking, embedding, and vector DB storage (Qdrant). Manages data sources and document pipelines. |
| 2 | SSO Backend | `shared-resources/sso-backend/` | 13456 | Flask API handling user authentication via Keycloak SSO. Manages sessions, CORS, and auth tokens. |
| 3 | Multi-Agent Backend | `multi-agent/` | 8002 | Agentic AI engine running via Gunicorn. Manages blueprints, workflow sessions, LangGraph plan execution, tools/providers, and LLM orchestration. |
| 4 | UI | `ui/` | 5000 | React + Vite frontend with Shadcn UI components. Provides the RAG data overview and Agentic Plan Builder interface. Proxies API calls to all three backends. |
| 5 | Backend | `backend/` |8003 | Main Flask API for configuration and general management. |
## Code changes needed for local runs

The following files need adjustments to be able to run locally with no errors:

### 1. `rag/config/app_config.py`

- `port: str` should be set to `"13457"` instead of `"13456"`.

### 2. `shared-resources/sso-backend/config/app_config.py`

- `hostname_local: str` should be `"127.0.0.1"` instead of `"0.0.0.0"`.
- `frontend_url: str` should be `"http://127.0.0.1:5000/"` instead of `"http://localhost:5000"`.

### 3. `shared-resources/sso-backend/app.py`

Change the CORS line from:

```python
CORS(app, supports_credentials=True, origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"))
```

to:

```python
CORS(app, supports_credentials=True, origins=os.environ.get("FRONTEND_URL", config.frontend_url))
```

### 4. `ui/vite.config.ts`

The `server` section should be:

```typescript
server: {
  port: 5000, // Personal preference, no issue with keeping this 5173
  proxy: {
    // Proxy for api1
    '/api1': {
      target: 'http://127.0.0.1:13457',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api1/, '/api'), // This rewrites /api1 to /api
      secure: false, // Set to true for production if target is HTTPS and has valid cert.
      // Set to false for dev if you're getting SSL errors with self-signed or invalid certs.
    },
    // Proxy for api2 (assuming this is still local or another service)
    '/api2': {
      target: 'http://127.0.0.1:8002', // Your second backend
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api2/, '/api'), // This rewrites /api2 to nothing
      // secure: false, // Only needed if this target is HTTPS and you have SSL issues
    },
    '/api3': {
      target: 'http://127.0.0.1:13456',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api3/, '/api'), // This rewrites /api3 to /api
      secure: false, // Set to true for production if target is HTTPS and has valid cert.
      // Set to false for dev if you're getting SSL errors with self-signed or invalid certs.
    },
    // You can add more proxies here if needed
  },
},
```

Then you can start the four terminals below.

## Terminal 1 — RAG Backend (`rag/`)

```bash
cd rag
python3.12 -m venv venv
. ./venv/bin/activate
pip install -e .
pip install -e ../global_utils
python3.12 -m bootstrap.flask_app
```

Runs on `http://0.0.0.0:13457`. The `global_utils` package is a shared Python library at the project root that all backends depend on — it provides config loading, Flask middleware, helpers, etc.

## Terminal 2 — SSO Backend (`shared-resources/sso-backend/`)

```bash
cd shared-resources/sso-backend
python -m venv venv
. ./venv/bin/activate
pip install -r requirements.txt
pip install -e ../../global_utils
python app.py
```

Runs on `http://127.0.0.1:13456`. Note the `global_utils` path is `../../global_utils` (two levels up) since you're inside `shared-resources/sso-backend/`.

## Terminal 3 — Multi-Agent Backend (`multi-agent/`)

```bash
cd multi-agent
python3.12 -m venv venv
. ./venv/bin/activate
pip install -r requirements.txt
pip install -e ../global_utils
gunicorn -w 4 --threads 16 -b 0.0.0.0:8002 --timeout 300 --access-logfile - --error-logfile - --chdir . run.wsgi:application
```

Runs on `http://0.0.0.0:8002`. The gunicorn command mirrors what's in `multi-agent/entrypoint.sh` (line 14) but with sensible local defaults instead of environment variables. Adjust `-w` (workers) and `--threads` as needed.

## Terminal 4 — UI (`ui/`)

```bash
cd ui
npm install
npm start
```

Runs on `http://localhost:5000`. Sometimes there are privacy issues on Mac and you have to use `http://127.0.0.1:5000` explicitly.

## Prerequisites

Make sure you have the following running locally (or accessible). They are built as containers via Podman:

- MongoDB on port 27017
- RabbitMQ on port 5672
- Qdrant (vector DB) on port 6333
- Python (Python 3.12 is used; multi-agent may work with 3.11 and RAG with 3.10)
- Node.js and npm/pnpm for the UI

Not all of these are necessary; it depends on what you want to do on UnifAI. For example, for embedding of documents or Slack channels you'll need to run Celery workers using RabbitMQ, but if you only use multi-agent you can do without. If you hit more specific problems, those can be discussed separately.

You might encounter errors that aren't covered here, as this guide was written retroactively. If anything goes wrong after these changes while trying to run the app locally and you can't understand why, share the error and we can help debug.

Once the app runs locally, spend a few days getting acquainted with the codebase and the app. If you find UI bugs you want to fix, send them over before starting work so nothing is duplicated and tickets can be assigned properly if needed.

Thank you and good luck!

— Maya
