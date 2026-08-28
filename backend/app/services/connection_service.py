import asyncio
import os
import sqlalchemy as sa
from sqlalchemy.engine import URL
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import set_committed_value
from datetime import datetime, timezone
from app.models.connection import DatabaseConnection
from app.services.encryption import encrypt, decrypt, mask, is_masked, MASKED, DecryptionError
from app.services.clone_utils import next_copy_name

TEST_TIMEOUT = 15  # seconds — overall safety net for connection tests

DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306}
_DRIVERS = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
}


def _connect_timeout_args(db_type: str) -> dict:
    """Driver-specific connect timeout args (10s) so an unreachable host fails
    fast instead of hanging on driver defaults (psycopg2 ~120s, pymysql
    effectively infinite)."""
    if db_type in ("postgresql", "mysql"):
        return {"connect_timeout": 10}
    return {}


def get_jdbc_url(conn: DatabaseConnection, plaintext_password: str) -> str:
    if conn.db_type not in _DRIVERS:
        raise ValueError(f"Unknown db_type: {conn.db_type}")
    port = conn.port or DEFAULT_PORTS.get(conn.db_type, 5432)
    url = URL.create(_DRIVERS[conn.db_type], username=conn.username,
                     password=plaintext_password, host=conn.host,
                     port=port, database=conn.database)
    return str(url)


def build_engine(conn: DatabaseConnection, plaintext_password: str):
    if conn.db_type not in _DRIVERS:
        raise ValueError(f"Unknown db_type: {conn.db_type}")
    port = conn.port or DEFAULT_PORTS.get(conn.db_type, 5432)
    url = URL.create(_DRIVERS[conn.db_type], username=conn.username,
                     password=plaintext_password, host=conn.host,
                     port=port, database=conn.database)
    return sa.create_engine(url, pool_pre_ping=True, connect_args=_connect_timeout_args(conn.db_type))


async def list_connections(db: AsyncSession) -> list[DatabaseConnection]:
    result = await db.execute(select(DatabaseConnection).order_by(DatabaseConnection.id))
    conns = result.scalars().all()
    for c in conns:
        # Mask without dirtying the session — a plain assignment would be flushed
        # to the DB by autoflush on the next query in this request, overwriting
        # the stored ciphertext with the literal "********".
        set_committed_value(c, "password", MASKED)
    return list(conns)


async def get_connection(db: AsyncSession, conn_id: int) -> Optional[DatabaseConnection]:
    result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
    conn = result.scalar_one_or_none()
    if conn:
        set_committed_value(conn, "password", MASKED)
    return conn


async def get_connection_raw(db: AsyncSession, conn_id: int) -> Optional[DatabaseConnection]:
    result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
    return result.scalar_one_or_none()


async def create_connection(db: AsyncSession, data: dict) -> DatabaseConnection:
    data = data.copy()
    if data.get("password"):
        data["password"] = encrypt(data["password"])
    conn = DatabaseConnection(**data)
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    set_committed_value(conn, "password", MASKED)
    return conn


async def update_connection(db: AsyncSession, conn_id: int, data: dict) -> Optional[DatabaseConnection]:
    result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
    conn = result.scalar_one_or_none()
    if not conn:
        return None
    data = data.copy()
    incoming_pw = data.get("password")
    if incoming_pw and not is_masked(incoming_pw):
        data["password"] = encrypt(incoming_pw)
    elif is_masked(incoming_pw) or not incoming_pw:
        data.pop("password", None)  # keep existing
    for k, v in data.items():
        setattr(conn, k, v)
    conn.last_test_status = None
    conn.last_tested_at = None
    conn.last_test_error = None
    await db.commit()
    await db.refresh(conn)
    set_committed_value(conn, "password", MASKED)
    return conn


async def clone_connection(db: AsyncSession, conn_id: int) -> Optional[DatabaseConnection]:
    result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
    source = result.scalar_one_or_none()
    if not source:
        return None
    new_name = await next_copy_name(db, DatabaseConnection, source.name)
    clone = DatabaseConnection(
        name=new_name,
        db_type=source.db_type,
        host=source.host,
        port=source.port,
        database=source.database,
        username=source.username,
        password=source.password,
        staging_format=source.staging_format,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    set_committed_value(clone, "password", MASKED)
    return clone


async def delete_connection(db: AsyncSession, conn_id: int) -> bool:
    from app.models.job import Job, JobExecution
    # Check for running executions on jobs that use this connection
    running_result = await db.execute(
        select(JobExecution.id)
        .join(Job, JobExecution.job_id == Job.id)
        .where(
            (Job.source_connection_id == conn_id) | (Job.target_connection_id == conn_id),
            JobExecution.status == "running"
        )
    )
    if running_result.scalar_one_or_none():
        raise ValueError("Connection is used by a job that is currently running")
    jobs_result = await db.execute(
        select(Job).where(
            (Job.source_connection_id == conn_id) | (Job.target_connection_id == conn_id)
        )
    )
    if jobs_result.scalars().first():
        raise ValueError("Connection is referenced by one or more jobs")
    result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
    conn = result.scalar_one_or_none()
    if not conn:
        return False
    await db.delete(conn)
    await db.commit()
    return True


async def test_connection(db: AsyncSession, conn_id: int) -> dict:
    try:
        return await asyncio.wait_for(_test_connection_inner(db, conn_id), timeout=TEST_TIMEOUT)
    except asyncio.TimeoutError:
        result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
        conn = result.scalar_one_or_none()
        if not conn:
            raise ValueError("Connection not found")
        tested_at = datetime.now(timezone.utc).isoformat()
        error_msg = f"Connection test timed out after {TEST_TIMEOUT}s"
        conn.last_test_status = "failed"
        conn.last_tested_at = tested_at
        conn.last_test_error = error_msg
        await db.commit()
        return {"success": False, "message": "Connection failed", "tested_at": tested_at, "error": error_msg}


async def _test_connection_inner(db: AsyncSession, conn_id: int) -> dict:
    result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise ValueError("Connection not found")

    tested_at = datetime.now(timezone.utc).isoformat()

    if conn.db_type == "filesystem":
        directory = conn.database or ""
        try:
            os.makedirs(directory, exist_ok=True)
            if not os.access(directory, os.R_OK | os.W_OK):
                raise PermissionError(f"No read/write access to {directory}")
            conn.last_test_status = "success"
            conn.last_tested_at = tested_at
            conn.last_test_error = None
            await db.commit()
            return {"success": True, "message": "Directory accessible", "tested_at": tested_at}
        except Exception as e:
            error_msg = str(e)[:500]
            conn.last_test_status = "failed"
            conn.last_tested_at = tested_at
            conn.last_test_error = error_msg
            await db.commit()
            return {"success": False, "message": "Directory not accessible", "tested_at": tested_at, "error": error_msg}

    try:
        plaintext_pw = decrypt(conn.password) if conn.password else ""
    except DecryptionError as e:
        error_msg = str(e)
        conn.last_test_status = "failed"
        conn.last_tested_at = tested_at
        conn.last_test_error = error_msg
        await db.commit()
        return {"success": False, "message": "Connection failed", "tested_at": tested_at, "error": error_msg}
    port = conn.port or DEFAULT_PORTS.get(conn.db_type, 5432)
    url = URL.create(_DRIVERS[conn.db_type], username=conn.username,
                     password=plaintext_pw, host=conn.host,
                     port=port, database=conn.database)
    connect_args = _connect_timeout_args(conn.db_type)
    engine = sa.create_engine(url, connect_args=connect_args)

    def _probe():
        with engine.connect() as c:
            c.execute(sa.text("SELECT 1"))

    try:
        await asyncio.to_thread(_probe)
        conn.last_test_status = "success"
        conn.last_tested_at = tested_at
        conn.last_test_error = None
        await db.commit()
        return {"success": True, "message": "Connection successful", "tested_at": tested_at}
    except Exception as e:
        error_msg = str(e)[:500]
        conn.last_test_status = "failed"
        conn.last_tested_at = tested_at
        conn.last_test_error = error_msg
        await db.commit()
        return {"success": False, "message": "Connection failed", "tested_at": tested_at, "error": error_msg}
    finally:
        engine.dispose()
