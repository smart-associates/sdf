from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DatabaseConnectionBase(BaseModel):
    name: str
    db_type: str  # postgresql|mysql|mssql|csv
    host: Optional[str] = None
    port: Optional[int] = None
    database: str  # for csv: directory path
    username: Optional[str] = None

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
