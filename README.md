# Smart Data Frameworks (SDF)

A web-based data migration tool for moving data between databases and file formats. Define reusable migration jobs, execute them with progress tracking, and monitor results through a clean UI.

## Features

- **Multi-source support** — PostgreSQL, MySQL, MSSQL, CSV files, Parquet files
- **Reusable jobs** — configure source tables, target destination, filters, and migration mode once; run repeatedly
- **Progress tracking** — per-table row counts, estimated progress bars, execution timestamps
- **Execution history** — full log of all runs with status and error details
- **Credential encryption** — database passwords encrypted at rest (Fernet)
- **Connection testing** — validate credentials before running jobs
- **Stop support** — cancel running jobs from the UI

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   React + Vite  │────▶│  FastAPI (Python) │────▶│ PostgreSQL / SQLite │
│   (port 5173)   │     │   (port 8000)     │     │                     │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
```

- **Frontend:** React 18 + TypeScript + Tailwind CSS + TanStack Query
- **Backend:** FastAPI + SQLAlchemy (async) + Uvicorn
- **Database:** PostgreSQL (preferred) or SQLite (auto-detected on startup)

## Quick Start

**Docker (recommended):**
```bash
git clone <repo-url>
cd sdf
./start.sh docker
```

**Local dev:**
```bash
git clone <repo-url>
cd sdf
./start.sh dev
```

Then open [http://localhost:5173](http://localhost:5173).

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
│   ├── requirements.txt
│   └── Dockerfile
├── ui/                    # React frontend
│   ├── src/
│   │   ├── api/           # Axios API client functions
│   │   ├── pages/         # Page components
│   │   └── components/    # Shared UI components
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
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
| GET | `/api/connections/{id}` | Get a connection |
| PUT | `/api/connections/{id}` | Update a connection |
| DELETE | `/api/connections/{id}` | Delete a connection |
| POST | `/api/connections/{id}/test` | Test a connection |
| GET | `/api/jobs` | List jobs |
| POST | `/api/jobs` | Create a job |
| GET | `/api/jobs/{id}` | Get a job |
| PUT | `/api/jobs/{id}` | Update a job |
| DELETE | `/api/jobs/{id}` | Delete a job |
| POST | `/api/jobs/{id}/validate` | Validate job configuration |
| POST | `/api/jobs/{id}/execute` | Run a job |
| POST | `/api/jobs/{id}/executions/{exec_id}/stop` | Stop a running job |
| GET | `/api/executions` | List executions (filter by `job_id`, paginate with `limit`/`offset`) |
| GET | `/api/executions/{id}` | Get execution with per-table details |
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
| MSSQL | `mssql` | Yes | Yes | |
| Filesystem | `filesystem` | Yes | Yes | Set `staging_format` to `csv` or `parquet`; `database` is the directory path |

## Migration Modes

- **append** — INSERT rows into the target table (preserves existing data)
- **truncate_load** — TRUNCATE then INSERT (full refresh)
