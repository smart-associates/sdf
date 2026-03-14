from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.job import Job
from app.models.connection import DatabaseConnection
from app.schemas.job import JobCreate, JobUpdate, JobResponse, JobValidationResponse, JobValidationItem, JobExecuteResponse
from app.services.job_runner import start_job_execution
from app.services.encryption import decrypt
from app.services.migration_engine import build_engine, table_exists, get_table_names

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

@router.get("", response_model=list[JobResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).order_by(Job.id))
    return result.scalars().all()

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job

@router.post("", response_model=JobResponse, status_code=201)
async def create_job(data: JobCreate, db: AsyncSession = Depends(get_db)):
    # Validate connections exist
    for conn_id in [data.source_connection_id, data.target_connection_id]:
        r = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == conn_id))
        if not r.scalar_one_or_none():
            raise HTTPException(400, f"Connection {conn_id} not found")
    job = Job(**data.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: int, data: JobUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(job, k, v)
    await db.commit()
    await db.refresh(job)
    return job

@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await db.delete(job)
    await db.commit()

@router.post("/{job_id}/validate", response_model=JobValidationResponse)
async def validate_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    # Load source connection
    src_result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == job.source_connection_id))
    src = src_result.scalar_one_or_none()
    if not src:
        raise HTTPException(400, "Source connection not found")

    items = []
    warnings = []
    valid = True

    try:
        src_pw = decrypt(src.password or "")
        src_engine = build_engine(src.db_type, src.host, src.port, src.database, src.username, src_pw)

        tables = [t.strip() for t in (job.source_tables or "").splitlines() if t.strip()]
        if not tables:
            warnings.append("No source tables defined")

        for entry in tables:
            if "." in entry:
                schema, table = entry.split(".", 1)
            else:
                schema, table = None, entry

            exists = table_exists(src_engine, table, schema)
            items.append(JobValidationItem(
                table_name=entry,
                exists=exists,
                message="Table found" if exists else "Table not found"
            ))
            if not exists:
                valid = False

        src_engine.dispose()
    except Exception as e:
        warnings.append(f"Could not connect to source: {str(e)}")
        valid = False

    # Check target connection exists
    tgt_result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.id == job.target_connection_id))
    tgt = tgt_result.scalar_one_or_none()
    if not tgt:
        warnings.append("Target connection not found")
        valid = False
    elif not job.create_target_table:
        try:
            tgt_pw = decrypt(tgt.password or "")
            tgt_engine = build_engine(tgt.db_type, tgt.host, tgt.port, tgt.database, tgt.username, tgt_pw)
            for item in items:
                entry = item.table_name
                table = entry.split(".", 1)[1] if "." in entry else entry
                tgt_schema = job.target_schema
                if not table_exists(tgt_engine, table, tgt_schema):
                    warnings.append(f"Target table '{table}' does not exist (enable 'create target table' to auto-create)")
            tgt_engine.dispose()
        except Exception as e:
            warnings.append(f"Could not connect to target: {str(e)}")

    return JobValidationResponse(valid=valid, items=items, warnings=warnings)

@router.post("/{job_id}/execute", response_model=JobExecuteResponse, status_code=202)
async def execute_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    execution = await start_job_execution(db, job_id)
    return JobExecuteResponse(
        execution_id=execution.id,
        job_id=job_id,
        status=execution.status,
        started_at=execution.started_at
    )
