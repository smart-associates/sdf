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
    await seed_defaults()
    yield


async def run_migrations():
    """Apply incremental schema changes to existing databases."""
    from app.database import engine
    from sqlalchemy import text
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE job_execution_tables ADD COLUMN estimated_row_count INTEGER"
            ))
    except Exception:
        pass  # Column already exists

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
