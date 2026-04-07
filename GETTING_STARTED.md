# Getting Started

## Prerequisites

### Docker (recommended path)
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose

### Local dev path
- Python 3.9+
- Node.js 18+ and npm
- PostgreSQL 14+ (optional — SQLite is used automatically if PostgreSQL is not running)

---

## Option 1: Local Development (recommended)

### 1. Start everything

```bash
./start.sh dev
```

`start.sh` auto-detects your database:
- If PostgreSQL is running locally (checked via `pg_isready`), it connects over the unix socket
- If PostgreSQL is not running, it falls back to a local SQLite database (`sdf.db`)

This will:
1. Auto-detect PostgreSQL or fall back to SQLite
2. Create a Python virtualenv in `backend/.venv`
3. Install Python dependencies
4. Start FastAPI on port 8000
5. Install npm packages
6. Start Vite dev server on port 5173

### 2. (Optional) Use PostgreSQL

If you want to use PostgreSQL, make sure it's running and create the database:

```bash
psql -U postgres -c "CREATE DATABASE sdf;"
```

Then restart with `./start.sh dev` — it will detect PostgreSQL automatically.

### 3. (Optional) Override database settings

To override auto-detection, copy `.env.example` to `backend/.env` and edit it:

```bash
cp .env.example backend/.env
```

```env
DATABASE_URL=postgresql+asyncpg:///sdf?host=/var/run/postgresql
SYNC_DATABASE_URL=postgresql+psycopg2:///sdf?host=/var/run/postgresql
ENCRYPTION_KEY=your-random-32-char-secret-key!!
CORS_ORIGINS=["http://localhost:5173"]
```

> **Important:** Change `ENCRYPTION_KEY` to a random 32-character string before storing any credentials. This key encrypts database passwords at rest.

When `backend/.env` contains `DATABASE_URL`, auto-detection is skipped.

Open [http://localhost:5173](http://localhost:5173). Press `Ctrl+C` to stop both services.

<details>
<summary>Manual start (without start.sh)</summary>

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
</details>

---

## Option 2: Docker Compose

If you prefer containers or don't have PostgreSQL installed locally:

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

## First Use

### 1. Add a database connection

Navigate to **Connections** → **Add Connection**.

Fill in:
- **Name** — a label for this connection (e.g. "Production Postgres")
- **Type** — `postgresql`, `mysql`, `mssql`, or `filesystem`
- **Host / Port / Database / Username / Password** — your DB credentials

Click **Test** to verify the connection before saving.

For filesystem connections (CSV, Parquet, or Avro files), set **Database** to the directory path containing your files (e.g. `/data/exports`) and set **Staging Format** to `csv`, `parquet`, or `avro`.

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

Navigate to **Settings** to configure system-wide defaults. The following setting is seeded automatically on first startup:

| Key | Default | Description |
|-----|---------|-------------|
| `batch_size` | `1000` | Number of rows per INSERT batch |

You can add additional custom settings via the Settings page or the `/api/settings` API endpoint.

---

## Troubleshooting

**Backend won't start — database connection error**
- If using PostgreSQL, make sure it's running (`pg_isready`) and the `sdf` database exists.
- If no `.env` is present, `start.sh` auto-detects: PostgreSQL if running, otherwise SQLite.
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
| `DATABASE_URL` | No | auto-detected | Async DB connection string (asyncpg or aiosqlite) |
| `SYNC_DATABASE_URL` | No | auto-detected | Sync DB connection string (psycopg2 or sqlite) |
| `ENCRYPTION_KEY` | Yes | — | 32-char key for encrypting DB passwords |
| `CORS_ORIGINS` | No | `["http://localhost:5173"]` | Allowed frontend origins |
