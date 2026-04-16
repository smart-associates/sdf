from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import logging

from app.core.config import settings
from app.database import init_db
from app.models import *  # noqa: ensure models are registered
from app.routers import connections, jobs, executions, settings as settings_router

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await run_migrations()
    await recover_stale_executions()
    await seed_defaults()
    yield
    # Graceful shutdown: signal running jobs and wait for threads to finish
    from app.services.job_runner import shutdown_all, _sync_engine
    shutdown_all()
    _sync_engine.dispose()


async def run_migrations():
    """Apply incremental schema changes to existing databases."""
    from app.database import engine
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    if engine.dialect.name == "sqlite":
        return

    logger = logging.getLogger(__name__)
    migrations = [
        "ALTER TABLE job_execution_tables ADD COLUMN estimated_row_count INTEGER",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_one_running_per_job
           ON job_executions (job_id) WHERE status = 'running'""",
        "ALTER TABLE database_connections ADD COLUMN staging_format VARCHAR(50)",
        "CREATE INDEX IF NOT EXISTS ix_job_executions_job_id ON job_executions (job_id)",
        "CREATE INDEX IF NOT EXISTS ix_job_execution_tables_execution_id ON job_execution_tables (execution_id)",
        "ALTER TABLE job_executions ALTER COLUMN started_at TYPE TIMESTAMPTZ USING started_at::timestamptz",
        "ALTER TABLE job_executions ALTER COLUMN completed_at TYPE TIMESTAMPTZ USING completed_at::timestamptz",
        "ALTER TABLE job_execution_tables ALTER COLUMN started_at TYPE TIMESTAMPTZ USING started_at::timestamptz",
        "ALTER TABLE job_execution_tables ALTER COLUMN completed_at TYPE TIMESTAMPTZ USING completed_at::timestamptz",
        "ALTER TABLE database_connections ALTER COLUMN password TYPE VARCHAR(8192)",
        """CREATE TABLE IF NOT EXISTS job_execution_logs (
               id SERIAL PRIMARY KEY,
               execution_id INTEGER NOT NULL REFERENCES job_executions(id),
               exec_table_id INTEGER REFERENCES job_execution_tables(id),
               level VARCHAR(20) NOT NULL,
               event_type VARCHAR(50) NOT NULL,
               message TEXT NOT NULL,
               metadata JSONB,
               created_at TIMESTAMPTZ DEFAULT now()
           )""",
        "CREATE INDEX IF NOT EXISTS ix_job_execution_logs_execution_id ON job_execution_logs (execution_id)",
        "CREATE INDEX IF NOT EXISTS ix_job_execution_logs_exec_table_id ON job_execution_logs (exec_table_id)",
        "ALTER TABLE job_executions ALTER COLUMN record_count TYPE BIGINT",
        "ALTER TABLE job_execution_tables ALTER COLUMN record_count TYPE BIGINT",
        "ALTER TABLE job_execution_tables ALTER COLUMN estimated_row_count TYPE BIGINT",
    ]
    for stmt in migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except ProgrammingError:
            pass  # already applied (e.g. duplicate column)
        except Exception as e:
            logger.warning("Migration failed: %s — %s", stmt.strip().split('\n')[0], e)

async def recover_stale_executions():
    """Mark any orphaned 'running' executions as failed on startup."""
    from app.database import engine
    from sqlalchemy import text, bindparam

    logger = logging.getLogger(__name__)
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT id FROM job_executions WHERE status = 'running'"
        ))
        exec_ids = [r[0] for r in result.fetchall()]
        if not exec_ids:
            return
        logger.warning("Recovered %d stale execution(s): %s", len(exec_ids), exec_ids)
        update_exec = text(
            """UPDATE job_executions
               SET status = 'failed',
                   completed_at = CURRENT_TIMESTAMP,
                   error_message = 'Process restarted while execution was running'
               WHERE id IN :ids"""
        ).bindparams(bindparam("ids", expanding=True))
        await conn.execute(update_exec, {"ids": exec_ids})
        update_tables = text(
            """UPDATE job_execution_tables
               SET status = 'failed',
                   completed_at = CURRENT_TIMESTAMP
               WHERE execution_id IN :ids
                 AND status = 'running'"""
        ).bindparams(bindparam("ids", expanding=True))
        await conn.execute(update_tables, {"ids": exec_ids})


async def seed_defaults():
    from app.database import AsyncSessionLocal
    from app.models.setting import Setting
    from sqlalchemy import select

    defaults = [
        ("batch_size", "1000", "Number of rows per INSERT batch", "integer"),
        ("csv_quoting", "none", "Quote character for CSV export: none (backslash escape), single, or double", "string"),
        ("csv_delimiter", ",", "Field delimiter for CSV output. Use escape sequences for control characters: \\t (tab), \\001 (SOH), etc.", "string"),
        ("csv_header", "true", "Include column headers in CSV export", "boolean"),
        ("log_level", "minimal", "Logging verbosity for job executions: minimal (key events only) or detailed (includes batch progress)", "string"),
    ]
    async with AsyncSessionLocal() as db:
        for key, value, desc, dtype in defaults:
            result = await db.execute(select(Setting).where(Setting.key == key))
            if not result.scalar_one_or_none():
                db.add(Setting(key=key, value=value, description=desc, data_type=dtype))
        await db.commit()

app = FastAPI(title="SDF - Smart Data Frameworks", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connections.router)
app.include_router(jobs.router)
app.include_router(executions.router)
app.include_router(settings_router.router)

@app.get("/health")
async def health():
    return {"status": "ok"}


_UI_DIST = Path(settings.ui_dist_dir)
if _UI_DIST.is_dir() and (_UI_DIST / "index.html").is_file():
    _assets_dir = _UI_DIST / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404)
        candidate = _UI_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_UI_DIST / "index.html")
