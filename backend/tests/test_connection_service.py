from app.services.connection_service import create_connection, list_connections, get_connection
from app.services.encryption import MASKED


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
