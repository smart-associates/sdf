from sqlalchemy import text

from app.services.connection_service import create_connection, list_connections, get_connection
from app.services.encryption import MASKED, decrypt


async def test_create_connection(db_session):
    conn = await create_connection(db_session, {
        "name": "Test PG",
        "db_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "testdb",
        "username": "user",
        "password": "secret",
    })
    assert conn.id is not None
    assert conn.name == "Test PG"
    assert conn.password == MASKED  # password is masked on return


async def test_list_connections(db_session):
    await create_connection(db_session, {
        "name": "List Test",
        "db_type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "mydb",
        "username": "user",
        "password": "pw",
    })
    conns = await list_connections(db_session)
    assert len(conns) >= 1
    assert all(c.password == MASKED for c in conns)


async def test_get_connection_not_found(db_session):
    result = await get_connection(db_session, 99999)
    assert result is None


async def test_masking_does_not_dirty_session(db_session):
    """Masking the response object must not mark it dirty for autoflush —
    otherwise a later query in the same request flushes the literal mask
    string over the real encrypted password (see issue #8)."""
    conn = await create_connection(db_session, {
        "name": "Mask Dirty Test",
        "db_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "testdb",
        "username": "user",
        "password": "secret",
    })
    assert conn.password == MASKED
    assert not db_session.is_modified(conn)

    # Force a flush (as an autoflush before another query would) and verify
    # the stored ciphertext survived, not the mask placeholder. Query the raw
    # column directly — going through the ORM would just return the same
    # identity-mapped (masked) instance rather than what's actually in the DB.
    await db_session.flush()
    row = (await db_session.execute(
        text("SELECT password FROM database_connections WHERE id = :id"),
        {"id": conn.id},
    )).first()
    assert row.password != MASKED
    assert decrypt(row.password) == "secret"
