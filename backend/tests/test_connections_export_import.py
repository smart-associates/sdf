"""Connection configuration export/import (issue #21).

Covers the acceptance criteria directly:
- round trip of a connection's non-secret metadata
- the export payload never carries a password or its ciphertext
- ambiguous name resolution on import is reported, not guessed
- re-importing the same document twice is a no-op (update in place),
  preserving the existing secret
"""
from sqlalchemy import select

from app.core.config import settings
from app.models.connection import DatabaseConnection
from app.services.encryption import encrypt


async def _create_connection(client, **overrides):
    payload = {
        "name": "src", "db_type": "postgresql", "host": "srchost", "port": 5432,
        "database": "srcdb", "username": "srcuser", "password": "s3cr3t-password",
    }
    payload.update(overrides)
    resp = await client.post("/api/connections", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_export_import_round_trip(db_session, client):
    created = await _create_connection(client, name="round_trip_conn", staging_format="csv")

    export_resp = await client.get(f"/api/connections/{created['id']}/export")
    assert export_resp.status_code == 200, export_resp.text
    doc = export_resp.json()
    assert doc["format_version"] == 1
    assert len(doc["connections"]) == 1
    exported = doc["connections"][0]
    assert exported["name"] == "round_trip_conn"
    assert exported["host"] == "srchost"
    assert exported["staging_format"] == "csv"
    assert "password" not in exported

    del_resp = await client.delete(f"/api/connections/{created['id']}")
    assert del_resp.status_code == 204

    import_resp = await client.post("/api/connections/import", json=doc)
    assert import_resp.status_code == 200, import_resp.text
    result = import_resp.json()
    assert result["created"] == ["round_trip_conn"]
    assert result["updated"] == []
    assert result["failed"] == []

    reimported = (await db_session.execute(
        select(DatabaseConnection).where(DatabaseConnection.name == "round_trip_conn")
    )).scalar_one()
    assert reimported.host == "srchost"
    assert reimported.staging_format == "csv"
    assert reimported.password is None  # never carried by the export — needs setting by hand


async def test_reimport_updates_in_place_and_keeps_existing_secret(db_session, client):
    created = await _create_connection(client, name="update_conn")
    doc = (await client.get(f"/api/connections/{created['id']}/export")).json()

    # Change the host locally, then re-import the (still-old) export doc —
    # the import should overwrite it back, and the secret set at creation
    # must survive untouched since the export never carries it.
    await client.put(f"/api/connections/{created['id']}", json={
        **created, "host": "changed-elsewhere", "password": "********",
    })

    import_resp = await client.post("/api/connections/import", json=doc)
    assert import_resp.status_code == 200, import_resp.text
    result = import_resp.json()
    assert result["created"] == []
    assert result["updated"] == ["update_conn"]

    row = (await db_session.execute(
        select(DatabaseConnection).where(DatabaseConnection.name == "update_conn")
    )).scalar_one()
    assert row.host == "srchost"
    assert row.password is not None
    assert row.password != "s3cr3t-password"  # stored encrypted, not plaintext


async def test_export_payload_contains_no_credentials(client):
    created = await _create_connection(client, name="secret_conn")

    export_resp = await client.get(f"/api/connections/{created['id']}/export")
    raw = export_resp.text

    assert "s3cr3t-password" not in raw
    assert encrypt("s3cr3t-password") not in raw
    assert "********" not in raw
    assert settings.encryption_key not in raw
    assert '"password"' not in raw


async def test_ambiguous_connection_name_is_reported_not_guessed(db_session, client):
    await _create_connection(client, name="dup_conn")
    dup = DatabaseConnection(
        name="dup_conn", db_type="postgresql", host="other", port=5432,
        database="d", username="u", password=None,
    )
    db_session.add(dup)
    await db_session.commit()

    doc = {
        "format_version": 1,
        "exported_at": "2026-01-01T00:00:00Z",
        "connections": [{
            "name": "dup_conn", "db_type": "postgresql", "host": "h",
            "port": 5432, "database": "d",
        }],
    }
    resp = await client.post("/api/connections/import", json=doc)
    assert resp.status_code == 400
    assert "ambiguous" in resp.text


async def test_export_all_connections(client):
    await _create_connection(client, name="a")
    await _create_connection(client, name="b")

    resp = await client.get("/api/connections/export")
    assert resp.status_code == 200, resp.text
    names = {c["name"] for c in resp.json()["connections"]}
    assert {"a", "b"} <= names


async def test_import_rejects_unsupported_format_version(client):
    resp = await client.post("/api/connections/import", json={
        "format_version": 2, "exported_at": "2026-01-01T00:00:00Z", "connections": [],
    })
    assert resp.status_code == 400
