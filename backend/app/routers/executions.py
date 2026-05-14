from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from app.database import get_db
from app.models.job import JobExecution, JobExecutionTable, JobExecutionLog
from app.schemas.execution import JobExecutionResponse, JobExecutionTableResponse, ExecutionStatsResponse, LogEntryResponse, RecordsTimelinePoint

router = APIRouter(prefix="/api/executions", tags=["executions"])


async def _batch_load_tables(db: AsyncSession, exec_ids: list[int]) -> dict[int, list[JobExecutionTableResponse]]:
    """Load execution tables for multiple executions in a single query."""
    if not exec_ids:
        return {}
    result = await db.execute(
        select(JobExecutionTable)
        .where(JobExecutionTable.execution_id.in_(exec_ids))
        .order_by(JobExecutionTable.execution_id, JobExecutionTable.id)
    )
    tables_by_exec: dict[int, list[JobExecutionTableResponse]] = defaultdict(list)
    for t in result.scalars().all():
        tables_by_exec[t.execution_id].append(JobExecutionTableResponse.model_validate(t))
    return tables_by_exec


def _build_responses(execs: list, tables_by_exec: dict[int, list[JobExecutionTableResponse]]) -> list[JobExecutionResponse]:
    out = []
    for ex in execs:
        resp = JobExecutionResponse.model_validate(ex)
        resp.tables = tables_by_exec.get(ex.id, [])
        out.append(resp)
    return out


async def _load_execution(db: AsyncSession, exec_id: int) -> Optional[JobExecutionResponse]:
    result = await db.execute(select(JobExecution).where(JobExecution.id == exec_id))
    ex = result.scalar_one_or_none()
    if not ex:
        return None
    tables_map = await _batch_load_tables(db, [exec_id])
    resp = JobExecutionResponse.model_validate(ex)
    resp.tables = tables_map.get(exec_id, [])
    return resp


@router.get("/stats", response_model=ExecutionStatsResponse)
async def get_stats(
    days: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    stats_q = select(
        func.count().label("total"),
        func.count().filter(JobExecution.status == "success").label("success"),
        func.count().filter(JobExecution.status == "failed").label("failed"),
        func.count().filter(JobExecution.status == "running").label("running"),
        func.count().filter(JobExecution.status == "cancelled").label("cancelled"),
        func.coalesce(func.sum(JobExecution.record_count), 0).label("total_recs"),
    ).select_from(JobExecution)
    if cutoff is not None:
        stats_q = stats_q.where(JobExecution.started_at >= cutoff)
    stats = (await db.execute(stats_q)).one()

    recent_q = select(JobExecution).order_by(JobExecution.id.desc()).limit(10)
    if cutoff is not None:
        recent_q = recent_q.where(JobExecution.started_at >= cutoff)
    recent_execs = (await db.execute(recent_q)).scalars().all()
    exec_ids = [ex.id for ex in recent_execs]
    tables_map = await _batch_load_tables(db, exec_ids)

    timeline = await _build_records_timeline(db, days, cutoff)

    return ExecutionStatsResponse(
        total_runs=stats.total or 0,
        success_count=stats.success or 0,
        failed_count=stats.failed or 0,
        running_count=stats.running or 0,
        cancelled_count=stats.cancelled or 0,
        total_records=stats.total_recs or 0,
        recent_executions=_build_responses(recent_execs, tables_map),
        records_timeline=timeline,
    )


async def _build_records_timeline(
    db: AsyncSession,
    days: Optional[int],
    cutoff: Optional[datetime],
) -> list[RecordsTimelinePoint]:
    tl_q = select(
        JobExecution.id,
        JobExecution.started_at,
        JobExecution.status,
        JobExecution.record_count,
    ).where(JobExecution.status.in_(["success", "failed", "cancelled"]))
    if cutoff is not None:
        tl_q = tl_q.where(JobExecution.started_at >= cutoff)
    tl_q = tl_q.order_by(JobExecution.started_at.asc())
    rows = (await db.execute(tl_q)).all()

    return [
        RecordsTimelinePoint(
            id=row.id,
            started_at=row.started_at,
            status=row.status,
            record_count=row.record_count or 0,
        )
        for row in rows
    ]


@router.get("/{exec_id}/logs", response_model=list[LogEntryResponse])
async def get_execution_logs(
    exec_id: int,
    level: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(JobExecutionLog).where(JobExecutionLog.execution_id == exec_id)
    if level == "info":
        q = q.where(JobExecutionLog.level.in_(["info", "error"]))
    q = q.order_by(JobExecutionLog.id.asc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{exec_id}", response_model=JobExecutionResponse)
async def get_execution(exec_id: int, db: AsyncSession = Depends(get_db)):
    ex = await _load_execution(db, exec_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return ex


@router.get("", response_model=list[JobExecutionResponse])
async def list_executions(
    job_id: Optional[int] = Query(None),
    days: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
):
    q = select(JobExecution).order_by(JobExecution.id.desc()).limit(limit).offset(offset)
    if job_id:
        q = q.where(JobExecution.job_id == job_id)
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        q = q.where(JobExecution.started_at >= cutoff)
    if status:
        q = q.where(JobExecution.status == status)
    result = await db.execute(q)
    execs = result.scalars().all()
    exec_ids = [ex.id for ex in execs]
    tables_map = await _batch_load_tables(db, exec_ids)
    return _build_responses(execs, tables_map)
