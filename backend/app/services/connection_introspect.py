"""Read-only schema/object listing for the Job form's table/view picker.

Lets the picker offer a "Browse…" panel backed by the connection's actual
catalog instead of free-typed names. Returns exact names only — no
glob/pattern support, matching the job_tables model.
"""
import asyncio
import os
from typing import Optional

from sqlalchemy import inspect

from app.models.connection import DatabaseConnection
from app.services.connection_service import build_engine
from app.services.encryption import decrypt

INTROSPECT_TIMEOUT = 15  # seconds — mirrors connection_service.TEST_TIMEOUT

NON_RELATIONAL_TYPES = {"filesystem"}

# Legacy polars_* staging formats map to their base extension.
_EXT_ALIASES = {"polars_avro": "avro", "polars_parquet": "parquet"}


class IntrospectError(Exception):
    """Raised when introspection cannot be performed (e.g. wrong connection type)."""


def _open_engine(conn: DatabaseConnection):
    if conn.db_type in NON_RELATIONAL_TYPES:
        raise IntrospectError(f"Cannot list tables/views on a {conn.db_type} connection")
    plaintext_pw = decrypt(conn.password) if conn.password else ""
    return build_engine(conn, plaintext_pw)


def get_schema_names(engine) -> list[str]:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        return sorted(inspect(conn).get_schema_names() or [])


def get_object_names(engine, schema: Optional[str] = None) -> list[dict]:
    """Return ``[{"name", "schema", "kind"}, ...]`` for tables and views."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        insp = inspect(conn)
        tables = insp.get_table_names(schema=schema) or []
        try:
            views = insp.get_view_names(schema=schema) or []
        except NotImplementedError:
            views = []
    out = [{"name": n, "schema": schema, "kind": "table"} for n in tables]
    out += [{"name": n, "schema": schema, "kind": "view"} for n in views]
    out.sort(key=lambda o: o["name"].lower())
    return out


def _list_schemas_sync(conn: DatabaseConnection) -> list[str]:
    engine = _open_engine(conn)
    try:
        return get_schema_names(engine)
    finally:
        engine.dispose()


def _list_objects_sync(conn: DatabaseConnection, schema: Optional[str]) -> list[dict]:
    engine = _open_engine(conn)
    try:
        return get_object_names(engine, schema=schema)
    finally:
        engine.dispose()


def _staging_ext(fmt: Optional[str]) -> str:
    f = (fmt or "parquet").strip()
    return _EXT_ALIASES.get(f, f)


def _list_files_sync(conn: DatabaseConnection) -> list[dict]:
    if conn.db_type != "filesystem":
        raise IntrospectError(f"Cannot browse files on a {conn.db_type} connection")
    directory = conn.database or ""
    if not directory or not os.path.isdir(directory):
        raise IntrospectError(f"Directory not found: {directory or '(unset)'}")

    ext = _staging_ext(conn.staging_format)
    # CSV/TSV may be stored gzip-compressed (<table>.csv.gz); accept both,
    # matching migration_engine.csv_table_exists.
    suffixes = [f".{ext}"]
    if ext in ("csv", "tsv"):
        suffixes.append(f".{ext}.gz")

    files = []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if not entry.is_file():
                    continue
                matched = next((s for s in suffixes if entry.name.endswith(s)), None)
                if not matched:
                    continue
                files.append({"name": entry.name, "table": entry.name[: -len(matched)]})
    except OSError as e:
        raise IntrospectError(f"Could not read directory: {str(e)[:200]}")

    files.sort(key=lambda f: f["table"].lower())
    return files


async def list_schemas(conn: DatabaseConnection) -> list[str]:
    return await asyncio.wait_for(asyncio.to_thread(_list_schemas_sync, conn), timeout=INTROSPECT_TIMEOUT)


async def list_objects(conn: DatabaseConnection, schema: Optional[str] = None) -> list[dict]:
    return await asyncio.wait_for(asyncio.to_thread(_list_objects_sync, conn, schema), timeout=INTROSPECT_TIMEOUT)


async def list_files(conn: DatabaseConnection) -> list[dict]:
    return await asyncio.wait_for(asyncio.to_thread(_list_files_sync, conn), timeout=INTROSPECT_TIMEOUT)
