from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

class DatabaseConnectionBase(BaseModel):
    name: str
    db_type: Literal["postgresql", "mysql", "mssql", "filesystem"]
    host: Optional[str] = None
    port: Optional[int] = None
    database: str  # for filesystem: directory path
    username: Optional[str] = None
    staging_format: Optional[str] = None  # csv|parquet (filesystem connections only)

class DatabaseConnectionCreate(DatabaseConnectionBase):
    password: Optional[str] = None

class DatabaseConnectionUpdate(DatabaseConnectionBase):
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
