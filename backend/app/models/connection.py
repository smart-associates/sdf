from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base

class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    db_type = Column(String(50), nullable=False)  # postgresql|mysql|mssql
    host = Column(String(255), nullable=True)
    port = Column(Integer)
    database = Column(String(255), nullable=False)
    username = Column(String(255))
    password = Column(String(1024))  # encrypted
    last_test_status = Column(String(50))   # success|failed
    last_tested_at = Column(String(50))
    last_test_error = Column(String(2048))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
