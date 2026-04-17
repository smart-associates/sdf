#!/usr/bin/env python3
"""Resolve DATABASE_URL at container start, then exec uvicorn.

Order of precedence:
  1. If DATABASE_URL is already set, honor it (and derive SYNC_DATABASE_URL if absent).
  2. Else probe Postgres at $POSTGRES_HOST:$POSTGRES_PORT with $POSTGRES_USER/$POSTGRES_DB.
  3. Else fall back to SQLite at /tmp/sdf.db (ephemeral — no volume).
"""
import os
import socket
import sys
from urllib.parse import quote_plus


SQLITE_ASYNC = "sqlite+aiosqlite:////tmp/sdf.db"
SQLITE_SYNC = "sqlite:////tmp/sdf.db"


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


def resolve_database_urls() -> None:
    if os.environ.get("DATABASE_URL"):
        log("DATABASE_URL set, skipping detection")
        if not os.environ.get("SYNC_DATABASE_URL"):
            # Derive a plausible sync URL from the async one so background threads work.
            async_url = os.environ["DATABASE_URL"]
            sync_url = (
                async_url
                .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
                .replace("sqlite+aiosqlite://", "sqlite://")
            )
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

    os.environ["DATABASE_URL"] = SQLITE_ASYNC
    os.environ["SYNC_DATABASE_URL"] = SQLITE_SYNC
    log("Postgres unreachable — falling back to SQLite at /tmp/sdf.db (ephemeral)")


def main() -> None:
    resolve_database_urls()
    args = sys.argv[1:] or [
        "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
    ]
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()
