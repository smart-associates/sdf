"""Async job execution service."""
import asyncio
import threading
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.models.job import Job, JobExecution, JobExecutionTable
from app.models.connection import DatabaseConnection
from app.models.setting import Setting
from app.services.encryption import decrypt
from app.services.migration_engine import build_engine, create_target_table, migrate_table, table_exists

logger = logging.getLogger(__name__)

_engine = create_async_engine(settings.database_url)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

def _get_setting_sync(session_factory, key: str, default: str) -> str:
    """Sync helper to read setting from DB in thread."""
    import sqlalchemy as sa
    from sqlalchemy import create_engine
    sync_engine = create_engine(settings.sync_database_url)
    with sync_engine.connect() as conn:
        from app.models.setting import Setting as SettingModel
        result = conn.execute(
            sa.text("SELECT value FROM settings WHERE key = :key"), {"key": key}
        )
        row = result.fetchone()
        sync_engine.dispose()
        return row[0] if row and row[0] is not None else default

def _update_execution_sync(execution_id: int, **kwargs):
    import sqlalchemy as sa
    from sqlalchemy import create_engine
    sync_engine = create_engine(settings.sync_database_url)
    with sync_engine.begin() as conn:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        conn.execute(
            sa.text(f"UPDATE job_executions SET {sets} WHERE id = :id"),
            {"id": execution_id, **kwargs}
        )
    sync_engine.dispose()

def _create_exec_table_sync(execution_id: int, table_name: str) -> int:
    import sqlalchemy as sa
    from sqlalchemy import create_engine
    sync_engine = create_engine(settings.sync_database_url)
    started_at = datetime.now(timezone.utc).isoformat()
    with sync_engine.begin() as conn:
        result = conn.execute(
            sa.text("""INSERT INTO job_execution_tables
                       (execution_id, table_name, status, started_at, record_count)
                       VALUES (:eid, :tn, 'running', :sa, 0)
                       RETURNING id"""),
            {"eid": execution_id, "tn": table_name, "sa": started_at}
        )
        row = result.fetchone()
    sync_engine.dispose()
    return row[0] if row else None

def _update_exec_table_sync(exec_table_id: int, **kwargs):
    import sqlalchemy as sa
    from sqlalchemy import create_engine
    sync_engine = create_engine(settings.sync_database_url)
    with sync_engine.begin() as conn:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        conn.execute(
            sa.text(f"UPDATE job_execution_tables SET {sets} WHERE id = :id"),
            {"id": exec_table_id, **kwargs}
        )
    sync_engine.dispose()

def _load_job_sync(job_id: int) -> dict:
    import sqlalchemy as sa
    from sqlalchemy import create_engine
    sync_engine = create_engine(settings.sync_database_url)
    with sync_engine.connect() as conn:
        job = conn.execute(sa.text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}).fetchone()
        src = conn.execute(sa.text("SELECT * FROM database_connections WHERE id = :id"),
                          {"id": job.source_connection_id}).fetchone()
        tgt = conn.execute(sa.text("SELECT * FROM database_connections WHERE id = :id"),
                          {"id": job.target_connection_id}).fetchone()
    sync_engine.dispose()
    return {
        "job": dict(job._mapping),
        "src": dict(src._mapping),
        "tgt": dict(tgt._mapping),
    }

def _run_job_thread(job_id: int, execution_id: int):
    """Runs in a background thread (not async) since DB drivers are blocking."""
    try:
        data = _load_job_sync(job_id)
        job = data["job"]
        src = data["src"]
        tgt = data["tgt"]

        batch_size = int(_get_setting_sync(None, "batch_size", "1000"))

        src_engine = build_engine(
            src["db_type"], src["host"], src["port"], src["database"],
            src["username"], decrypt(src["password"] or "")
        )
        tgt_engine = build_engine(
            tgt["db_type"], tgt["host"], tgt["port"], tgt["database"],
            tgt["username"], decrypt(tgt["password"] or "")
        )

        tables_raw = job.get("source_tables") or ""
        tables = [t.strip() for t in tables_raw.splitlines() if t.strip()]
        table_filter = job.get("table_filter") or None
        create_tgt = bool(job.get("create_target_table"))
        migration_mode = job.get("migration_mode") or "append"
        tgt_schema = job.get("target_schema") or None

        total_records = 0

        for table_entry in tables:
            # Parse schema.table or just table
            if "." in table_entry:
                src_schema, src_table = table_entry.split(".", 1)
            else:
                src_schema = None
                src_table = table_entry

            tgt_table = src_table  # same table name on target
            exec_table_id = _create_exec_table_sync(execution_id, table_entry)

            try:
                if create_tgt and not table_exists(tgt_engine, tgt_table, tgt_schema):
                    create_target_table(src_engine, tgt_engine, src_table, tgt_table, src_schema, tgt_schema)

                count = migrate_table(
                    src_engine, tgt_engine,
                    src_table, tgt_table,
                    src_schema, tgt_schema,
                    table_filter, migration_mode, batch_size
                )
                total_records += count
                _update_exec_table_sync(
                    exec_table_id,
                    status="success",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    record_count=count
                )
            except Exception as e:
                logger.error(f"Table {table_entry} failed: {e}")
                _update_exec_table_sync(
                    exec_table_id,
                    status="failed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    error_message=str(e)[:1000]
                )
                src_engine.dispose()
                tgt_engine.dispose()
                _update_execution_sync(
                    execution_id,
                    status="failed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    record_count=total_records,
                    error_message=f"Failed on table {table_entry}: {str(e)[:500]}"
                )
                return

        src_engine.dispose()
        tgt_engine.dispose()
        _update_execution_sync(
            execution_id,
            status="success",
            completed_at=datetime.now(timezone.utc).isoformat(),
            record_count=total_records
        )
    except Exception as e:
        logger.error(f"Job {job_id} execution {execution_id} failed: {e}")
        _update_execution_sync(
            execution_id,
            status="failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=str(e)[:1000]
        )

async def start_job_execution(db: AsyncSession, job_id: int) -> JobExecution:
    """Create execution record and start background thread."""
    started_at = datetime.now(timezone.utc).isoformat()
    execution = JobExecution(
        job_id=job_id,
        status="running",
        started_at=started_at,
        record_count=0
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    thread = threading.Thread(
        target=_run_job_thread,
        args=(job_id, execution.id),
        daemon=True
    )
    thread.start()
    return execution
