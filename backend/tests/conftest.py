import os
import subprocess
import shutil
from pathlib import Path

# Resolve database URL, mirroring start.sh logic:
#   1. Check backend/.env for DATABASE_URL
#   2. If no .env, check if PostgreSQL is running locally via pg_isready
#   3. Fall back to in-memory SQLite
_dotenv = Path(__file__).resolve().parent.parent / ".env"
_db_url = None
_sync_db_url = None

if _dotenv.exists():
    for line in _dotenv.read_text().splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            _db_url = line.split("=", 1)[1]
        elif line.startswith("SYNC_DATABASE_URL="):
            _sync_db_url = line.split("=", 1)[1]

if _db_url:
    pass  # got URLs from .env
elif shutil.which("pg_isready") and subprocess.run(
    ["pg_isready", "-q"], capture_output=True
).returncode == 0:
    _db_url = "postgresql+asyncpg:///sdf?host=/var/run/postgresql"
    _sync_db_url = "postgresql+psycopg2:///sdf?host=/var/run/postgresql"
else:
    _db_url = "sqlite+aiosqlite://"
    _sync_db_url = "sqlite:///"

# Use a separate test database so dev data is never touched
if "postgresql" in _db_url:
    import re
    _db_url = re.sub(r"/sdf(\b)", r"/sdf_test\1", _db_url)
    _sync_db_url = re.sub(r"/sdf(\b)", r"/sdf_test\1", _sync_db_url)
    # Auto-create sdf_test if it doesn't exist (mirrors start.sh for sdf)
    if shutil.which("psql"):
        result = subprocess.run(
            ["psql", "-h", "/var/run/postgresql", "-lqt"],
            capture_output=True, text=True
        )
        if "sdf_test" not in result.stdout:
            subprocess.run(
                ["createdb", "-h", "/var/run/postgresql", "sdf_test"],
                capture_output=True
            )
    print(f"Tests using PostgreSQL: {_db_url}")
else:
    print("Tests using in-memory SQLite")

os.environ.setdefault("DATABASE_URL", _db_url)
os.environ.setdefault("SYNC_DATABASE_URL", _sync_db_url or "sqlite:///")

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport

from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
async def test_engine():
    pool_kwargs = {}
    if "sqlite" not in _db_url:
        pool_kwargs = dict(pool_size=5, max_overflow=10, pool_pre_ping=True)
    engine = create_async_engine(_db_url, echo=False, **pool_kwargs)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.fixture(autouse=True)
async def clean_tables(test_engine):
    """Clean all rows before each test for isolation with persistent databases."""
    async with test_engine.begin() as conn:
        if "sqlite" not in _db_url:
            # PostgreSQL: TRUNCATE with CASCADE handles FK constraints
            table_names = ", ".join(t.name for t in Base.metadata.sorted_tables)
            if table_names:
                from sqlalchemy import text
                await conn.execute(text(f"TRUNCATE {table_names} CASCADE"))
        else:
            # SQLite: delete in reverse FK order
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())
    yield


@pytest.fixture
async def db_session(test_engine):
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
