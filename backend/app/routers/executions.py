from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.job import JobExecution, JobExecutionTable
from app.schemas.execution import JobExecutionResponse, JobExecutionTableResponse, ExecutionStatsResponse

router = APIRouter(prefix="/api/executions", tags=["executions"])

async def _load_execution(db: AsyncSession, exec_id: int) -> Optional[JobExecutionResponse]:
    result = await db.execute(select(JobExecution).where(JobExecution.id == exec_id))
    ex = result.scalar_one_or_none()
    if not ex:
        return None
    tables_result = await db.execute(
        select(JobExecutionTable)
        .where(JobExecutionTable.execution_id == exec_id)
        .order_by(JobExecutionTable.id)
    )
    tables = tables_result.scalars().all()
    resp = JobExecutionResponse.model_validate(ex)
    resp.tables = [JobExecutionTableResponse.model_validate(t) for t in tables]
    return resp

@router.get("/stats", response_model=ExecutionStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count()).select_from(JobExecution))).scalar()
    success = (await db.execute(select(func.count()).select_from(JobExecution).where(JobExecution.status == "success"))).scalar()
    failed = (await db.execute(select(func.count()).select_from(JobExecution).where(JobExecution.status == "failed"))).scalar()
    running = (await db.execute(select(func.count()).select_from(JobExecution).where(JobExecution.status == "running"))).scalar()
    total_recs = (await db.execute(select(func.coalesce(func.sum(JobExecution.record_count), 0)))).scalar()

    recent_result = await db.execute(
        select(JobExecution).order_by(JobExecution.id.desc()).limit(10)
    )
    recent_execs = recent_result.scalars().all()
    recent = []
    for ex in recent_execs:
        r = await _load_execution(db, ex.id)
        if r:
            recent.append(r)

    return ExecutionStatsResponse(
        total_runs=total or 0,
        success_count=success or 0,
        failed_count=failed or 0,
        running_count=running or 0,
        total_records=total_recs or 0,
        recent_executions=recent
    )

@router.get("/{exec_id}", response_model=JobExecutionResponse)
async def get_execution(exec_id: int, db: AsyncSession = Depends(get_db)):
    ex = await _load_execution(db, exec_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return ex

@router.get("", response_model=list[JobExecutionResponse])
async def list_executions(
    job_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
):
    q = select(JobExecution).order_by(JobExecution.id.desc()).limit(limit).offset(offset)
    if job_id:
        q = q.where(JobExecution.job_id == job_id)
    result = await db.execute(q)
    execs = result.scalars().all()
    out = []
    for ex in execs:
        r = await _load_execution(db, ex.id)
        if r:
            out.append(r)
    return out
