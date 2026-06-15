#!/usr/bin/env python3
"""Resolve DATABASE_URL at container start, then exec uvicorn.

Order of precedence:
  1. If DATABASE_URL is already set, honor it (and derive SYNC_DATABASE_URL if absent).
  2. Else probe Postgres at $POSTGRES_HOST:$POSTGRES_PORT with $POSTGRES_USER/$POSTGRES_DB.
  3. Else spin up a bundled embedded Postgres on a unix socket (ephemeral — no
     volume). The app's schema is Postgres-only (JSONB, SERIAL, TIMESTAMPTZ,
     partial indexes), so this fallback runs real Postgres rather than SQLite.
"""
import glob
import os
import pwd
import socket
import subprocess
import sys
from urllib.parse import quote_plus


# Ephemeral embedded-Postgres fallback (no volume — wiped on container restart).
EMBEDDED_PGDATA = os.environ.get("SDF_EMBEDDED_PGDATA", "/tmp/pgdata")
EMBEDDED_PGSOCKET_DIR = os.environ.get("SDF_EMBEDDED_PGSOCKET_DIR", "/tmp")
EMBEDDED_PGPORT = int(os.environ.get("SDF_EMBEDDED_PGPORT", "5432"))
EMBEDDED_PGLOG = os.environ.get("SDF_EMBEDDED_PGLOG", "/tmp/embedded-pg.log")


def log(msg: str) -> None:
    print(f"[entrypoint] {msg}", flush=True)


def tcp_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def pg_auth_ok(host: str, port: int, user: str, password: str, dbname: str, timeout: float) -> bool:
    try:
        import psycopg2
    except ImportError:
        log("psycopg2 not available — cannot probe Postgres")
        return False
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password or None,
            dbname=dbname, connect_timeout=int(max(1, timeout)),
        )
        conn.close()
        return True
    except Exception as exc:
        log(f"Postgres auth probe failed: {exc}")
        return False


def build_pg_urls(host: str, port: int, user: str, password: str, dbname: str) -> tuple[str, str]:
    auth = quote_plus(user)
    if password:
        auth = f"{auth}:{quote_plus(password)}"
    base = f"{auth}@{host}:{port}/{dbname}"
    return (
        f"postgresql+asyncpg://{base}",
        f"postgresql+psycopg2://{base}",
    )


def find_pg_bindir() -> str | None:
    """Locate the Debian PostgreSQL server binaries (initdb/pg_ctl/createdb).

    Debian installs them under /usr/lib/postgresql/<major>/bin, not on PATH.
    Pick the highest version present.
    """
    candidates = sorted(
        glob.glob("/usr/lib/postgresql/*/bin"),
        key=lambda p: int(p.split("/")[3]) if p.split("/")[3].isdigit() else 0,
        reverse=True,
    )
    for d in candidates:
        if os.path.exists(os.path.join(d, "initdb")):
            return d
    return None


def start_embedded_postgres() -> tuple[str, str] | None:
    """Boot an ephemeral bundled Postgres on a local unix socket.

    Returns (async_url, sync_url) on success, or None if the server binaries
    aren't bundled in the image.
    """
    bindir = find_pg_bindir()
    if not bindir:
        log("embedded Postgres binaries not found under /usr/lib/postgresql/*/bin")
        return None

    initdb = os.path.join(bindir, "initdb")
    pg_ctl = os.path.join(bindir, "pg_ctl")
    createdb = os.path.join(bindir, "createdb")

    # initdb's superuser role defaults to the OS user running it (uid 10001 = "sdf").
    user = pwd.getpwuid(os.getuid()).pw_name or "sdf"
    dbname = os.environ.get("POSTGRES_DB", "sdf")

    if not os.path.exists(os.path.join(EMBEDDED_PGDATA, "PG_VERSION")):
        os.makedirs(EMBEDDED_PGDATA, exist_ok=True)
        os.chmod(EMBEDDED_PGDATA, 0o700)  # postgres refuses a group/world-readable datadir
        log(f"initialising embedded Postgres cluster at {EMBEDDED_PGDATA}")
        subprocess.run(
            [initdb, "-D", EMBEDDED_PGDATA, "-U", user,
             "-A", "trust", "--encoding=UTF8", "--locale=C"],
            check=True, stdout=subprocess.DEVNULL,
        )

    # listen_addresses='' → unix socket only (no TCP, no port conflicts). -w waits
    # for readiness. The postmaster keeps running after this process execs uvicorn.
    log(f"starting embedded Postgres on socket {EMBEDDED_PGSOCKET_DIR}/.s.PGSQL.{EMBEDDED_PGPORT}")
    subprocess.run(
        [pg_ctl, "-D", EMBEDDED_PGDATA, "-w", "-l", EMBEDDED_PGLOG, "-o",
         f"-p {EMBEDDED_PGPORT} -k {EMBEDDED_PGSOCKET_DIR} -c listen_addresses=''",
         "start"],
        check=True,
    )

    # Create the application database if it doesn't already exist (idempotent).
    exists = subprocess.run(
        [os.path.join(bindir, "psql"), "-h", EMBEDDED_PGSOCKET_DIR,
         "-p", str(EMBEDDED_PGPORT), "-U", user, "-d", "postgres",
         "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{dbname}'"],
        capture_output=True, text=True,
    )
    if exists.stdout.strip() != "1":
        subprocess.run(
            [createdb, "-h", EMBEDDED_PGSOCKET_DIR, "-p", str(EMBEDDED_PGPORT),
             "-U", user, dbname],
            check=True,
        )
        log(f"created embedded database {dbname!r}")

    # asyncpg/psycopg2 over a unix socket: host is the socket *directory*.
    base = f"{quote_plus(user)}@:{EMBEDDED_PGPORT}/{dbname}?host={quote_plus(EMBEDDED_PGSOCKET_DIR)}"
    return (
        f"postgresql+asyncpg://{base}",
        f"postgresql+psycopg2://{base}",
    )


def resolve_database_urls() -> None:
    if os.environ.get("DATABASE_URL"):
        log("DATABASE_URL set, skipping detection")
        if not os.environ.get("SYNC_DATABASE_URL"):
            # Derive a plausible sync URL from the async one so background threads work.
            async_url = os.environ["DATABASE_URL"]
            sync_url = async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            os.environ["SYNC_DATABASE_URL"] = sync_url
        return

    host = os.environ.get("POSTGRES_HOST", "host.docker.internal")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    dbname = os.environ.get("POSTGRES_DB", "sdf")
    timeout = float(os.environ.get("SDF_PG_PROBE_TIMEOUT", "2"))

    log(f"Probing Postgres at {host}:{port} as user={user!r} db={dbname!r}")
    if tcp_reachable(host, port, timeout) and pg_auth_ok(host, port, user, password, dbname, timeout):
        async_url, sync_url = build_pg_urls(host, port, user, password, dbname)
        os.environ["DATABASE_URL"] = async_url
        os.environ["SYNC_DATABASE_URL"] = sync_url
        log(f"Postgres detected at {host}:{port} — using PostgreSQL backend")
        return

    log("external Postgres unreachable — starting bundled embedded Postgres (ephemeral)")
    urls = start_embedded_postgres()
    if urls is None:
        log("FATAL: no external Postgres and embedded Postgres unavailable; cannot start")
        sys.exit(1)
    os.environ["DATABASE_URL"], os.environ["SYNC_DATABASE_URL"] = urls
    log("embedded Postgres ready — using PostgreSQL backend")


def main() -> None:
    resolve_database_urls()
    args = sys.argv[1:] or [
        "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
    ]
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()
