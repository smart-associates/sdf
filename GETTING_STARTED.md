# Getting Started

## Prerequisites

### Docker (recommended path)
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose

### Local dev path
- Python 3.9+
- Node.js 18+ and npm
- PostgreSQL 14+ (optional — SQLite is used automatically if PostgreSQL is not running)

---

## Option 1: Docker Compose

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

### Restart policy

The `sdf` service is configured with `restart: unless-stopped`, so Docker will bring the container back automatically after a host reboot or daemon restart. The only things that keep it stopped are an explicit `docker compose down` / `docker compose stop`, or repeated startup failures. Detached mode (`docker compose up -d`) plus this policy means the container survives terminal logout, SSH disconnect, and host reboot.

### Logs

The `sdf` service is configured with Docker's `local` log driver and rotation (`max-size: 10m`, `max-file: 5`) — container logs are capped at ~50 MB per container lifetime, which matters when running detached (`docker compose up -d`) over long periods. Tail with:

```bash
docker compose logs -f sdf
```

### Option 1b: Plain `docker build` + `docker run`

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
docker run --rm --network=host \
  -e ENCRYPTION_KEY="your-stable-32-char-secret-string" \
  sdf:local
```

Or run the published image without building anything:
```bash
docker run --rm --network=host \
  -e ENCRYPTION_KEY="your-stable-32-char-secret-string" \
  smartassociates/sdf:latest
```

Flags explained:
- `--network=host` — share the host's network namespace. Port 8000 is bound directly on the host (no `-p` needed) and the container can reach a host PostgreSQL on `127.0.0.1`. On Docker Desktop (macOS/Windows) this requires enabling host networking in **Settings → Resources → Network**.
- `-e ENCRYPTION_KEY=...` — stable secret used to encrypt stored DB passwords. Keep it constant across runs or previously-saved credentials become unreadable.

Pass any of the `POSTGRES_*` env vars (see table below) with additional `-e` flags to override detection, e.g. `-e POSTGRES_USER=shaneel -e POSTGRES_PASSWORD=...`.

To run detached with a healthcheck-visible name:
```bash
docker run -d --name sdf --network=host \
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

The compose file sets `network_mode: host`, so the container shares the host's network namespace. That means `127.0.0.1` inside the container is the host's loopback — the same interface a local Postgres is almost always bound to. No `extra_hosts`, no NAT layer, no `-p` flag.

On Docker Desktop (macOS/Windows), host networking is available but opt-in: **Settings → Resources → Network → Enable host networking**. On plain Linux it works out of the box.

By default the container probes `127.0.0.1:5432` as user `postgres` on database `sdf`. Override any of the following via shell env or a `.env` file at the repo root:

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_HOST` | `127.0.0.1` | Hostname for the probe |
| `POSTGRES_PORT` | `5432` | Port for the probe |
| `POSTGRES_USER` | `postgres` | User for the probe |
| `POSTGRES_PASSWORD` | _(empty)_ | Password for the probe |
| `POSTGRES_DB` | `sdf` | Database name |
| `DATABASE_URL` | _(unset)_ | If set, skips auto-detection entirely |
| `ENCRYPTION_KEY` | placeholder | **Set this to a stable 32-char string in production** |

The probe requires TCP access and an auth method the container can satisfy. Most distro Postgres setups ship with `pg_hba.conf` requiring `md5`/`scram-sha-256` for loopback TCP — set `POSTGRES_PASSWORD` accordingly. For a single-user dev laptop you can swap those lines for `trust` and skip the password:
```
# /var/lib/pgsql/data/pg_hba.conf
host  all  all  127.0.0.1/32  trust
host  all  all  ::1/128       trust
```
Then `sudo systemctl reload postgresql`.

If probe fails, the container uses `sqlite:////tmp/sdf.db` — fine for evaluation, but data is lost when the container exits. For persistent usage, fix the PG path above or pass `DATABASE_URL`.

### A note on `network_mode: host`

With host networking the container binds port 8000 directly on the host (no `-p 8000:8000` needed or honored). That means:

- The app is reachable on every interface the host has — loopback, LAN, public. Same practical reachability as a published port, but the host's firewall is the only gate (no docker iptables NAT rules).
- If anything else on the host already owns `:8000`, the container fails to start.
- You can't pin to a specific interface via compose; uvicorn binds `0.0.0.0`. For localhost-only, put a firewall rule in front.

---

## Option 2: Local Development (recommended)

### a. Start everything

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

### b. (Optional) Use PostgreSQL

If you want to use PostgreSQL, make sure it's running and create the database:

```bash
psql -U postgres -c "CREATE DATABASE sdf;"
```

Then restart with `./start.sh dev` — it will detect PostgreSQL automatically.

### c. (Optional) Override database settings

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
- **Source Tables** — add one or more tables/views to replicate. Either type a
  name directly (e.g. `public.orders`), or click **Browse…** to pick from the
  source's actual schemas and tables (or, for a filesystem source, its files).
  There's no wildcard/pattern matching — every entry is one exact object. Each
  table has its own optional **Filter** (a WHERE clause, e.g.
  `created_at > '2024-01-01'`) and can be temporarily disabled without removing
  it.
- **Target Connection** — where data goes
- **Target Schema** — schema to write into on the target (leave blank to use default)
- **Create Target Table** — auto-create a target table if it doesn't exist yet,
  including its primary key, non-PK indexes, CHECK constraints, and (once every
  table in the job has loaded) foreign keys
- **Migration Mode** — `append` to add rows, `truncate_load` to replace all data

Click **Validate** to check that the saved job's source tables exist and the
configuration is valid — it's disabled while the form has unsaved changes,
since it checks the saved job, not what's currently in the form.

### 3. Run the job

From the **Jobs** page, click **Run** next to a job. The button changes to **Stop** while it runs.

Click a job row to see per-table progress, estimated row counts, and status.

### 4. View history

**Logs** shows all past executions with status, duration, record counts, and error messages.

**Dashboard** shows aggregate stats: total runs, success/failure rates, records migrated, and charts of recent activity.

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

## Settings

Navigate to **Settings** to configure system-wide defaults. The following settings are seeded automatically on first startup:

| Key | Default | Description |
|-----|---------|-------------|
| `maximum_batch_size` | `100000` | Upper bound on rows per batch. The actual batch size is chosen per table as ~1% of its estimated row count (floored at 1,000), so small tables use small batches and large tables ramp up to this ceiling. |
| `csv_quoting` | `none` | Quote character for CSV export: `none` (backslash-escape instead), `single`, or `double`. |
| `csv_delimiter` | `,` | Field delimiter for CSV output. Use escape sequences for control characters, e.g. `\t` (tab) or `\001` (SOH). |
| `csv_null_value` | _(empty)_ | Sentinel string written for NULL fields in CSV output, and recognized as NULL when reading CSV back in. Leave blank for empty-string NULLs. |
| `csv_header` | `true` | Include column headers in CSV export. |
| `log_level` | `minimal` | Logging verbosity for job executions: `minimal` (key events only) or `detailed` (includes batch progress). |

You can add additional custom settings via the Settings page or the `/api/settings` API endpoint.

---

## Troubleshooting

**Backend won't start — database connection error**
- If using PostgreSQL, make sure it's running (`pg_isready`) and the `sdf` database exists.
- If no `.env` is present, `start.sh` auto-detects: PostgreSQL if running, otherwise SQLite.
- The app creates tables automatically on startup; no manual migrations needed.

**"Connection refused" when testing a connection**
- Verify host/port are reachable from the machine running the backend.
- In Docker mode the container uses host networking, so `127.0.0.1` inside the container is the host's loopback. If a remote DB is still unreachable, check your `pg_hba.conf` auth rules and whether the firewall allows port 8000/5432 as needed.

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

Before publishing, regenerate the third-party licence notices so they match the dependencies actually being shipped:

```bash
./scripts/gen-third-party-notices.sh
git diff THIRD_PARTY_NOTICES.txt   # review, then commit if it changed
```

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
