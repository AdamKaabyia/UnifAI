# MAS — Multi-Agent System

A production-grade orchestration engine for building and executing multi-agent workflows. Define agent graphs as visual blueprints, run them locally or across distributed workers, and stream results to clients in real time.

---

## Features

- **Blueprint-driven workflows** — Define agent graphs declaratively with nodes, edges, and conditional routing. Blueprints are portable, versionable, and shareable.
- **Two execution modes** — Run graphs in-process (LangGraph) for development, or distribute them across Temporal workers for production.
- **Real-time streaming** — Stream node output as NDJSON over HTTP. Supports both synchronous and fire-and-forget (Redis Streams) modes.
- **Rich element catalog** — Built-in agents, tools (SSH, MCP, web fetch, OpenShift), LLM providers (OpenAI, Gemini), conditions, and RAG retrievers.
- **Horizontal scaling** — Temporal workers scale across pods. Redis Streams enable cross-process event delivery. MongoDB provides persistence.

---

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB
- Redis *(optional — for background streaming)*
- Temporal Server *(optional — for distributed execution)*

### Install

```bash
cd multi-agent

# Everything
pip install -e ".[all]"

# Or only what you need
pip install -e ".[flask,mongo,langgraph]"       # Local-only
pip install -e ".[flask,mongo,temporal,redis]"   # Distributed
```

### Configure

Create a `.env` file (or export environment variables):

```bash
# Server
HOSTNAME=0.0.0.0
PORT=8002

# MongoDB
MONGODB_IP=localhost
MONGODB_PORT=27017
MONGO_DB=UnifAI

# Engine: "temporal" or "langgraph"
ENGINE_NAME=temporal

# Temporal (when using temporal engine)
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=graph-engine

# Redis (enables background streaming)
REDIS_URL=redis://localhost:6379
REDIS_STREAM_TTL=3600          # Retention in seconds (0 = forever)

```

### Run

```bash
# Development server
mas api --dev

# Production server
mas api --workers 4

# Temporal worker (one or more instances)
mas worker --threads 20
```

---

## API

All endpoints live under `/api/`. Session endpoints use RPC-style naming.

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions/user.session.create` | Create a session from a blueprint |
| `POST` | `/sessions/user.session.execute` | Execute synchronously (supports streaming) |
| `POST` | `/sessions/user.session.submit` | Submit for background execution (202) |
| `GET` | `/sessions/session.state.get` | Get final graph state |
| `GET` | `/sessions/session.status.get` | Get session status |
| `DELETE` | `/sessions/session.delete` | Delete a session |

### Streaming & Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sessions/session.subscribe?sessionId=ID` | NDJSON event stream (replays full history) |
| `GET` | `/sessions/session.stream.status?sessionId=ID` | Stream metadata (event count, active flag) |
| `GET` | `/sessions/session.stream.active` | List all running sessions |

### Other

Blueprints, catalog, resources, graph, templates, shares, statistics, actions, and health endpoints are also available.

---

## Usage Examples

### Synchronous execution with streaming

```bash
curl -N -X POST http://localhost:8002/api/sessions/user.session.execute \
  -H 'Content-Type: application/json' \
  -d '{"sessionId": "abc-123", "inputs": {"user_prompt": "hello"}, "stream": true}'
```

### Fire-and-forget with live subscription

```bash
# 1. Submit
curl -X POST http://localhost:8002/api/sessions/user.session.submit \
  -H 'Content-Type: application/json' \
  -d '{"sessionId": "abc-123", "inputs": {"user_prompt": "hello"}}'

# 2. Subscribe to events
curl -N 'http://localhost:8002/api/sessions/session.subscribe?sessionId=abc-123'
```

### Polling

```bash
# Check progress
curl 'http://localhost:8002/api/sessions/session.stream.status?sessionId=abc-123'
# → {"session_id": "abc-123", "event_count": 47, "is_active": false}
```

---

## Extras Reference

| Extra | Purpose |
|-------|---------|
| `flask` | HTTP API server |
| `mongo` | Database persistence |
| `temporal` | Distributed workflow engine |
| `langgraph` | In-process graph execution |
| `llms` | OpenAI, Google Gemini providers |
| `tools` | SSH, MCP, web fetch, OpenShift tools |
| `a2a` | Agent-to-Agent protocol |
| `rag` | RAG retrievers |
| `redis` | Distributed streaming |
| `all` | Everything |

---

## License

Proprietary.
