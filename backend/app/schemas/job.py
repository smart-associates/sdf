from pydantic import BaseModel, Field, validator
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


class ConnectionRef(BaseModel):
    """A connection referenced by name/type only — never credentials, and
    never any other connection metadata either, since a connection is its own
    portable export/import document. Resolved against the target instance's
    connections by (name, db_type); never auto-created.
    """
    name: str
    db_type: str


class JobExportItem(JobBase):
    """A job's config as a portable document — connection IDs replaced by
    name/type references.

    The two *_connection_id ints are inherited from JobBase but given a
    default and marked exclude=True: they're meaningless on another instance,
    must not appear in the serialized document, and — since this model is
    also used to *parse* an imported document — must not be required on the
    way in either (the exported JSON never contains them).
    """
    source_connection_id: Optional[int] = Field(default=None, exclude=True)
    target_connection_id: Optional[int] = Field(default=None, exclude=True)
    source_connection: Optional[ConnectionRef] = None
    target_connection: Optional[ConnectionRef] = None


class JobExportDocument(BaseModel):
    format_version: int = 1
    exported_at: datetime
    jobs: List[JobExportItem]


class JobImportFailure(BaseModel):
    name: str
    error: str


class JobImportResult(BaseModel):
    created: List[str] = []
    updated: List[str] = []
    failed: List[JobImportFailure] = []

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
