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

---

## Running Tests

### Backend (pytest)

```bash
cd backend
source .venv/bin/activate
python -m pytest -v
```

Database detection mirrors `start.sh`: tests use PostgreSQL if a `backend/.env` file exists or if `pg_isready` succeeds, otherwise they use in-memory SQLite. When PostgreSQL is used, tests run against a separate `sdf_test` database (auto-created if needed) so your development data is never affected.

### Frontend (Vitest)

```bash
cd ui
npx vitest run
```

Or run in watch mode during development:

```bash
cd ui
npx vitest
```

---

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

The Docker build is a single unified image published at [`smartassociates/sdf`](https://hub.docker.com/r/smartassociates/sdf) on Docker Hub. The image bundles the built React frontend + FastAPI backend, serving both on port 8000. There is **no Postgres container** — at startup the container tries to connect to PostgreSQL on the host, and if it can't reach one, it falls back to an in-container SQLite database (ephemeral, no volume).

```bash
docker compose pull      # fetch the published image (skip if you want to build locally)
docker compose up
```

Or, as a one-shot build + run from source (devs):
```bash
./start.sh docker        # or: docker compose up --build
```

Or, to build and run as two explicit steps (useful for faster iteration — you can rebuild without restarting the stack, and inspect the image before it runs):
```bash
docker build -t smartassociates/sdf:latest .   # tag matches the default in docker-compose.yml
docker compose up                              # picks up the local image, no rebuild
```

Since `pull_policy: missing` is set in the compose file, `docker compose up` will use the image you just built rather than trying to pull from Docker Hub.

Open [http://localhost:8000](http://localhost:8000). API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

To stop: `Ctrl+C`, then `docker compose down`.

### Option 2b: Plain `docker build` + `docker run`

If you'd rather not use Compose, the same workflow works with plain Docker commands.

**Build the image locally:**
```bash
docker build -t sdf:local .
```

The build runs both stages — a Node 20 stage that compiles the React UI to static assets, and a Python 3.11-slim runtime stage that installs backend deps and copies the build output into `/app/ui_dist`. The first build takes a few minutes; subsequent builds reuse layer cache and finish in seconds if only source changed.

Optional build args for labels / release metadata:
```bash
docker build \
  --build-arg SDF_VERSION=1.2.0 \
  --build-arg SDF_GIT_SHA="$(git rev-parse --short HEAD)" \
  -t sdf:local .
```

**Run the image:**
```bash
docker run --rm -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e ENCRYPTION_KEY="your-stable-32-char-secret-string" \
  sdf:local
```

Or run the published image without building anything:
```bash
docker run --rm -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e ENCRYPTION_KEY="your-stable-32-char-secret-string" \
  smartassociates/sdf:latest
```

Flags explained:
- `-p 8000:8000` — publish the app port.
- `--add-host=host.docker.internal:host-gateway` — **Linux only.** Lets the container reach the host's `localhost` so it can probe your host PostgreSQL. Docker Desktop (macOS/Windows) resolves `host.docker.internal` natively and ignores this flag.
- `-e ENCRYPTION_KEY=...` — stable secret used to encrypt stored DB passwords. Keep it constant across runs or previously-saved credentials become unreadable.

Pass any of the `POSTGRES_*` env vars (see table below) with additional `-e` flags to override detection.

To run detached with a healthcheck-visible name:
```bash
docker run -d --name sdf -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e ENCRYPTION_KEY="your-stable-32-char-secret-string" \
  smartassociates/sdf:latest

docker logs -f sdf      # watch startup (entrypoint logs which DB it picked)
docker stop sdf         # stop
```

### Pinning a version

The compose file uses `image: smartassociates/sdf:${SDF_IMAGE_TAG:-latest}`. Pin a release by setting the env var:

```bash
SDF_IMAGE_TAG=0.1.0 docker compose up
# or in a .env file: SDF_IMAGE_TAG=0.1.0
```

Each published release is also tagged by its git sha (e.g. `smartassociates/sdf:abc1234`), so you can pin to an exact commit.

### How the container finds PostgreSQL

By default the container probes `host.docker.internal:5432` as user `postgres` on database `sdf`. On Linux the compose file already wires `host.docker.internal` to the host gateway (`extra_hosts`), so no runtime flags are needed. On macOS/Windows Docker Desktop this resolves automatically.

Override any of the following via shell env or a `.env` file at the repo root:

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_HOST` | `host.docker.internal` | Hostname for the probe |
| `POSTGRES_PORT` | `5432` | Port for the probe |
| `POSTGRES_USER` | `postgres` | User for the probe |
| `POSTGRES_PASSWORD` | _(empty)_ | Password for the probe |
| `POSTGRES_DB` | `sdf` | Database name |
| `DATABASE_URL` | _(unset)_ | If set, skips auto-detection entirely |
| `ENCRYPTION_KEY` | placeholder | **Set this to a stable 32-char string in production** |

If probe fails, the container uses `sqlite:////tmp/sdf.db` — fine for evaluation, but data is lost when the container exits. For persistent usage, run a PostgreSQL on your host or pass `DATABASE_URL`.

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
- In Docker mode, use `host.docker.internal` (not `localhost`) to reach services running on the host. The compose file already wires this for Linux.

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

---

## Publishing a new release (maintainers only)

The Docker image is pushed to Docker Hub as multi-arch (`linux/amd64` + `linux/arm64`) via a local script. Prerequisites: `docker login` with push access to the `smartassociates` namespace, and `docker buildx` available (bundled with Docker Desktop; on plain Linux run `docker run --rm --privileged tonistiigi/binfmt --install all` once to enable cross-builds).

```bash
# Tag the current commit as :latest and :<git-sha>:
./scripts/publish.sh

# Additionally tag as a named version:
./scripts/publish.sh 1.2.0
```

The script builds, pushes, and tags in one shot. Verify with:

```bash
docker buildx imagetools inspect smartassociates/sdf:1.2.0
```

If the working tree is dirty, the git-sha tag gets a `-dirty` suffix — useful for diagnosing "what exactly did I push" but a signal to clean up before a real release.
