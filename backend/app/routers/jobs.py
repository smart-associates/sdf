import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.job import Job, JobTable, JobExecution, JobExecutionTable, JobExecutionLog
from app.models.connection import DatabaseConnection
from app.schemas.job import (
    JobCreate, JobUpdate, JobResponse, JobValidationResponse, JobValidationItem, JobExecuteResponse,
    JobTableItem, ConnectionRef, JobExportItem, JobExportDocument, JobImportResult, JobImportFailure,
)
from app.services.job_runner import start_job_execution, stop_execution
from app.services.encryption import decrypt
from app.services.migration_engine import build_engine, table_exists, csv_table_exists, parquet_table_exists, avro_table_exists
from app.services.clone_utils import next_copy_name
from app.services.job_objects import resolve_job_objects, qualify_rows, entry_of
from app.services.connection_introspect import get_schema_names, get_object_names

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _validate_connections(data):
    if data.source_connection_id == data.target_connection_id:
        raise HTTPException(400, "Source and target connections must be different")


def _build_job_tables(items) -> list[JobTable]:
    """Materialize JobTable rows from JobTableItem schema entries, preserving order."""
    rows = []
    for i, t in enumerate(items):
        rows.append(JobTable(
            schema_name=t.schema_name or None,
            object_name=t.object_name,
            table_filter=t.table_filter or None,
            enabled=t.enabled,
            position=t.position if t.position else i,
        ))
    return rows


def _job_table_rows(job) -> list[dict]:
    """A job's ORM job_tables rows as plain dicts."""
    return [{
        "schema_name": t.schema_name,
        "object_name": t.object_name,
        "table_filter": t.table_filter,
        "enabled": t.enabled,
        "position": t.position,
    } for t in job.tables]


def _resolve_job_tables(job) -> list:
    """Resolve a job's ORM job_tables rows into ordered ResolvedObjects."""
    return resolve_job_objects(_job_table_rows(job))


# ---- export / import --------------------------------------------------------

_JOB_CONNECTION_FIELDS = (
    ("source_connection_id", "source_connection"),
    ("target_connection_id", "target_connection"),
)


def _connection_ref(conn: DatabaseConnection) -> ConnectionRef:
    # name+db_type only — a connection's full metadata is now its own portable
    # export/import document; a job document just points at it.
    return ConnectionRef(name=conn.name, db_type=conn.db_type)


async def _load_connections(db: AsyncSession, ids: set) -> dict:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id.in_(ids)))
    return {c.id: c for c in result.scalars().all()}


async def _export_item(db: AsyncSession, job: Job) -> JobExportItem:
    conn_map = await _load_connections(db, {job.source_connection_id, job.target_connection_id})
    payload = {
        "name": job.name,
        "target_schema": job.target_schema,
        "create_target_table": job.create_target_table,
        "migration_mode": job.migration_mode,
        "tables": [JobTableItem.model_validate(t) for t in job.tables],
    }
    for id_field, ref_field in _JOB_CONNECTION_FIELDS:
        conn_id = getattr(job, id_field)
        payload[ref_field] = _connection_ref(conn_map[conn_id]) if conn_id in conn_map else None
    return JobExportItem(**payload)


async def _resolve_connection_ref(db: AsyncSession, ref: Optional[ConnectionRef]):
    """Resolve a ConnectionRef to a local connection id by (name, db_type).

    Never auto-creates: an unresolved or ambiguous name is reported back to
    the caller, not guessed at. Returns (id_or_None, problem_or_None).
    """
    if ref is None:
        return None, None
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.name == ref.name,
            DatabaseConnection.db_type == ref.db_type,
        )
    )
    matches = result.scalars().all()
    if not matches:
        return None, f"connection '{ref.name}' ({ref.db_type}) not found"
    if len(matches) > 1:
        return None, f"connection '{ref.name}' ({ref.db_type}) is ambiguous ({len(matches)} matches on this instance)"
    return matches[0].id, None


async def _find_job_by_name(db: AsyncSession, name: str):
    result = await db.execute(select(Job).where(Job.name == name))
    matches = result.scalars().all()
    if len(matches) > 1:
        return None, f"job name '{name}' is ambiguous ({len(matches)} matches on this instance)"
    return (matches[0] if matches else None), None


@router.get("", response_model=list[JobResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    jobs = (await db.execute(select(Job).order_by(Job.id))).scalars().all()
    running = (await db.execute(
        select(JobExecution.job_id, JobExecution.id)
        .where(JobExecution.status == "running")
    )).all()
    running_map = {row[0]: row[1] for row in running}
    out = []
    for j in jobs:
        r = JobResponse.model_validate(j)
        r.running_execution_id = running_map.get(j.id)
        out.append(r)
    return out


@router.get("/export", response_model=JobExportDocument)
async def export_all_jobs(db: AsyncSession = Depends(get_db)):
    """Registered before GET /{job_id} — otherwise FastAPI would try to parse
    'export' as a job_id and 404 rather than reaching this handler."""
    jobs = (await db.execute(select(Job).order_by(Job.id))).scalars().all()
    items = [await _export_item(db, j) for j in jobs]
    return JobExportDocument(exported_at=datetime.now(timezone.utc), jobs=items)


@router.get("/{job_id}/export", response_model=JobExportDocument)
async def export_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    item = await _export_item(db, job)
    return JobExportDocument(exported_at=datetime.now(timezone.utc), jobs=[item])


@router.post("/import", response_model=JobImportResult)
async def import_jobs(doc: JobExportDocument, db: AsyncSession = Depends(get_db)):
    """Import a job export document.

    Two phases: resolve everything first and fail the whole request if any
    connection name or job name can't be resolved unambiguously (nothing is
    written); then apply job-by-job by calling create_job/update_job directly
    so import gets every validation those endpoints already enforce, for
    free. Each job commits independently in phase two — a failure there is
    reported per-job rather than rolling back earlier jobs.
    """
    if doc.format_version != 1:
        raise HTTPException(400, f"Unsupported export format_version {doc.format_version}")

    problems: list = []
    plan: list = []
    for item in doc.jobs:
        resolved = {}
        for id_field, ref_field in _JOB_CONNECTION_FIELDS:
            ref = getattr(item, ref_field)
            conn_id, problem = await _resolve_connection_ref(db, ref)
            if problem:
                problems.append(f"job '{item.name}': {problem}")
            resolved[id_field] = conn_id
        existing, ambiguous = await _find_job_by_name(db, item.name)
        if ambiguous:
            problems.append(ambiguous)
        plan.append((item, existing, resolved))

    if problems:
        raise HTTPException(400, "; ".join(problems))

    result = JobImportResult()
    for item, existing, resolved in plan:
        payload = item.model_dump(exclude={"source_connection", "target_connection"})
        payload.update(resolved)
        try:
            if existing is None:
                await create_job(JobCreate(**payload), db)
                result.created.append(item.name)
            else:
                await update_job(existing.id, JobUpdate(**payload), db)
                result.updated.append(item.name)
        except HTTPException as e:
            result.failed.append(JobImportFailure(name=item.name, error=str(e.detail)))

    return result


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(data: JobCreate, db: AsyncSession = Depends(get_db)):
    _validate_connections(data)
    for conn_id in [data.source_connection_id, data.target_connection_id]:
        r = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
        if not r.scalar_one_or_none():
            raise HTTPException(400, f"Connection {conn_id} not found")
    payload = data.model_dump()
    table_items = data.tables
    payload.pop("tables", None)
    job = Job(**payload)
    job.tables = _build_job_tables(table_items)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: int, data: JobUpdate, db: AsyncSession = Depends(get_db)):
    _validate_connections(data)
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    update = data.model_dump(exclude_unset=True)
    tables_given = "tables" in update
    update.pop("tables", None)
    for k, v in update.items():
        setattr(job, k, v)
    if tables_given:
        # Replace the selection wholesale (delete-orphan cascade removes old rows).
        job.tables = _build_job_tables(data.tables)
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    # Block deletion while a job is actively running
    running = await db.execute(
        select(JobExecution.id).where(
            JobExecution.job_id == job_id,
            JobExecution.status == "running"
        )
    )
    if running.scalar_one_or_none():
        raise HTTPException(409, "Cannot delete job while it is running")
    # Delete child execution records to avoid orphaned rows
    exec_ids_result = await db.execute(
        select(JobExecution.id).where(JobExecution.job_id == job_id)
    )
    exec_ids = [r[0] for r in exec_ids_result.all()]
    if exec_ids:
        await db.execute(sa.delete(JobExecutionLog).where(JobExecutionLog.execution_id.in_(exec_ids)))
        await db.execute(sa.delete(JobExecutionTable).where(JobExecutionTable.execution_id.in_(exec_ids)))
        await db.execute(sa.delete(JobExecution).where(JobExecution.job_id == job_id))
    await db.delete(job)
    await db.commit()


@router.post("/{job_id}/validate", response_model=JobValidationResponse)
async def validate_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    src_result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == job.source_connection_id))
    src = src_result.scalar_one_or_none()
    if not src:
        raise HTTPException(400, "Source connection not found")

    items = []
    warnings = []
    valid = True

    rows = _job_table_rows(job)
    resolved = resolve_job_objects(rows)
    tables = [o.entry for o in resolved]
    if not tables:
        warnings.append("No source tables defined")

    def _validate_source_tables():
        """Blocking: connect to source and check table existence."""
        _items = []
        _valid = True
        _quals: list = []
        if src.db_type == "filesystem":
            fmt = src.staging_format or "parquet"
            if fmt in ("csv", "tsv"):
                check_fn = lambda d, t, _ext=fmt: csv_table_exists(d, t, ext=_ext)
            elif fmt == "avro":
                check_fn = avro_table_exists
            else:
                check_fn = parquet_table_exists
            for obj in resolved:
                # Files are named by a single "<schema>.<table>" stem (e.g.
                # title.ratings.tsv), so fold schema back in rather than
                # splitting obj.entry — a dotted filename with no schema would
                # otherwise be mis-split into a fake schema/table pair.
                file_stem = f"{obj.schema}.{obj.name}" if obj.schema else obj.name
                exists = check_fn(src.database or "", file_stem)
                _items.append(JobValidationItem(
                    table_name=obj.entry,
                    exists=exists,
                    message=f"{fmt.upper()} file found" if exists else f"{fmt.upper()} file not found: {file_stem}.{fmt}"
                ))
                if not exists:
                    _valid = False
        else:
            src_pw = decrypt(src.password or "")
            src_engine = build_engine(src.db_type, src.host, src.port, src.database, src.username, src_pw)
            try:
                # Qualify bare/mis-cased manual entries against the full source
                # catalog, and use the result for the existence checks below so
                # e.g. a bare name that only exists in a non-default schema
                # reads as found, not "not found".
                try:
                    _quals = qualify_rows(
                        rows,
                        list_schemas=lambda: get_schema_names(src_engine),
                        list_objects=lambda s: get_object_names(src_engine, s),
                    )
                except Exception as exc:
                    logger.debug("qualify_rows failed: %s", exc)
                    _quals = []
                _qmap = {q["original"].lower(): q for q in _quals}
                eff_rows = []
                for r in rows:
                    entry = entry_of(r.get("schema_name"), (r.get("object_name") or "").strip())
                    q = _qmap.get(entry.lower())
                    eff_rows.append({**r, "schema_name": q["schema_name"], "object_name": q["object_name"]} if q else r)
                eff_resolved = resolve_job_objects(eff_rows)
                for obj in eff_resolved:
                    exists = table_exists(src_engine, obj.name, obj.schema)
                    _items.append(JobValidationItem(
                        table_name=obj.entry,
                        exists=exists,
                        message="Table found" if exists else "Table not found on source"
                    ))
                    if not exists:
                        _valid = False
            finally:
                src_engine.dispose()
        return _items, _valid, _quals

    qualified: list = []
    try:
        src_items, src_valid, qualified = await asyncio.to_thread(_validate_source_tables)
        items.extend(src_items)
        if not src_valid:
            valid = False
    except Exception as e:
        warnings.append(f"Could not connect to source: {str(e)}")
        valid = False

    # Check target connection and tables
    tgt_result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == job.target_connection_id))
    tgt = tgt_result.scalar_one_or_none()
    if not tgt:
        warnings.append("Target connection not found")
        valid = False
    elif not job.create_target_table:
        def _validate_target():
            """Blocking: connect to target and check table existence."""
            _warnings = []
            _valid = True
            if tgt.db_type == "filesystem":
                tgt_dir = tgt.database or ""
                if not os.path.isdir(tgt_dir):
                    _warnings.append(f"Target filesystem directory '{tgt_dir}' does not exist (it will be created on execution)")
            else:
                tgt_pw = decrypt(tgt.password or "")
                tgt_engine = build_engine(tgt.db_type, tgt.host, tgt.port, tgt.database, tgt.username, tgt_pw)
                try:
                    # Target table name always mirrors the source object's own
                    # name (job_runner's tgt_table == src_table convention) —
                    # not a split of the display entry, which would mangle a
                    # dotted filesystem stem into a fake schema/table pair.
                    # zip(resolved, items) also preserves the existing
                    # skip-if-source-validation-failed behavior (items is []
                    # in that case).
                    for obj, _item in zip(resolved, items):
                        table = obj.name
                        tgt_schema = job.target_schema
                        if not table_exists(tgt_engine, table, tgt_schema):
                            _warnings.append(f"Target table '{table}' does not exist (enable 'create target table' to auto-create)")
                            _valid = False  # missing target table blocks execution
                finally:
                    tgt_engine.dispose()
            return _warnings, _valid

        try:
            tgt_warnings, tgt_valid = await asyncio.to_thread(_validate_target)
            warnings.extend(tgt_warnings)
            if not tgt_valid:
                valid = False
        except Exception as e:
            warnings.append(f"Could not connect to target: {str(e)}")
            valid = False

    return JobValidationResponse(valid=valid, items=items, warnings=warnings, qualified=qualified)


@router.post("/{job_id}/execute", response_model=JobExecuteResponse, status_code=202)
async def execute_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    tables = [o.entry for o in _resolve_job_tables(job)]
    if not tables:
        raise HTTPException(400, "Job has no source tables defined")

    try:
        execution = await start_job_execution(db, job_id)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Job is already running")
    return JobExecuteResponse(
        execution_id=execution.id,
        job_id=job_id,
        status=execution.status,
        started_at=execution.started_at
    )


@router.post("/{job_id}/clone", response_model=JobResponse, status_code=201)
async def clone_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Job not found")
    new_name = await next_copy_name(db, Job, source.name)
    clone = Job(
        name=new_name,
        source_connection_id=source.source_connection_id,
        target_connection_id=source.target_connection_id,
        target_schema=source.target_schema,
        create_target_table=source.create_target_table,
        migration_mode=source.migration_mode,
    )
    clone.tables = [
        JobTable(
            schema_name=t.schema_name,
            object_name=t.object_name,
            table_filter=t.table_filter,
            enabled=t.enabled,
            position=t.position,
        ) for t in source.tables
    ]
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


@router.post("/{job_id}/executions/{execution_id}/stop", status_code=200)
async def stop_job_execution(job_id: int, execution_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JobExecution).where(
            JobExecution.id == execution_id,
            JobExecution.job_id == job_id,
            JobExecution.status == "running"
        )
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Running execution not found")
    signalled = stop_execution(execution_id)
    if not signalled:
        raise HTTPException(409, "Execution has already finished")
    return {"detail": "Stop signal sent"}
