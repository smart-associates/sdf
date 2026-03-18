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
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React + Vite  │────▶│  FastAPI (Python) │────▶│   PostgreSQL    │
│   (port 5173)   │     │   (port 8000)     │     │   (port 5432)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

- **Frontend:** React 18 + TypeScript + Tailwind CSS + TanStack Query
- **Backend:** FastAPI + SQLAlchemy (async) + Uvicorn
- **Database:** PostgreSQL 16

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
| POST | `/api/connections/{id}/test` | Test a connection |
| GET | `/api/jobs` | List jobs |
| POST | `/api/jobs` | Create a job |
| POST | `/api/jobs/{id}/execute` | Run a job |
| POST | `/api/jobs/{id}/executions/{exec_id}/stop` | Stop a running job |
| GET | `/api/executions/stats` | System-wide stats |
| GET | `/health` | Health check |

## Supported Database Types

| Type | Source | Target |
|------|--------|--------|
| PostgreSQL | Yes | Yes |
| MySQL | Yes | Yes |
| MSSQL | Yes | Yes |
| CSV | Yes | Yes |
| Parquet | Yes | Yes |

## Migration Modes

- **append** — INSERT rows into the target table (preserves existing data)
- **truncate_load** — TRUNCATE then INSERT (full refresh)
