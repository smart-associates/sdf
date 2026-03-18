# Getting Started

## Prerequisites

### Docker (recommended path)
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose

### Local dev path
- Python 3.9+
- Node.js 18+ and npm
- PostgreSQL 14+ running locally

---

## Option 1: Docker Compose

The fastest way to run everything.

```bash
./start.sh docker
```

This builds and starts three containers:
- `postgres` — PostgreSQL 16 database
- `api` — FastAPI backend on port 8000
- `ui` — Vite dev server on port 5173

Open [http://localhost:5173](http://localhost:5173).

To stop: `Ctrl+C`, then `docker compose down`.

To reset the database (wipes all data):
```bash
docker compose down -v
```

---

## Option 2: Local Development

### 1. Configure environment

```bash
cp .env.example backend/.env
```

Edit `backend/.env`:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sdf
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/sdf
ENCRYPTION_KEY=your-random-32-char-secret-key!!
CORS_ORIGINS=["http://localhost:5173"]
```

> **Important:** Change `ENCRYPTION_KEY` to a random 32-character string before storing any credentials. This key encrypts database passwords at rest.

### 2. Create the database

```bash
psql -U postgres -c "CREATE DATABASE sdf;"
```

### 3. Start everything

```bash
./start.sh dev
```

This will:
1. Create a Python virtualenv in `backend/.venv`
2. Install Python dependencies
3. Start FastAPI on port 8000
4. Install npm packages
5. Start Vite dev server on port 5173

Or start each service manually:

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
cd ui
npm install
npm run dev
```

---

## First Use

### 1. Add a database connection

Navigate to **Connections** → **Add Connection**.

Fill in:
- **Name** — a label for this connection (e.g. "Production Postgres")
- **Type** — postgresql, mysql, mssql, csv, or parquet
- **Host / Port / Database / Username / Password** — your DB credentials

Click **Test** to verify the connection before saving.

For CSV or Parquet connections, set **Host** to the directory path containing your files (e.g. `/data/exports`).

### 2. Create a migration job

Navigate to **Jobs** → **New Job**.

- **Source Connection** — where data comes from
- **Source Tables** — one table name per line (e.g. `public.orders`)
- **Table Filter** — optional WHERE clause applied to each table (e.g. `created_at > '2024-01-01'`)
- **Target Connection** — where data goes
- **Target Schema** — schema to write into on the target (leave blank to use default)
- **Create Target Table** — auto-create the table if it doesn't exist
- **Migration Mode** — `append` to add rows, `truncate_load` to replace all data

Click **Validate** to check that source tables exist and the job configuration is valid.

### 3. Run the job

From the **Jobs** page, click **Run** next to a job. The button changes to **Stop** while it runs.

Click a job row to see per-table progress, estimated row counts, and status.

### 4. View history

**Logs** shows all past executions with status, duration, record counts, and error messages.

**Dashboard** shows aggregate stats: total runs, success/failure rates, records migrated, and charts of recent activity.

---

## Settings

Navigate to **Settings** to configure system-wide defaults:

| Key | Description |
|-----|-------------|
| `default_output_path` | Default directory for CSV/Parquet output |
| `parallel_jobs` | Max concurrent job executions |
| `default_delimiter` | CSV column delimiter |
| `include_header` | Include header row in CSV output |
| `compress_output` | Compress output files |

---

## Troubleshooting

**Backend won't start — database connection error**
- Make sure PostgreSQL is running and `DATABASE_URL` in `backend/.env` is correct.
- The app creates tables automatically on startup; no manual migrations needed.

**"Connection refused" when testing a connection**
- Verify host/port are reachable from the machine running the backend.
- In Docker mode, use the host machine's IP (not `localhost`) to reach services outside Docker.

**Job fails immediately with permission error**
- The database user needs SELECT on source tables and INSERT/CREATE on target tables.

**Encryption key errors after restart**
- The `ENCRYPTION_KEY` must not change after connections are saved — passwords are encrypted with it. Back it up somewhere safe.

**Port conflicts**
- Backend: set a different port with `uvicorn app.main:app --port <port>`
- Frontend: edit `vite.config.ts` and update the `server.port` value

---

## Environment Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | Async PostgreSQL connection string (asyncpg) |
| `SYNC_DATABASE_URL` | Yes | — | Sync PostgreSQL connection string (psycopg2) |
| `ENCRYPTION_KEY` | Yes | — | 32-char key for encrypting DB passwords |
| `CORS_ORIGINS` | No | `["http://localhost:5173"]` | Allowed frontend origins |
