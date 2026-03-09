# RAG Module

> **Data Pipeline Hub** — Feature-sliced architecture implementation for document and Slack data ingestion with vector search capabilities.

## Overview

The RAG (Retrieval-Augmented Generation) module handles data ingestion pipelines for multiple source types, processing content into vector embeddings for semantic search. Built with a **Feature-Sliced Architecture** combining hexagonal principles with vertical organization for maximum cohesion and maintainability.

### Key Features

- 📄 **Document Processing** — PDF, Markdown ingestion with intelligent chunking
- 💬 **Slack Integration** — Channel and thread message indexing
- 🔍 **Vector Search** — Semantic similarity search via Qdrant
- ⚡ **Async Pipelines** — Celery-based background task execution
- 🔌 **Pluggable Adapters** — Easy to swap MongoDB, Qdrant, or add new sources
- ☁️ **Remote Services** — Document conversion and embedding can run as external HTTP micro-services (switchable via feature flags, no code changes required)

---

## Architecture

```
rag/
├── core/            # 🎯 Business logic + services (domain + use cases)
├── infrastructure/  # 🔌 Adapters (Mongo, Qdrant, Celery, HTTP, Sources)
├── bootstrap/       # ⚡ Dependency injection & app setup
├── config/          # ⚙️ Configuration management
├── shared/          # 🔧 Cross-cutting utilities (logging)
```

### Layer Responsibilities

| Layer | Purpose | Dependencies |
|-------|---------|--------------|
| **Core** | Business rules, domain models, ports, services | None (pure Python) |
| **Infrastructure** | External system adapters | Core + external libs |
| **Bootstrap** | Wiring, DI container, app factory | All layers |

### Dependency Flow

```
Infrastructure ───────▶ Core ◀──────── Bootstrap
   (Adapters)       (Domain + Services)    (Wiring)

         Adapters depend on Core abstractions,
              Core has no dependencies!
```

📖 **See [DIAGRAMS.md](./DIAGRAMS.md) for detailed flow diagrams.**

---

## Quick Start

### Prerequisites

- Python 3.10+
- MongoDB (running on localhost:27017)
- Qdrant (running on localhost:6333)
- RabbitMQ (running on localhost:5672)

### Installation

```bash
cd rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install package in development mode
pip install -e .
```

### Environment Variables

Create a `.env` file or export these variables:

### Running the Server

```bash
# Development server
python -m bootstrap.flask_app

```

### Running Celery Workers

```bash
# Start pipeline worker
celery -A infrastructure.celery.app worker -Q document_queue,slack_queue -l info

# Start event worker (Slack events)
celery -A infrastructure.celery.app worker -Q slack_events -l info
```

---

## Core Modules

The `core/` directory contains feature-sliced modules, each with its own domain models, ports, and services.

### Data Sources (`core/data_sources/`)

Central module for managing data source lifecycle.

| Component | Path | Purpose |
|-----------|------|---------|
| `DataSource` model | `domain/model.py` | Data source entity |
| `DataSourceRepository` port | `domain/repository.py` | Storage interface |
| `DataSourceService` | `service.py` | CRUD operations |

#### Source Types (`core/data_sources/types/`)

Source-specific processing logic organized by type:

**Document** (`types/document/`)
| Component | Purpose |
|-----------|---------|
| `DocumentProcessor` | Text extraction from PDF/Markdown |
| `DocumentPipelineHandler` | Pipeline execution for documents |
| `DocumentRegistration` | Document registration strategy |
| `FileValidationService` | Pre-upload file validation |
| Validators | Extension, size, duplicate checks |

**Slack** (`types/slack/`)
| Component | Purpose |
|-----------|---------|
| `SlackProcessor` | Message/thread processing |
| `SlackPipelineHandler` | Pipeline execution for channels |
| `SlackRegistration` | Channel registration strategy |
| `SlackChannel` model | Channel entity (`domain/channel/`) |
| `SlackEvent` model | Event entity (`domain/event/`) |
| Event handlers | Channel created, message events |
| Validators | Bot installation checks |

### Pipeline (`core/pipeline/`)

Pipeline lifecycle and execution.

| Component | Path | Purpose |
|-----------|------|---------|
| `PipelineRecord` model | `domain/model.py` | Pipeline state entity |
| `PipelineRepository` port | `domain/repository.py` | State storage interface |
| `PipelineDispatcher` port | `domain/dispatcher.py` | Async dispatch interface |
| `PipelineService` | `service.py` | Lifecycle management |
| `PipelineDispatchService` | `dispatch_service.py` | Registration + dispatch |
| `PipelineExecutor` | `executor.py` | Pipeline step execution |

### Vector (`core/vector/`)

Vector storage and embedding.

| Component | Path | Purpose |
|-----------|------|---------|
| `VectorChunk` model | `domain/model.py` | Chunk with embedding |
| `VectorRepository` port | `domain/repository.py` | Vector storage interface |
| `ContentChunker` port | `domain/chunker.py` | Chunking interface |
| `EmbeddingGenerator` port | `domain/embedder.py` | Embedding interface |
| `VectorStatsService` | `stats_service.py` | Storage statistics |

### Other Core Modules

| Module | Purpose |
|--------|---------|
| `core/retrieval/` | Vector search orchestration |
| `core/registration/` | Source registration factory & service |
| `core/validation/` | Validation pipeline framework |
| `core/monitoring/` | Pipeline metrics and logging |
| `core/pagination/` | Pagination model |
| `core/connector/` | Base connector interface |
| `core/processing/` | Base processor interface |
| `core/user/terms_approval/` | User terms acceptance |

---

## Infrastructure Layer

Concrete implementations of core ports using external technologies.

### Storage Adapters (`infrastructure/mongo/`)

| Adapter | Implements |
|---------|------------|
| `MongoPipelineRepository` | `PipelineRepository` |
| `MongoDataSourceRepository` | `DataSourceRepository` |
| `MongoMonitoringRepository` | `MonitoringRepository` |
| `MongoTermsApprovalRepository` | `TermsApprovalRepository` |
| `MongoSlackChannelRepository` | `SlackChannelRepository` (in `data_sources/`) |

### Vector Storage (`infrastructure/qdrant/`)

| Adapter | Implements |
|---------|------------|
| `QdrantVectorRepository` | `VectorRepository` |

### Source Adapters (`infrastructure/sources/`)

Source-specific infrastructure organized by type:

**Document** (`sources/document/`)
| Adapter | Purpose |
|---------|---------|
| `DocumentChunker` | PDF/Markdown chunking strategy |
| `DocumentConnector` | File loading (wraps a `DocumentConverterPort`) |
| `DocumentConfig` | Document-specific settings |
| `LocalDoclingAdapter` | Runs the `docling` library in-process |
| `RemoteDoclingAdapter` | Delegates to the external Docling HTTP service |
| Validators | Duplicate checking adapters |

Converter adapters implement `DocumentConverterPort` and are **lazily imported** via `infrastructure/sources/document/converters/__init__.py` to avoid loading the `docling` package when only the remote adapter is required.

**Slack** (`sources/slack/`)
| Adapter | Purpose |
|---------|---------|
| `SlackChunker` | Conversation-aware chunking |
| `SlackConnector` | Slack API integration |
| `SlackConfig` | Slack-specific settings |
| `ThreadRetriever` | Thread message fetching |
| Validators | Bot installation checking |

### Processing Adapters (`infrastructure/embedding/`)

Each adapter implements the `EmbeddingPort` and `HealthCheckable` protocols. The active adapter is selected at startup via the `use_remote_embedding` feature flag.

| Adapter | Mode | Purpose |
|---------|------|---------|
| `LocalEmbeddingAdapter` | local | Runs `sentence-transformers` in-process → 384-dim vectors |
| `RemoteEmbeddingAdapter` | remote | Delegates to the external Embedding HTTP service |

Adapters are **lazily imported** via `infrastructure/embedding/embedders/__init__.py`, so heavy libraries (e.g. `sentence-transformers`, `torch`) are never loaded when only the remote adapter is used.

### HTTP Adapters (`infrastructure/http/`)

| Blueprint | Path Prefix |
|-----------|-------------|
| `/health` | Health checks |
| `/docs` | Document operations |
| `/slack` | Slack operations |
| `/pipelines` | Pipeline management |
| `/data-sources` | Data source management |
| `/vector` | Vector statistics |
| `/settings` | Configuration |
| `/terms-approval` | User terms |

### Async Adapters (`infrastructure/celery/`)

| Adapter | Purpose |
|---------|---------|
| `CeleryPipelineDispatcher` | Dispatch pipeline tasks |
| `CelerySlackEventDispatcher` | Dispatch Slack event handlers |
| `pipeline_tasks.py` | Celery worker tasks |

---

## Remote Services

The RAG service supports two execution modes for its two compute-heavy steps — **document conversion** and **embedding generation**. Each step can run either in-process (local) or by calling a dedicated HTTP micro-service (remote). The choice is made at startup via feature flags and has no impact on the core pipeline logic.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        bootstrap (wiring)                            │
│  DocumentConnectorFactory.from_app_config()                          │
│  EmbeddingGeneratorFactory.from_app_config()                         │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ reads use_remote_* flags once at startup
          ┌────────────┴─────────────┐
          ▼                          ▼
   LOCAL adapters              REMOTE adapters
   LocalDoclingAdapter  ◀──▶  RemoteDoclingAdapter ──▶ Docling HTTP API
   LocalEmbeddingAdapter◀──▶  RemoteEmbeddingAdapter──▶ Embedding HTTP API
          │                          │
          └────────────┬─────────────┘
                       ▼
               Domain ports (core layer)
          DocumentConverterPort  /  EmbeddingPort
```

The core pipeline only depends on the **domain ports** (`DocumentConverterPort`, `EmbeddingPort`). The adapters are swapped at the composition root without touching any business logic.

---

### Remote Docling Service

Converts uploaded documents (PDF, etc.) to structured text and Markdown by calling the Docling HTTP service.

**Domain port:** `core/data_sources/types/document/domain/document_converter.py`

```python
class DocumentConverterPort(Protocol):
    is_remote: bool
    def convert_file(self, file_path: str) -> ConversionResult: ...
    def convert_url(self, document_url: str) -> ConversionResult: ...
    def test_connection(self) -> bool: ...
```

**Remote adapter:** `infrastructure/sources/document/converters/remote_docling_adapter.py`

| Class | Implements | Key detail |
|-------|-----------|------------|
| `RemoteDoclingAdapter` | `DocumentConverterPort` | Delegates to `DoclingService` (from `global_utils`) |

The adapter calls `DoclingService.process_file()` / `process_url()`, which posts to the Docling HTTP service and returns a response with `text`, `markdown`, and `metadata` fields.  
The adapter builds a `ConversionResult` and estimates `page_count` from character count when the service does not return it.

**HTTP client chain** (`global_utils.docling`):

```
RemoteDoclingAdapter
  └── DoclingService
        └── DoclingClient (httpx)
              ├── POST /v1/convert/file   (multipart, for local files)
              ├── POST /v1/convert/source (JSON, for URLs)
              └── GET  /health
```

**Factory method:**

```python
# bootstrap/factories.py
DocumentConverterFactory.create_remote(
    base_url="https://...",
    timeout=300,
    image_export_mode="placeholder",
    pdf_backend="pypdfium2",
)
```

---

### Remote Embedding Service

Generates vector embeddings for text chunks by calling the Embedding HTTP service.

**Domain port:** `core/vector/domain/embedder.py`

```python
class EmbeddingPort(Protocol):
    is_remote: bool
    embedding_dim: int
    def encode_texts(self, texts: List[str]) -> List[np.ndarray]: ...
    def encode_single(self, text: str) -> np.ndarray: ...
    def test_connection(self) -> bool: ...
```

**Remote adapter:** `infrastructure/embedding/embedders/remote_embedding_adapter.py`

| Class | Implements | Key detail |
|-------|-----------|------------|
| `RemoteEmbeddingAdapter` | `EmbeddingPort`, `HealthCheckable` | Delegates to `EmbeddingService` (from `global_utils`) |

The adapter calls `EmbeddingService.generate_embeddings(texts)`, which posts to the Embedding HTTP service (OpenAI-compatible `/v1/embeddings` format) and returns a list of float vectors.

**HTTP client chain** (`global_utils.embedding`):

```
RemoteEmbeddingAdapter
  └── EmbeddingService
        └── EmbeddingClient (httpx)
              ├── POST /v1/embeddings   (OpenAI-style, texts + model)
              └── GET  /health
```

**Factory method:**

```python
# bootstrap/factories.py
EmbeddingPortFactory.create_remote(
    base_url="https://...",
    timeout=60,
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    embedding_dim=384,
)
```

---

### Health Checks (`core/health/`)

A registry-based health system checks whether remote services are reachable before allowing document uploads.

**Protocol:** `core/health/domain/port.py`

```python
class HealthCheckable(Protocol):
    is_remote: bool          # True → HTTP check; False → always "local" (no check)
    def test_connection(self) -> bool: ...
```

Both `RemoteDoclingAdapter` and `RemoteEmbeddingAdapter` implement this protocol.  
Both `LocalDoclingAdapter` and `LocalEmbeddingAdapter` implement it with `is_remote = False` — no network call is made.

**Service:** `core/health/service.py` — `ServicesHealthService`

```python
service = ServicesHealthService()
service.register("docling",   document_connector())   # same instance used by the pipeline
service.register("embedding", embedding_generator())  # same instance used by the pipeline

result = service.check_all()
# result.upload_enabled → True when docling + embedding are healthy or local
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `"local"` | Adapter runs in-process — no network check needed |
| `"healthy"` | Remote service responded successfully |
| `"unhealthy"` | Remote service unreachable or returned an error |

**Response shape (JSON):**

```json
{
  "docling":   { "status": "healthy",  "mode": "remote", "message": "Service is available" },
  "embedding": { "status": "healthy",  "mode": "remote", "message": "Service is available" },
  "upload_enabled": true
}
```

`upload_enabled` is `false` when any required service (docling or embedding) is `"unhealthy"`.

---

### Feature Flags

The adapter selection is controlled by two boolean flags in `config/app_config.py`:

| Flag | Env Variable | Default | Effect |
|------|-------------|---------|--------|
| `use_remote_docling` | `USE_REMOTE_DOCLING` | `true` | `RemoteDoclingAdapter` when `true`, `LocalDoclingAdapter` when `false` |
| `use_remote_embedding` | `USE_REMOTE_EMBEDDING` | `true` | `RemoteEmbeddingAdapter` when `true`, `LocalEmbeddingAdapter` when `false` |

The decision is encapsulated in `DocumentConnectorFactory.from_app_config()` and `EmbeddingGeneratorFactory.from_app_config()` — the composition root (`app_container.py`) performs **pure wiring** with no branching on configuration.

---

### Lazy Imports

Both adapter packages use `__getattr__`-based lazy loading so that installing only one backend is sufficient:

```python
# infrastructure/embedding/embedders/__init__.py
# infrastructure/sources/document/converters/__init__.py
_ADAPTER_MAP = {
    "LocalEmbeddingAdapter":  ("<module>", "LocalEmbeddingAdapter"),
    "RemoteEmbeddingAdapter": ("<module>", "RemoteEmbeddingAdapter"),
}

def __getattr__(name):
    module_path, attr = _ADAPTER_MAP[name]
    return getattr(importlib.import_module(module_path), attr)
```

This prevents `sentence-transformers` / `torch` / `docling` from being imported when only the remote adapter is active.

---

## Dependency Injection

All dependencies are wired in `bootstrap/app_container.py` using `@lru_cache` for singleton management.

### Usage

```python
from bootstrap.app_container import (
    pipeline_service,
    data_source_service,
    retrieval_service,
)

# Services are singletons - same instance on every call
svc = pipeline_service()
result = svc.get(pipeline_id)

# Parameterized singletons
retriever = retrieval_service("DOCUMENT")  # One per source type
```

### Available Factories

```python
# Infrastructure (shared resources)
mongo_client()              # MongoDB connection pool
file_storage()              # Local file storage

# Repositories
pipeline_repository()       # Pipeline state storage
data_source_repository()    # Data source metadata
vector_repository(name)     # Vector storage (per collection)

# Services
pipeline_service()          # Pipeline lifecycle
data_source_service()       # Data source CRUD
monitoring_service()        # Metrics & logging
retrieval_service(type)     # Vector search
remote_services_health()    # Health checker for Docling + Embedding services

# Pipeline Components
embedding_generator()       # Local or remote embedding (set by USE_REMOTE_EMBEDDING)
document_chunker()          # Document chunking
slack_chunker()             # Conversation chunking
document_connector()        # Local or remote document conversion (set by USE_REMOTE_DOCLING)
slack_connector(project)    # Slack API client
```

---

## API Endpoints

### Health

```
GET /health           → Service health status
```

### Documents

```
POST   /docs/upload   → Upload document(s)
GET    /docs          → List documents (paginated)
DELETE /docs/{id}     → Delete document
```

### Slack

```
POST   /slack/channels      → Register Slack channels
GET    /slack/channels      → List registered channels
DELETE /slack/channels/{id} → Remove channel
POST   /slack/events        → Slack Events API webhook
```

### Pipelines

```
GET    /pipelines           → List all pipelines
GET    /pipelines/{id}      → Get pipeline status
DELETE /pipelines/{id}      → Cancel/delete pipeline
```

### Vector Search

```
POST   /vector/search       → Semantic search
GET    /vector/stats        → Vector storage statistics
```

---

## Configuration

Configuration is managed via `config/app_config.py` (extends `SharedConfig`) with environment variable overrides.

**Core infrastructure**

| Config Key | Env Variable | Default | Description |
|------------|--------------|---------|-------------|
| `mongodb_ip` | `MONGODB_IP` | `0.0.0.0` | MongoDB host |
| `mongodb_port` | `MONGODB_PORT` | `27017` | MongoDB port |
| `qdrant_ip` | `QDRANT_IP` | `0.0.0.0` | Qdrant host |
| `qdrant_port` | `QDRANT_PORT` | `6333` | Qdrant port |
| `rabbitmq_ip` | `RABBITMQ_IP` | `0.0.0.0` | RabbitMQ host |
| `port` | `PORT` | `13457` | Server port |
| `upload_folder` | `UPLOAD_FOLDER` | `/app/shared` | File upload path |

**Remote Docling service**

| Config Key | Env Variable | Default | Description |
|------------|--------------|---------|-------------|
| `use_remote_docling` | `USE_REMOTE_DOCLING` | `true` | Use remote Docling adapter |
| `docling_service_url` | `DOCLING_SERVICE_URL` | *(OpenShift URL)* | Base URL of Docling HTTP service |
| `docling_service_timeout` | `DOCLING_SERVICE_TIMEOUT` | `300` | Request timeout in seconds |

**Remote Embedding service**

| Config Key | Env Variable | Default | Description |
|------------|--------------|---------|-------------|
| `use_remote_embedding` | `USE_REMOTE_EMBEDDING` | `true` | Use remote Embedding adapter |
| `embedding_service_url` | `EMBEDDING_SERVICE_URL` | *(OpenShift URL)* | Base URL of Embedding HTTP service |
| `embedding_service_timeout` | `EMBEDDING_SERVICE_TIMEOUT` | `60` | Request timeout in seconds |
| `embedding_service_model` | `EMBEDDING_SERVICE_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Model to request from the service |
| `embedding_dim` | `EMBEDDING_DIM` | `384` | Vector dimension (must match the model) |

---

## Data Flow

### Document Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Upload    │────▶│  Validate &  │────▶│   Celery    │────▶│   Execute    │
│   Request   │     │   Register   │     │   Queue     │     │   Pipeline   │
└─────────────┘     └──────────────┘     └─────────────┘     └──────┬───────┘
                                                                    │
                                                             ┌───────▼───────┐
                                                             │    Convert    │
                                                             │ LocalDocling  │
                                                             │     OR        │
                                                             │ RemoteDocling │
                                                             │  HTTP service │
                                                             └───────┬───────┘
                                                                    │
                   ┌──────────────┐     ┌─────────────┐     ┌───────▼───────┐
                   │    Store     │◀────│   Embed     │◀────│    Chunk      │
                   │   (Qdrant)   │     │  LocalEmb   │     │   (500 tok)   │
                   └──────────────┘     │     OR      │     └───────────────┘
                                        │  RemoteEmb  │
                                        │ HTTP service│
                                        └─────────────┘
```

### Search Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Query     │────▶│    Embed     │────▶│   Vector    │────▶│   Return     │
│   Text      │     │    Query     │     │   Search    │     │   Results    │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
```

---

## Extending

### Adding a New Data Source

1. **Core Domain**: Create `core/data_sources/types/<source>/domain/` with models
2. **Core Handler**: Implement `SourcePipelinePort` in `core/data_sources/types/<source>/pipeline_handler.py`
3. **Core Registration**: Add registration strategy in `core/data_sources/types/<source>/registration.py`
4. **Infrastructure Adapters**: Add connector, chunker in `infrastructure/sources/<source>/`
5. **Wire Dependencies**: Add factories to `bootstrap/app_container.py`
6. **HTTP Endpoints**: Create blueprint in `infrastructure/http/<source>.py`

### Swapping an Adapter

To replace Qdrant with Pinecone:

1. Create `infrastructure/pinecone/pinecone_vector_repository.py`
2. Implement `VectorRepository` interface from `core/vector/domain/repository.py`
3. Update `bootstrap/factories.py` to use new adapter
4. No changes needed in core layer ✅

---

## Project Structure

```
rag/
├── core/
│   ├── health/
│   │   ├── domain/
│   │   │   ├── model.py               # ServiceHealthStatus, ServicesHealthResult
│   │   │   └── port.py                # HealthCheckable protocol
│   │   └── service.py                 # ServicesHealthService (registry-based)
│   ├── connector/domain/              # Base connector interface
│   ├── data_sources/
│   │   ├── domain/                    # DataSource model & repository port
│   │   ├── service.py                 # Data source CRUD
│   │   └── types/
│   │       ├── document/
│   │       │   ├── domain/            # Document processor
│   │       │   ├── validators/        # Extension, size, duplicate validators
│   │       │   ├── document_service.py
│   │       │   ├── file_validation_service.py
│   │       │   ├── log_parser.py
│   │       │   ├── pipeline_handler.py
│   │       │   └── registration.py
│   │       └── slack/
│   │           ├── domain/
│   │           │   ├── channel/       # SlackChannel model & repository port
│   │           │   ├── event/         # SlackEvent model & dispatcher port
│   │           │   └── processor.py
│   │           ├── event/
│   │           │   ├── handlers/      # Event handlers (channel_created, etc.)
│   │           │   ├── dispatch_service.py
│   │           │   └── service.py
│   │           ├── validators/        # Bot installation validator
│   │           ├── log_parser.py
│   │           ├── pipeline_handler.py
│   │           ├── registration.py
│   │           └── stats_service.py
│   ├── monitoring/
│   │   ├── domain/                    # Monitoring model & repository port
│   │   ├── parsing/                   # Log parsing utilities
│   │   └── service.py
│   ├── pagination/domain/             # Pagination model
│   ├── pipeline/
│   │   ├── domain/                    # Pipeline model, repository, dispatcher ports
│   │   ├── dispatch_service.py
│   │   ├── executor.py
│   │   └── service.py
│   ├── processing/domain/             # Base processor interface
│   ├── registration/
│   │   ├── domain/                    # Registration model & port
│   │   ├── base_registration.py
│   │   ├── factory.py
│   │   └── service.py
│   ├── retrieval/
│   │   └── service.py                 # Vector search orchestration
│   ├── user/terms_approval/
│   │   ├── domain/                    # Terms model & repository port
│   │   └── service.py
│   ├── validation/
│   │   ├── domain/                    # Validation model & port
│   │   └── validator.py
│   └── vector/
│       ├── domain/                    # Vector model, repository, chunker, embedder ports
│       └── stats_service.py
│
├── infrastructure/
│   ├── celery/
│   │   ├── app.py                     # Celery application
│   │   ├── pipeline_dispatcher.py     # Pipeline task dispatcher
│   │   ├── slack_event_dispatcher.py  # Slack event dispatcher
│   │   └── workers/
│   │       └── pipeline_tasks.py      # Worker task definitions
│   ├── config/
│   │   └── base_config_manager.py
│   ├── embedding/
│   │   ├── embedding_generator.py             # DefaultEmbeddingGenerator
│   │   └── embedders/
│   │       ├── __init__.py                    # Lazy adapter loader
│   │       ├── local_embedding_adapter.py     # SentenceTransformer (in-process)
│   │       └── remote_embedding_adapter.py    # HTTP embedding service
│   ├── http/                          # Flask blueprints
│   │   ├── blueprints.py
│   │   ├── data_sources.py
│   │   ├── docs.py
│   │   ├── health.py
│   │   ├── pipelines.py
│   │   ├── settings.py
│   │   ├── slack.py
│   │   ├── terms_approval.py
│   │   └── vector.py
│   ├── mongo/
│   │   ├── data_sources/
│   │   │   └── slack_channel_repository.py
│   │   ├── data_source_repository.py
│   │   ├── monitoring_repository.py
│   │   ├── pagination_builder.py
│   │   ├── pipeline_repository.py
│   │   └── terms_approval_repository.py
│   ├── qdrant/
│   │   └── qdrant_vector_repository.py
│   ├── retrieval/
│   │   └── source_filter_resolver.py
│   ├── sources/
│   │   ├── document/
│   │   │   ├── chunker.py
│   │   │   ├── config.py
│   │   │   ├── connector.py
│   │   │   ├── converters/
│   │   │   │   ├── __init__.py                # Lazy adapter loader
│   │   │   │   ├── local_docling_adapter.py   # docling library (in-process)
│   │   │   │   └── remote_docling_adapter.py  # HTTP Docling service
│   │   │   └── validator/
│   │   │       ├── duplicate_checker.py
│   │   │       └── name_duplicate_checker.py
│   │   └── slack/
│   │       ├── chunker.py
│   │       ├── config.py
│   │       ├── connector.py
│   │       ├── thread_retriever.py
│   │       ├── thread_retriever_worker.py
│   │       └── validator/
│   │           └── bot_installation_checker.py
│   ├── storage/
│   │   └── local_file_storage.py
│   └── umami/
│       └── umami_client.py
│
├── bootstrap/
│   ├── app_container.py               # Dependency injection container (composition root)
│   ├── factories.py                   # DocumentConnectorFactory, EmbeddingGeneratorFactory, etc.
│   └── flask_app.py                   # Flask application factory
│
├── config/
│   └── app_config.py                  # Application configuration
│
├── shared/
│   └── logger.py                      # Logging utilities
│
├── requirements.txt                   # Python dependencies
├── setup.py                           # Package setup
├── DIAGRAMS.md                        # Flow diagrams
└── README.md                          # This file
```

---

## Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| `flask` | HTTP framework | always |
| `qdrant-client` | Vector database client | always |
| `celery` | Async task queue | always |
| `pymongo` | MongoDB driver | always |
| `httpx` | HTTP client for remote service calls | always |
| `langchain` | LLM utilities | always |
| `sentence-transformers` | Embedding generation (local mode) | `USE_REMOTE_EMBEDDING=false` |
| `docling` | Document parsing (local mode) | `USE_REMOTE_DOCLING=false` |

When running with both remote flags enabled (`USE_REMOTE_DOCLING=true`, `USE_REMOTE_EMBEDDING=true`), `docling` and `sentence-transformers` / `torch` are never imported — only `httpx` is used for external calls.

---
