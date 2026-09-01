# Smart Data Frameworks (SDF)

A web-based data migration tool for moving data between databases and file formats. Define reusable migration jobs, execute them with progress tracking, and monitor results through a clean UI.

## Features

- **Multi-source support** — PostgreSQL, MySQL, and filesystem connections (CSV, Parquet, Avro)
- **Reusable jobs** — configure source tables, target destination, filters, and migration mode once; run repeatedly
- **Progress tracking** — per-table row counts, estimated progress bars, execution timestamps
- **Execution history** — full log of all runs with status and error details
- **Credential encryption** — database passwords encrypted at rest (Fernet)
- **Connection testing** — validate credentials before running jobs
- **Stop support** — cancel running jobs from the UI
- **Job validation** — verify source tables exist and configuration is valid before running
- **Retry with backoff** — transient database errors are retried automatically, both during schema reflection (2s, 4s, doubling up to 20s) and batch inserts (1s, 3s, 10s)
- **Graceful shutdown** — running migrations are given up to 30 seconds to complete on shutdown
- **Deletion safety** — connections and jobs cannot be deleted while referenced by any job, running or not
- **Catalog browsing** — pick source tables/views (or files) from a connection's live schema instead of typing them by hand
- **Export / import** — download a connection's or job's configuration as credential-free JSON, and re-import it elsewhere
- **Auto-create target tables** — automatically create tables on the target database if they don't exist, including primary key, non-PK indexes, CHECK constraints, and foreign keys
- **In-app user guide** — a built-in Guide page covering setup and every major feature
- **Card/list views** — toggle how Connections and Jobs are displayed; choice is remembered
- **Dashboard** — aggregate stats, charts, and recent activity at a glance

## Architecture

```
┌─────────────────────────────────────────┐     ┌─────────────────────┐
│  React build + FastAPI (single image)   │────▶│ PostgreSQL / SQLite │
│              port 8000                  │     │  (auto-detected)    │
└─────────────────────────────────────────┘     └─────────────────────┘
```

- **Frontend:** React 18 + TypeScript + Tailwind CSS + TanStack Query (built and served as static assets by FastAPI)
- **Backend:** FastAPI + SQLAlchemy (async) + Uvicorn
- **Database:** PostgreSQL (auto-detected on host) or SQLite (in-container fallback, ephemeral)

## Quick Start

**Docker (recommended — pulls prebuilt image from GHCR):**
```bash
# Grab just the compose file; no clone needed.
curl -fsSL https://raw.githubusercontent.com/smart-associates/sdf/main/docker-compose.yml -o docker-compose.yml
docker compose pull
docker compose up
```

Or from a checkout:
```bash
git clone git@github.com:smart-associates/sdf.git && cd sdf
docker compose pull && docker compose up
```

The compose file uses `network_mode: host`, so the container auto-detects PostgreSQL on the
host's `127.0.0.1:5432`. If none is reachable it falls back to an in-container SQLite
database (ephemeral — no persistence). Override via env vars (see
[GETTING_STARTED.md](GETTING_STARTED.md#option-1b-docker-compose)).

> **macOS/Windows:** enable host networking in Docker Desktop under
> **Settings → Resources → Network**. Linux works out of the box.

Pin a specific version: `SDF_IMAGE_TAG=1.2.0 docker compose up`.

**Build locally, run via compose:**
```bash
git clone git@github.com:smart-associates/sdf.git && cd sdf
docker build -t ghcr.io/smart-associates/sdf:latest .   # tag matches what compose expects
docker compose up                              # no rebuild, no pull — uses the local image
```

**Plain Docker (no compose):**
```bash
git clone git@github.com:smart-associates/sdf.git && cd sdf
docker build -t sdf:local .

docker run --rm --network=host \
  -e ENCRYPTION_KEY="$(openssl rand -hex 16)" \
  sdf:local
```

`--network=host` lets the container reach a host PostgreSQL on `127.0.0.1` and binds port 8000 directly on the host. On Docker Desktop (macOS/Windows) enable host networking in Settings first.

**Local dev (non-Docker):**
```bash
git clone git@github.com:smart-associates/sdf.git && cd sdf
./start.sh dev
```

Open [http://localhost:8000](http://localhost:8000) for the Docker path, or
[http://localhost:5173](http://localhost:5173) for local-dev mode (Vite dev server).

See [GETTING_STARTED.md](GETTING_STARTED.md) for detailed setup instructions.

## Project Structure

```
sdf/
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── main.py        # App entry point + startup
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── routers/       # API route handlers
│   │   └── services/      # Business logic + migration engine
│   ├── docker-entrypoint.py   # Postgres-probe + uvicorn launcher (container only)
│   └── requirements.txt
├── ui/                    # React frontend
│   ├── src/
│   │   ├── api/           # Axios API client functions
│   │   ├── pages/         # Page components
│   │   ├── components/    # Shared UI components
│   │   ├── hooks/         # Shared React hooks
│   │   ├── guide/         # In-app user guide content + loader
│   │   ├── lib/           # Small shared utilities
│   │   └── assets/        # Static assets (logo, etc.)
│   └── package.json
├── Dockerfile             # Unified image (UI build + FastAPI runtime)
├── docker-compose.yml     # Single-service wrapper around the unified image
├── .env.example
└── start.sh
```

## API Documentation

Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs) when the backend is running.

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/connections` | List database connections |
| POST | `/api/connections` | Create a connection |
| GET | `/api/connections/export` | Export all connections as credential-free JSON |
| GET | `/api/connections/{id}` | Get a connection |
| GET | `/api/connections/{id}/export` | Export a single connection as credential-free JSON |
| POST | `/api/connections/import` | Import connections from JSON |
| PUT | `/api/connections/{id}` | Update a connection |
| DELETE | `/api/connections/{id}` | Delete a connection |
| POST | `/api/connections/{id}/test` | Test a connection |
| POST | `/api/connections/{id}/clone` | Clone a connection |
| GET | `/api/connections/{id}/schemas` | List schemas on a connection |
| GET | `/api/connections/{id}/objects` | List tables/views in a schema |
| GET | `/api/connections/{id}/files` | List files (filesystem connections) |
| GET | `/api/jobs` | List jobs |
| POST | `/api/jobs` | Create a job |
| GET | `/api/jobs/export` | Export all jobs as credential-free JSON |
| GET | `/api/jobs/{id}/export` | Export a single job as credential-free JSON |
| POST | `/api/jobs/import` | Import jobs from JSON |
| GET | `/api/jobs/{id}` | Get a job |
| PUT | `/api/jobs/{id}` | Update a job |
| DELETE | `/api/jobs/{id}` | Delete a job |
| POST | `/api/jobs/{id}/validate` | Validate job configuration |
| POST | `/api/jobs/{id}/execute` | Run a job |
| POST | `/api/jobs/{id}/clone` | Clone a job |
| POST | `/api/jobs/{id}/executions/{exec_id}/stop` | Stop a running job |
| GET | `/api/executions` | List executions (filter by `job_id`, paginate with `limit`/`offset`) |
| GET | `/api/executions/{id}` | Get execution with per-table details |
| GET | `/api/executions/{id}/logs` | Get step-by-step logs for an execution |
| GET | `/api/executions/stats` | System-wide stats and recent executions |
| GET | `/api/settings` | List settings |
| POST | `/api/settings` | Create a setting |
| GET | `/api/settings/{id}` | Get a setting |
| PUT | `/api/settings/{id}` | Update a setting |
| DELETE | `/api/settings/{id}` | Delete a setting |
| GET | `/health` | Health check |

## Supported Connection Types

| Type | db_type | Source | Target | Notes |
|------|---------|--------|--------|-------|
| PostgreSQL | `postgresql` | Yes | Yes | |
| MySQL | `mysql` | Yes | Yes | |
| Filesystem | `filesystem` | Yes | Yes | Set `staging_format` to `csv`, `parquet`, or `avro`; `database` is the directory path |

## Migration Modes

- **append** — INSERT rows into the target table (preserves existing data)
- **truncate_load** — TRUNCATE then INSERT (full refresh)

## License

SDF is licensed under the [Business Source License 1.1](LICENSE). See [CONTRIBUTING.md](CONTRIBUTING.md#license) for what that means for contributions.
