# Backend (Platform Service)

Lightweight Flask service for cross-cutting platform concerns. Runs on port **8005**, proxied via `/api4` from the UI.

For architecture details, patterns, and conventions see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Prerequisites

- Python 3.11+
- MongoDB instance
- `global_utils` package (shared across services, installed as editable)

## Setup

```bash
cd backend

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -e ../global_utils/
```

## Running

### Development

```bash
python run/dev.py
```

Starts Flask dev server with auto-reload on `0.0.0.0:8005`.

### Production

```bash
gunicorn -w 2 -b 0.0.0.0:8005 run.wsgi:application
```

### Docker

```bash
# From repo root
docker build -f backend/Dockerfile -t unifai-backend .
docker run -p 8005:8005 unifai-backend
```

## Configuration

Environment-driven via `AppConfig` (inherits from `global_utils.config.SharedConfig`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_DB` | `config` | MongoDB database name |
| `ADMIN_CONFIG_COLL` | `admin_config` | Collection for stored config values |
| `HOSTNAME_LOCAL` | `0.0.0.0` | Bind address |
| `PORT` | `8005` | Server port |
| `RAG_URL` | `http://localhost:13457` | RAG service URL (for action dispatch) |

## API Endpoints

All endpoints are prefixed with `/api/admin_config/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/config.get` | Full config template merged with stored values |
| PUT | `/config.section.update` | Update a single section's values |
| GET | `/access.check?username=...` | Check admin access for a username |
| GET | `/api/health/` | Health check |
