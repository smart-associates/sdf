"""Tests for post-load schema migration: PK/index/CHECK on create, FKs as a
post-load phase (issue #25).

Runs real DDL against this test run's own Postgres database (skipped
entirely on the SQLite fallback, since these are constraint/reflection
behaviors that only make sense against a real relational engine). Source
and target tables live in separate schemas within the same database, which
both realistically simulates a same-server migration and avoids index-name
collisions (Postgres scopes index names per-schema, not per-table).
"""
import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import text

from app.services.migration_engine import create_target_table, migrate_foreign_keys

pytestmark = pytest.mark.skipif(
    "sqlite" in os.environ.get("SYNC_DATABASE_URL", ""),
    reason="schema migration tests need a real Postgres engine",
)


@pytest.fixture
def pg_engine():
    engine = sa.create_engine(os.environ["SYNC_DATABASE_URL"], pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def schemas(pg_engine):
    """A pair of throwaway schemas (src/tgt) so source and target tables never
    collide, dropped (with everything in them) after the test."""
    suffix = uuid.uuid4().hex[:8]
    src_schema, tgt_schema = f"src_{suffix}", f"tgt_{suffix}"
    with pg_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{src_schema}"'))
        conn.execute(text(f'CREATE SCHEMA "{tgt_schema}"'))
    yield src_schema, tgt_schema
    with pg_engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA "{src_schema}" CASCADE'))
        conn.execute(text(f'DROP SCHEMA "{tgt_schema}" CASCADE'))


def test_create_target_table_copies_primary_key(pg_engine, schemas):
    src_schema, tgt_schema = schemas
    with pg_engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{src_schema}".t (id INT PRIMARY KEY, name TEXT)'))

    create_target_table(pg_engine, pg_engine, "t", "t", src_schema, tgt_schema)

    insp = sa.inspect(pg_engine)
    pk = insp.get_pk_constraint("t", schema=tgt_schema)
    assert pk["constrained_columns"] == ["id"]


def test_create_target_table_does_not_recreate_identity(pg_engine, schemas):
    """A SERIAL source column must not become SERIAL/IDENTITY on the target —
    the target is bulk-loaded with the source's own id values, which a live
    generator would collide with (issue #25 / sdf-pro #53)."""
    src_schema, tgt_schema = schemas
    with pg_engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{src_schema}".t (id SERIAL PRIMARY KEY, name TEXT)'))

    create_target_table(pg_engine, pg_engine, "t", "t", src_schema, tgt_schema)

    with pg_engine.begin() as conn:
        row = conn.execute(text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = 't' AND column_name = 'id'"
        ), {"s": tgt_schema}).fetchone()
    assert row is not None
    assert row[0] is None


def test_create_target_table_copies_non_pk_index(pg_engine, schemas):
    src_schema, tgt_schema = schemas
    with pg_engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{src_schema}".t (id INT PRIMARY KEY, email TEXT)'))
        conn.execute(text(f'CREATE UNIQUE INDEX t_email_uq ON "{src_schema}".t (email)'))

    create_target_table(pg_engine, pg_engine, "t", "t", src_schema, tgt_schema)

    insp = sa.inspect(pg_engine)
    indexes = insp.get_indexes("t", schema=tgt_schema)
    assert any(set(i["column_names"]) == {"email"} and i["unique"] for i in indexes)


def test_create_target_table_skips_expression_index(pg_engine, schemas):
    """An expression-based index isn't portable (no plain column list) and
    must be skipped rather than crash table creation."""
    src_schema, tgt_schema = schemas
    with pg_engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{src_schema}".t (id INT PRIMARY KEY, name TEXT)'))
        conn.execute(text(f'CREATE INDEX t_lower_name ON "{src_schema}".t (lower(name))'))

    create_target_table(pg_engine, pg_engine, "t", "t", src_schema, tgt_schema)  # must not raise

    insp = sa.inspect(pg_engine)
    assert "t" in insp.get_table_names(schema=tgt_schema)


def test_create_target_table_copies_check_constraint_same_dialect(pg_engine, schemas):
    src_schema, tgt_schema = schemas
    with pg_engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{src_schema}".t (id INT PRIMARY KEY, age INT CHECK (age >= 0))'))

    create_target_table(pg_engine, pg_engine, "t", "t", src_schema, tgt_schema)

    with pytest.raises(Exception):
        with pg_engine.begin() as conn:
            conn.execute(text(f'INSERT INTO "{tgt_schema}".t (id, age) VALUES (1, -5)'))


def test_create_target_table_skips_check_constraint_cross_dialect(pg_engine, schemas):
    """CHECK expression text isn't translated across dialects — a
    cross-dialect target must not get the (possibly-invalid) constraint."""
    src_schema, tgt_schema = schemas
    sqlite_engine = sa.create_engine("sqlite://")
    try:
        with pg_engine.begin() as conn:
            conn.execute(text(f'CREATE TABLE "{src_schema}".t (id INT PRIMARY KEY, age INT CHECK (age >= 0))'))

        create_target_table(pg_engine, sqlite_engine, "t", "t", src_schema, None)

        with sqlite_engine.begin() as conn:
            # No CHECK constraint carried over -> a negative age must be accepted.
            conn.execute(text('INSERT INTO t (id, age) VALUES (1, -5)'))
            row = conn.execute(text('SELECT age FROM t WHERE id = 1')).fetchone()
        assert row[0] == -5
    finally:
        sqlite_engine.dispose()


def test_migrate_foreign_keys_applies_when_referenced_table_in_job(pg_engine, schemas):
    src_schema, tgt_schema = schemas
    with pg_engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{src_schema}".parent (id INT PRIMARY KEY)'))
        conn.execute(text(f'CREATE TABLE "{src_schema}".child (id INT PRIMARY KEY, parent_id INT REFERENCES "{src_schema}".parent(id))'))

    create_target_table(pg_engine, pg_engine, "parent", "parent", src_schema, tgt_schema)
    create_target_table(pg_engine, pg_engine, "child", "child", src_schema, tgt_schema)

    applied = migrate_foreign_keys(
        pg_engine, pg_engine,
        created=[("child", src_schema)],
        job_table_names={"parent", "child"},
        tgt_schema=tgt_schema,
    )
    assert applied == 1

    with pg_engine.begin() as conn:
        conn.execute(text(f'INSERT INTO "{tgt_schema}".parent (id) VALUES (1)'))
        with pytest.raises(Exception):
            conn.execute(text(f'INSERT INTO "{tgt_schema}".child (id, parent_id) VALUES (1, 999)'))


def test_migrate_foreign_keys_skips_table_outside_job_selection(pg_engine, schemas):
    src_schema, tgt_schema = schemas
    with pg_engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{src_schema}".parent (id INT PRIMARY KEY)'))
        conn.execute(text(f'CREATE TABLE "{src_schema}".child (id INT PRIMARY KEY, parent_id INT REFERENCES "{src_schema}".parent(id))'))

    create_target_table(pg_engine, pg_engine, "child", "child", src_schema, tgt_schema)
    # Deliberately do not create "parent" on the target at all.

    applied = migrate_foreign_keys(
        pg_engine, pg_engine,
        created=[("child", src_schema)],
        job_table_names={"child"},  # "parent" deliberately excluded
        tgt_schema=tgt_schema,
    )
    assert applied == 0

    # No FK on the target -> an orphaned reference is accepted.
    with pg_engine.begin() as conn:
        conn.execute(text(f'INSERT INTO "{tgt_schema}".child (id, parent_id) VALUES (1, 999)'))
