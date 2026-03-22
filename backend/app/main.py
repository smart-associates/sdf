from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
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


async def run_migrations():
    """Apply incremental schema changes to existing databases."""
    from app.database import engine
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    logger = logging.getLogger(__name__)
    migrations = [
        "ALTER TABLE job_execution_tables ADD COLUMN estimated_row_count INTEGER",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_one_running_per_job
           ON job_executions (job_id) WHERE status = 'running'""",
        "ALTER TABLE database_connections ADD COLUMN staging_format VARCHAR(50)",
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
    from sqlalchemy import text

    logger = logging.getLogger(__name__)
    async with engine.begin() as conn:
        result = await conn.execute(text(
            """UPDATE job_executions
               SET status = 'failed',
                   completed_at = now(),
                   error_message = 'Process restarted while execution was running'
               WHERE status = 'running'
               RETURNING id"""
        ))
        rows = result.fetchall()
        if rows:
            exec_ids = [r[0] for r in rows]
            logger.warning("Recovered %d stale execution(s): %s", len(exec_ids), exec_ids)
            await conn.execute(text(
                """UPDATE job_execution_tables
                   SET status = 'failed',
                       completed_at = now()
                   WHERE execution_id = ANY(:ids)
                     AND status = 'running'"""
            ), {"ids": exec_ids})


async def seed_defaults():
    from app.database import AsyncSessionLocal
    from app.models.setting import Setting
    from sqlalchemy import select

    defaults = [
        ("batch_size", "1000", "Number of rows per INSERT batch", "integer"),
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
