from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class JobExecutionTableResponse(BaseModel):
    id: int
    execution_id: int
    table_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    record_count: int = 0
    estimated_row_count: Optional[int] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class JobExecutionResponse(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    record_count: int = 0
    error_message: Optional[str] = None
    tables: list[JobExecutionTableResponse] = []

    class Config:
        from_attributes = True

class ExecutionStatsResponse(BaseModel):
    total_runs: int
    success_count: int
    failed_count: int
    running_count: int
    total_records: int
    recent_executions: list[JobExecutionResponse] = []
