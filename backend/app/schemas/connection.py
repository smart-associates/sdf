from pydantic import BaseModel, ConfigDict
from typing import List, Literal, Optional
from datetime import datetime

class DatabaseConnectionBase(BaseModel):
    name: str
    db_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: str  # for filesystem: directory path
    username: Optional[str] = None
    staging_format: Optional[str] = None  # csv|tsv|parquet|avro (filesystem connections only)

class DatabaseConnectionCreate(DatabaseConnectionBase):
    db_type: Literal["postgresql", "mysql", "filesystem"]
    password: Optional[str] = None

class DatabaseConnectionUpdate(DatabaseConnectionBase):
    db_type: Literal["postgresql", "mysql", "filesystem"]
    password: Optional[str] = None

class DatabaseConnectionResponse(DatabaseConnectionBase):
    id: int
    password: Optional[str] = None  # will be masked
    last_test_status: Optional[str] = None
    last_tested_at: Optional[str] = None
    last_test_error: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    tested_at: str
    error: Optional[str] = None

class ConnectionExportItem(DatabaseConnectionBase):
    """A connection's config as a portable document.

    DatabaseConnectionBase already excludes id and password — it's exactly
    the safe-to-export shape, so this is a thin reuse rather than a restatement.
    """
    model_config = ConfigDict(from_attributes=True)

class ConnectionExportDocument(BaseModel):
    format_version: int = 1
    exported_at: datetime
    connections: List[ConnectionExportItem]

class ConnectionImportFailure(BaseModel):
    name: str
    error: str

class ConnectionImportResult(BaseModel):
    created: List[str] = []
    updated: List[str] = []
    failed: List[ConnectionImportFailure] = []
