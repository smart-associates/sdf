"""Async job execution service."""
import threading
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, text

from app.core.config import settings
from app.models.job import Job, JobExecution, JobExecutionTable
from app.models.connection import DatabaseConnection
from app.models.setting import Setting
from app.services.encryption import decrypt
from app.services.migration_engine import (
    build_engine, create_target_table, migrate_table, table_exists,
    csv_table_exists, migrate_csv_to_db, migrate_db_to_csv, migrate_csv_to_csv,
    parquet_table_exists, migrate_parquet_to_db, migrate_db_to_parquet, migrate_parquet_to_parquet,
    avro_table_exists, migrate_avro_to_db, migrate_db_to_avro, migrate_avro_to_avro,
    get_estimated_row_count, get_csv_estimated_row_count, get_parquet_estimated_row_count,
    get_avro_estimated_row_count,
)

logger = logging.getLogger(__name__)


class _StopRequested(Exception):
    """Raised inside progress_cb to abort a migration mid-batch."""


# Module-level sync engine shared across all background threads
_sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
    pool_pre_ping=True,
)

# Registry of stop events keyed by execution_id
_stop_events: dict = {}
_active_threads: dict[int, threading.Thread] = {}
_stop_events_lock = threading.Lock()


def stop_execution(execution_id: int) -> bool:
    """Signal a running execution to stop. Returns True if the signal was sent."""
    with _stop_events_lock:
        event = _stop_events.get(execution_id)
    if event:
        event.set()
        return True
    return False


def shutdown_all(timeout: float = 30) -> None:
    """Signal all running executions to stop and wait for threads to finish.

    Called during application shutdown so that non-daemon threads can complete
    gracefully instead of being killed mid-migration.
    """
    with _stop_events_lock:
        events = list(_stop_events.values())
        threads = list(_active_threads.values())
    if not threads:
        return
    logger.info("Shutting down %d running execution(s)…", len(threads))
    for event in events:
        event.set()
    for thread in threads:
        thread.join(timeout=timeout)
    still_alive = [t for t in threads if t.is_alive()]
    if still_alive:
        logger.warning("%d thread(s) did not finish within %ds", len(still_alive), timeout)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_setting_sync(key: str, default: str) -> str:
    with _sync_engine.connect() as conn:
        result = conn.execute(text("SELECT value FROM settings WHERE key = :key"), {"key": key})
        row = result.fetchone()
        return row[0] if row and row[0] is not None else default


def _update_execution_sync(execution_id: int, **kwargs):
    with _sync_engine.begin() as conn:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        conn.execute(
            text(f"UPDATE job_executions SET {sets} WHERE id = :id"),
            {"id": execution_id, **kwargs}
        )


def _create_exec_table_sync(execution_id: int, table_name: str, estimated_row_count=None) -> int:
    with _sync_engine.begin() as conn:
        result = conn.execute(
            text("""INSERT INTO job_execution_tables
                   (execution_id, table_name, status, started_at, record_count, estimated_row_count)
                   VALUES (:eid, :tn, 'running', :sa, 0, :erc)
                   RETURNING id"""),
            {"eid": execution_id, "tn": table_name, "sa": _now_utc(), "erc": estimated_row_count}
        )
        row = result.fetchone()
    return row[0] if row else None


def _update_exec_table_sync(exec_table_id: int, **kwargs):
    with _sync_engine.begin() as conn:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        conn.execute(
            text(f"UPDATE job_execution_tables SET {sets} WHERE id = :id"),
            {"id": exec_table_id, **kwargs}
        )


def _load_job_sync(job_id: int) -> dict:
    with _sync_engine.connect() as conn:
        job = conn.execute(text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}).fetchone()
        src = conn.execute(text("SELECT * FROM database_connections WHERE id = :id"),
                           {"id": job.source_connection_id}).fetchone()
        tgt = conn.execute(text("SELECT * FROM database_connections WHERE id = :id"),
                           {"id": job.target_connection_id}).fetchone()
    return {
        "job": dict(job._mapping),
        "src": dict(src._mapping),
        "tgt": dict(tgt._mapping),
    }


def _run_job_thread(job_id: int, execution_id: int, stop_event: threading.Event):
    """Runs in a background thread (not async) since DB drivers are blocking."""
    src_engine = None
    tgt_engine = None
    try:
        data = _load_job_sync(job_id)
        job = data["job"]
        src = data["src"]
        tgt = data["tgt"]

        batch_size = int(_get_setting_sync("batch_size", "1000"))
        csv_quoting = _get_setting_sync("csv_quoting", "none").strip() or "none"
        csv_delimiter = _get_setting_sync("csv_delimiter", ",").strip() or ","
        csv_header = _get_setting_sync("csv_header", "true").strip() not in ("0", "false", "False")

        src_is_file = src["db_type"] == "filesystem"
        tgt_is_file = tgt["db_type"] == "filesystem"
        src_dir = src["database"] if src_is_file else None
        tgt_dir = tgt["database"] if tgt_is_file else None

        src_engine = None if src_is_file else build_engine(
            src["db_type"], src["host"], src["port"], src["database"],
            src["username"], decrypt(src["password"] or "")
        )
        tgt_engine = None if tgt_is_file else build_engine(
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
        any_failed = False
        stopped = False

        for table_entry in tables:
            if stop_event.is_set():
                stopped = True
                break
            # Parse schema.table or just table
            if "." in table_entry:
                src_schema, src_table = table_entry.split(".", 1)
            else:
                src_schema = None
                src_table = table_entry

            tgt_table = src_table  # same table name on target

            # Gather estimated row count from source statistics (best-effort)
            try:
                if src_is_file:
                    src_fmt = src.get("staging_format") or "parquet"
                    if src_fmt == "csv":
                        estimated = get_csv_estimated_row_count(src_dir, src_table)
                    elif src_fmt == "avro":
                        estimated = get_avro_estimated_row_count(src_dir, src_table)
                    else:
                        estimated = get_parquet_estimated_row_count(src_dir, src_table)
                else:
                    estimated = get_estimated_row_count(src_engine, src_table, src_schema)
            except Exception:
                estimated = None

            exec_table_id = _create_exec_table_sync(execution_id, table_entry, estimated)

            try:
                # Auto-create target table only applies to DB targets
                if create_tgt and not tgt_is_file:
                    if not table_exists(tgt_engine, tgt_table, tgt_schema):
                        create_target_table(src_engine, tgt_engine, src_table, tgt_table, src_schema, tgt_schema)

                src_type = src["db_type"]
                tgt_type = tgt["db_type"]

                def progress_cb(n: int):
                    if stop_event.is_set():
                        raise _StopRequested()
                    _update_exec_table_sync(exec_table_id, record_count=n)
                    _update_execution_sync(execution_id, record_count=total_records + n)

                if src_type == "filesystem" and tgt_type == "filesystem":
                    src_fmt = src.get("staging_format") or "parquet"
                    tgt_fmt = tgt.get("staging_format") or "parquet"
                    if src_fmt == "csv" and tgt_fmt == "csv":
                        count = migrate_csv_to_csv(src_dir, tgt_dir, src_table, tgt_table, migration_mode, progress_cb, csv_quoting=csv_quoting, csv_delimiter=csv_delimiter, include_header=csv_header)
                    elif src_fmt == "parquet" and tgt_fmt == "parquet":
                        count = migrate_parquet_to_parquet(src_dir, tgt_dir, src_table, tgt_table, migration_mode, progress_cb)
                    elif src_fmt == "avro" and tgt_fmt == "avro":
                        count = migrate_avro_to_avro(src_dir, tgt_dir, src_table, tgt_table, migration_mode, progress_cb)
                    else:
                        raise ValueError(f"Cross-format filesystem copies ('{src_fmt}' → '{tgt_fmt}') are not supported")
                elif src_type == "filesystem":
                    src_fmt = src.get("staging_format") or "parquet"
                    if src_fmt == "csv":
                        count = migrate_csv_to_db(src_dir, tgt_engine, src_table, tgt_table, tgt_schema, migration_mode, batch_size, progress_cb)
                    elif src_fmt == "avro":
                        count = migrate_avro_to_db(src_dir, tgt_engine, src_table, tgt_table, tgt_schema, migration_mode, batch_size, progress_cb)
                    else:
                        count = migrate_parquet_to_db(src_dir, tgt_engine, src_table, tgt_table, tgt_schema, migration_mode, batch_size, progress_cb)
                elif tgt_type == "filesystem":
                    tgt_fmt = tgt.get("staging_format") or "parquet"
                    if tgt_fmt == "csv":
                        count = migrate_db_to_csv(src_engine, tgt_dir, src_table, tgt_table, src_schema, table_filter, migration_mode, progress_cb, batch_size, csv_quoting=csv_quoting, csv_delimiter=csv_delimiter, include_header=csv_header)
                    elif tgt_fmt == "avro":
                        count = migrate_db_to_avro(src_engine, tgt_dir, src_table, tgt_table, src_schema, table_filter, migration_mode, progress_cb)
                    else:
                        count = migrate_db_to_parquet(src_engine, tgt_dir, src_table, tgt_table, src_schema, table_filter, migration_mode, progress_cb)
                else:
                    count = migrate_table(
                        src_engine, tgt_engine,
                        src_table, tgt_table,
                        src_schema, tgt_schema,
                        table_filter, migration_mode, batch_size,
                        progress_cb
                    )

                total_records += count
                _update_exec_table_sync(
                    exec_table_id,
                    status="success",
                    completed_at=_now_utc(),
                    record_count=count
                )
            except _StopRequested:
                _update_exec_table_sync(
                    exec_table_id,
                    status="cancelled",
                    completed_at=_now_utc(),
                )
                stopped = True
                break
            except Exception as e:
                logger.error(f"Table {table_entry} failed: {e}")
                _update_exec_table_sync(
                    exec_table_id,
                    status="failed",
                    completed_at=_now_utc(),
                    error_message=str(e)[:1000]
                )
                any_failed = True
                # Continue processing remaining tables instead of aborting

        if stopped:
            final_status = "cancelled"
            final_error = "Execution stopped by user"
        elif any_failed:
            final_status = "failed"
            final_error = "One or more tables failed — see table details"
        else:
            final_status = "success"
            final_error = None
        _update_execution_sync(
            execution_id,
            status=final_status,
            completed_at=_now_utc(),
            record_count=total_records,
            error_message=final_error
        )
    except Exception as e:
        logger.error(f"Job {job_id} execution {execution_id} failed: {e}")
        _update_execution_sync(
            execution_id,
            status="failed",
            completed_at=_now_utc(),
            error_message=str(e)[:1000]
        )
    finally:
        if src_engine is not None:
            src_engine.dispose()
        if tgt_engine is not None:
            tgt_engine.dispose()
        with _stop_events_lock:
            _stop_events.pop(execution_id, None)
            _active_threads.pop(execution_id, None)


async def start_job_execution(db: AsyncSession, job_id: int) -> JobExecution:
    """Create execution record and start background thread."""
    execution = JobExecution(
        job_id=job_id,
        status="running",
        started_at=_now_utc(),
        record_count=0
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    stop_event = threading.Event()
    with _stop_events_lock:
        _stop_events[execution.id] = stop_event

    thread = threading.Thread(
        target=_run_job_thread,
        args=(job_id, execution.id, stop_event),
        daemon=False
    )
    with _stop_events_lock:
        _active_threads[execution.id] = thread
    thread.start()
    return execution
