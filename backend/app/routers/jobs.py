import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.job import Job, JobTable, JobExecution, JobExecutionTable, JobExecutionLog
from app.models.connection import DatabaseConnection
from app.schemas.job import JobCreate, JobUpdate, JobResponse, JobValidationResponse, JobValidationItem, JobExecuteResponse
from app.services.job_runner import start_job_execution, stop_execution
from app.services.encryption import decrypt
from app.services.migration_engine import build_engine, table_exists, csv_table_exists, parquet_table_exists, avro_table_exists
from app.services.clone_utils import next_copy_name
from app.services.job_objects import resolve_job_objects

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


def _resolve_job_tables(job) -> list:
    """Resolve a job's ORM job_tables rows into ordered ResolvedObjects."""
    rows = [{
        "schema_name": t.schema_name,
        "object_name": t.object_name,
        "table_filter": t.table_filter,
        "enabled": t.enabled,
        "position": t.position,
    } for t in job.tables]
    return resolve_job_objects(rows)


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

    resolved = _resolve_job_tables(job)
    tables = [o.entry for o in resolved]
    if not tables:
        warnings.append("No source tables defined")

    def _validate_source_tables():
        """Blocking: connect to source and check table existence."""
        _items = []
        _valid = True
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
                for obj in resolved:
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
        return _items, _valid

    try:
        src_items, src_valid = await asyncio.to_thread(_validate_source_tables)
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

    return JobValidationResponse(valid=valid, items=items, warnings=warnings)


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
