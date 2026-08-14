from pydantic import BaseModel, validator
from typing import List, Literal, Optional
from datetime import datetime


class JobTableItem(BaseModel):
    """One source-object selection (a row in job_tables)."""
    schema_name: Optional[str] = None
    object_name: str
    table_filter: Optional[str] = None       # per-object WHERE clause
    enabled: bool = True
    position: int = 0

    class Config:
        from_attributes = True

    @validator("object_name")
    def object_name_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("object_name must not be blank")
        return v.strip()


class JobBase(BaseModel):
    name: str
    source_connection_id: int
    tables: List[JobTableItem] = []          # source-object selection (job_tables rows)
    target_connection_id: int
    target_schema: Optional[str] = None
    create_target_table: bool = False
    migration_mode: Literal["append", "truncate_load"] = "append"

    @validator("tables")
    def at_least_one_enabled(cls, v):
        if not any(t.enabled for t in v):
            raise ValueError("at least one enabled table entry is required")
        return v

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

class TableQualification(BaseModel):
    original: str                  # the entry as currently stored (e.g. "orders")
    schema_name: Optional[str] = None
    object_name: str

class JobValidationResponse(BaseModel):
    valid: bool
    items: list[JobValidationItem]
    warnings: list[str]
    qualified: list[TableQualification] = []  # bare/mis-cased entries resolved against the source catalog

class JobExecuteResponse(BaseModel):
    execution_id: int
    job_id: int
    status: str
    started_at: datetime
