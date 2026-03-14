from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    source_connection_id = Column(Integer, ForeignKey("database_connections.id"), nullable=False)
    source_tables = Column(Text)          # newline-separated: schema.table or table
    table_filter = Column(Text)           # WHERE clause applied to all tables
    target_connection_id = Column(Integer, ForeignKey("database_connections.id"), nullable=False)
    target_schema = Column(String(255))   # override target schema
    create_target_table = Column(Boolean, default=False)
    migration_mode = Column(String(50), default="append")  # append|truncate_load
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class JobExecution(Base):
    __tablename__ = "job_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    status = Column(String(50), nullable=False, default="running")  # running|success|failed
    started_at = Column(String(50), nullable=False)
    completed_at = Column(String(50))
    record_count = Column(Integer, default=0)
    error_message = Column(Text)

class JobExecutionTable(Base):
    __tablename__ = "job_execution_tables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("job_executions.id"), nullable=False)
    table_name = Column(String(512), nullable=False)
    status = Column(String(50), nullable=False, default="running")
    started_at = Column(String(50), nullable=False)
    completed_at = Column(String(50))
    record_count = Column(Integer, default=0)
    error_message = Column(Text)
