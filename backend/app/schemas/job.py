from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class JobBase(BaseModel):
    name: str
    source_connection_id: int
    source_tables: Optional[str] = None
    table_filter: Optional[str] = None
    target_connection_id: int
    target_schema: Optional[str] = None
    create_target_table: bool = False
    migration_mode: str = "append"  # append|truncate_load

class JobCreate(JobBase):
    pass

class JobUpdate(JobBase):
    pass

class JobResponse(JobBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    running_execution_id: Optional[int] = None

    class Config:
        from_attributes = True

class JobValidationItem(BaseModel):
    table_name: str
    exists: bool
    message: str

class JobValidationResponse(BaseModel):
    valid: bool
    items: list[JobValidationItem]
    warnings: list[str]

class JobExecuteResponse(BaseModel):
    execution_id: int
    job_id: int
    status: str
    started_at: str
