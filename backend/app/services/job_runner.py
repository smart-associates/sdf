"""Async job execution service."""
import json
import time
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
from app.services.job_objects import resolve_job_objects
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
_sync_pool_kwargs = {}
if "sqlite" not in settings.sync_database_url:
    _sync_pool_kwargs = dict(pool_size=10, max_overflow=20, pool_recycle=1800, pool_pre_ping=True)

_sync_engine = create_engine(settings.sync_database_url, **_sync_pool_kwargs)

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


_EXECUTION_COLUMNS = frozenset({
    "status", "completed_at", "record_count", "error_message",
})
_EXEC_TABLE_COLUMNS = frozenset({
    "status", "completed_at", "record_count", "error_message", "estimated_row_count",
})


def _update_execution_sync(execution_id: int, **kwargs):
    invalid = kwargs.keys() - _EXECUTION_COLUMNS
    if invalid:
        raise ValueError(f"Invalid columns for job_executions: {invalid}")
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
    invalid = kwargs.keys() - _EXEC_TABLE_COLUMNS
    if invalid:
        raise ValueError(f"Invalid columns for job_execution_tables: {invalid}")
    with _sync_engine.begin() as conn:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        conn.execute(
            text(f"UPDATE job_execution_tables SET {sets} WHERE id = :id"),
            {"id": exec_table_id, **kwargs}
        )


class ExecutionLogger:
    """Writes structured log entries to job_execution_logs."""

    def __init__(self, execution_id: int, log_level: str):
        self.execution_id = execution_id
        self.log_level = log_level
        self._last_detail_time: dict[int, float] = {}

    def info(self, event_type: str, message: str, exec_table_id: int = None, **meta):
        self._emit(exec_table_id, "info", event_type, message, meta)

    def detail(self, event_type: str, message: str, exec_table_id: int = None, **meta):
        if self.log_level != "detailed":
            return
        if event_type == "batch_inserted" and exec_table_id:
            now = time.monotonic()
            if now - self._last_detail_time.get(exec_table_id, 0) < 3:
                return
            self._last_detail_time[exec_table_id] = now
        self._emit(exec_table_id, "detail", event_type, message, meta)

    def error(self, event_type: str, message: str, exec_table_id: int = None, **meta):
        self._emit(exec_table_id, "error", event_type, message, meta)

    def _emit(self, exec_table_id, level, event_type, message, meta):
        try:
            with _sync_engine.begin() as conn:
                conn.execute(
                    text("""INSERT INTO job_execution_logs
                           (execution_id, exec_table_id, level, event_type, message, metadata, created_at)
                           VALUES (:eid, :etid, :level, :etype, :msg, :meta, :ts)"""),
                    {
                        "eid": self.execution_id,
                        "etid": exec_table_id,
                        "level": level,
                        "etype": event_type,
                        "msg": message,
                        "meta": json.dumps(meta) if meta else None,
                        "ts": _now_utc(),
                    },
                )
        except Exception:
            logger.debug("Failed to write execution log entry", exc_info=True)


def _load_job_sync(job_id: int) -> dict:
    with _sync_engine.connect() as conn:
        job = conn.execute(text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}).fetchone()
        src = conn.execute(text("SELECT * FROM database_connections WHERE id = :id"),
                           {"id": job.source_connection_id}).fetchone()
        tgt = conn.execute(text("SELECT * FROM database_connections WHERE id = :id"),
                           {"id": job.target_connection_id}).fetchone()
        table_rows = conn.execute(
            text("SELECT * FROM job_tables WHERE job_id = :id"), {"id": job_id}
        ).fetchall()
    return {
        "job": dict(job._mapping),
        "src": dict(src._mapping),
        "tgt": dict(tgt._mapping),
        "tables": [dict(r._mapping) for r in table_rows],
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

        def _delim_for(fmt: str) -> str:
            # TSV is CSV with a tab delimiter: default to a tab when the format
            # is tsv and the user left the global delimiter at its comma default.
            # An explicit non-comma delimiter still wins.
            if fmt == "tsv" and csv_delimiter == ",":
                return "\t"
            return csv_delimiter
        log_level = _get_setting_sync("log_level", "minimal").strip() or "minimal"

        elog = ExecutionLogger(execution_id, log_level)

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

        tables = resolve_job_objects(data.get("tables") or [])
        create_tgt = bool(job.get("create_target_table"))
        migration_mode = job.get("migration_mode") or "append"
        tgt_schema = job.get("target_schema") or None

        elog.detail("settings_loaded", f"Settings: batch_size={batch_size}, mode={migration_mode}",
                    batch_size=batch_size, migration_mode=migration_mode)
        elog.info("job_started", f"Job '{job.get('name', '')}' started ({len(tables)} table{'s' if len(tables) != 1 else ''})",
                  table_count=len(tables))

        total_records = 0
        any_failed = False
        stopped = False

        for obj in tables:
            if stop_event.is_set():
                stopped = True
                break
            table_entry = obj.entry
            table_filter = obj.table_filter   # per-object WHERE clause, or None
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
                    if src_fmt in ("csv", "tsv"):
                        estimated = get_csv_estimated_row_count(src_dir, src_table, ext=src_fmt)
                    elif src_fmt == "avro":
                        estimated = get_avro_estimated_row_count(src_dir, src_table)
                    else:
                        estimated = get_parquet_estimated_row_count(src_dir, src_table)
                else:
                    estimated = get_estimated_row_count(src_engine, src_table, src_schema)
            except Exception:
                estimated = None

            exec_table_id = _create_exec_table_sync(execution_id, table_entry, estimated)
            table_start_mono = time.monotonic()

            elog.info("table_started", f"{table_entry}: migration started",
                      exec_table_id=exec_table_id, source_schema=src_schema, migration_mode=migration_mode)
            if estimated is not None:
                elog.detail("row_estimate", f"{table_entry}: ~{estimated:,} estimated rows",
                            exec_table_id=exec_table_id, estimated=estimated)

            try:
                # Auto-create target table only applies to DB targets
                if create_tgt and not tgt_is_file:
                    if not table_exists(tgt_engine, tgt_table, tgt_schema):
                        create_target_table(src_engine, tgt_engine, src_table, tgt_table, src_schema, tgt_schema,
                                            elog=elog, exec_table_id=exec_table_id)
                        elog.info("table_created", f"{table_entry}: target table created",
                                  exec_table_id=exec_table_id)

                src_type = src["db_type"]
                tgt_type = tgt["db_type"]

                def progress_cb(n: int):
                    if stop_event.is_set():
                        raise _StopRequested()
                    _update_exec_table_sync(exec_table_id, record_count=n)
                    _update_execution_sync(execution_id, record_count=total_records + n)
                    elog.detail("batch_inserted", f"{table_entry}: {n:,} rows so far",
                                exec_table_id=exec_table_id, rows=n)

                if src_type == "filesystem" and tgt_type == "filesystem":
                    src_fmt = src.get("staging_format") or "parquet"
                    tgt_fmt = tgt.get("staging_format") or "parquet"
                    if src_fmt == tgt_fmt and src_fmt in ("csv", "tsv"):
                        count = migrate_csv_to_csv(src_dir, tgt_dir, src_table, tgt_table, migration_mode, progress_cb, csv_quoting=csv_quoting, csv_delimiter=_delim_for(src_fmt), include_header=csv_header, ext=src_fmt)
                    elif src_fmt == "parquet" and tgt_fmt == "parquet":
                        count = migrate_parquet_to_parquet(src_dir, tgt_dir, src_table, tgt_table, migration_mode, progress_cb)
                    elif src_fmt == "avro" and tgt_fmt == "avro":
                        count = migrate_avro_to_avro(src_dir, tgt_dir, src_table, tgt_table, migration_mode, progress_cb)
                    else:
                        raise ValueError(f"Cross-format filesystem copies ('{src_fmt}' → '{tgt_fmt}') are not supported")
                elif src_type == "filesystem":
                    src_fmt = src.get("staging_format") or "parquet"
                    if src_fmt in ("csv", "tsv"):
                        count = migrate_csv_to_db(src_dir, tgt_engine, src_table, tgt_table, tgt_schema, migration_mode, batch_size, progress_cb,
                                                  csv_delimiter=_delim_for(src_fmt), elog=elog, exec_table_id=exec_table_id, ext=src_fmt)
                    elif src_fmt == "avro":
                        count = migrate_avro_to_db(src_dir, tgt_engine, src_table, tgt_table, tgt_schema, migration_mode, batch_size, progress_cb,
                                                   elog=elog, exec_table_id=exec_table_id)
                    else:
                        count = migrate_parquet_to_db(src_dir, tgt_engine, src_table, tgt_table, tgt_schema, migration_mode, batch_size, progress_cb,
                                                      elog=elog, exec_table_id=exec_table_id)
                elif tgt_type == "filesystem":
                    tgt_fmt = tgt.get("staging_format") or "parquet"
                    if tgt_fmt in ("csv", "tsv"):
                        count = migrate_db_to_csv(src_engine, tgt_dir, src_table, tgt_table, src_schema, table_filter, migration_mode, progress_cb, batch_size, csv_quoting=csv_quoting, csv_delimiter=_delim_for(tgt_fmt), include_header=csv_header,
                                                  elog=elog, exec_table_id=exec_table_id, ext=tgt_fmt)
                    elif tgt_fmt == "avro":
                        count = migrate_db_to_avro(src_engine, tgt_dir, src_table, tgt_table, src_schema, table_filter, migration_mode, progress_cb,
                                                   elog=elog, exec_table_id=exec_table_id)
                    else:
                        count = migrate_db_to_parquet(src_engine, tgt_dir, src_table, tgt_table, src_schema, table_filter, migration_mode, progress_cb,
                                                      elog=elog, exec_table_id=exec_table_id)
                else:
                    count = migrate_table(
                        src_engine, tgt_engine,
                        src_table, tgt_table,
                        src_schema, tgt_schema,
                        table_filter, migration_mode, batch_size,
                        progress_cb,
                        elog=elog, exec_table_id=exec_table_id,
                    )

                total_records += count
                duration_ms = int((time.monotonic() - table_start_mono) * 1000)
                duration_s = duration_ms / 1000
                elog.info("table_completed",
                          f"{table_entry}: {count:,} rows in {duration_s:.1f}s",
                          exec_table_id=exec_table_id, rows=count, duration_ms=duration_ms)
                _update_exec_table_sync(
                    exec_table_id,
                    status="success",
                    completed_at=_now_utc(),
                    record_count=count
                )
            except _StopRequested:
                elog.info("table_cancelled", f"{table_entry}: cancelled by user",
                          exec_table_id=exec_table_id)
                _update_exec_table_sync(
                    exec_table_id,
                    status="cancelled",
                    completed_at=_now_utc(),
                )
                stopped = True
                break
            except Exception as e:
                logger.error(f"Table {table_entry} failed: {e}")
                elog.error("table_failed", f"{table_entry}: {str(e)[:500]}",
                           exec_table_id=exec_table_id, error=str(e)[:1000])
                _update_exec_table_sync(
                    exec_table_id,
                    status="failed",
                    completed_at=_now_utc(),
                    error_message=str(e)[:1000]
                )
                any_failed = True
                # Continue processing remaining tables instead of aborting

        tables_total = len(tables)

        if stopped:
            final_status = "cancelled"
            final_error = "Execution stopped by user"
            elog.info("job_cancelled", "Job cancelled by user")
        elif any_failed:
            final_status = "failed"
            final_error = "One or more tables failed — see table details"
            elog.error("job_failed", f"Job failed: see table details ({total_records:,} rows migrated)",
                       total_rows=total_records, tables_total=tables_total)
        else:
            final_status = "success"
            final_error = None
            elog.info("job_completed",
                      f"Job finished: {tables_total}/{tables_total} tables, {total_records:,} rows",
                      total_rows=total_records, tables_ok=tables_total, tables_total=tables_total)
        _update_execution_sync(
            execution_id,
            status=final_status,
            completed_at=_now_utc(),
            record_count=total_records,
            error_message=final_error
        )
    except Exception as e:
        logger.error(f"Job {job_id} execution {execution_id} failed: {e}")
        try:
            ExecutionLogger(execution_id, "minimal").error(
                "job_failed", f"Job failed: {str(e)[:500]}", error=str(e)[:1000])
        except Exception:
            pass
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
