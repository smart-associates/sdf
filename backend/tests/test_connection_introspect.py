"""Tests for the Job form's table/view/file browse endpoints (issue #19)."""
import getpass


async def test_list_files_for_filesystem_connection(client, tmp_path):
    (tmp_path / "orders.csv").write_text("id\n1\n")
    (tmp_path / "customers.csv").write_text("id\n1\n")
    (tmp_path / "notes.txt").write_text("not a data file")

    resp = await client.post("/api/connections", json={
        "name": "files", "db_type": "filesystem", "database": str(tmp_path),
        "staging_format": "csv",
    })
    conn_id = resp.json()["id"]

    resp = await client.get(f"/api/connections/{conn_id}/files")
    assert resp.status_code == 200, resp.text
    tables = sorted(f["table"] for f in resp.json()["files"])
    assert tables == ["customers", "orders"]


async def test_list_files_rejects_non_filesystem_connection(client):
    resp = await client.post("/api/connections", json={
        "name": "pg", "db_type": "postgresql", "host": "localhost",
        "port": 5432, "database": "whatever",
    })
    conn_id = resp.json()["id"]

    resp = await client.get(f"/api/connections/{conn_id}/files")
    assert resp.status_code == 400


async def test_list_schemas_and_objects_for_postgres_connection(client):
    # Point the connection at this test run's own Postgres database — a real,
    # already-reachable catalog to introspect without standing up a second DB.
    resp = await client.post("/api/connections", json={
        "name": "self", "db_type": "postgresql", "host": "/var/run/postgresql",
        "port": 5432, "database": "sdf_test",
        "username": getpass.getuser(),
    })
    conn_id = resp.json()["id"]

    resp = await client.get(f"/api/connections/{conn_id}/schemas")
    assert resp.status_code == 200, resp.text
    assert "public" in resp.json()["schemas"]

    resp = await client.get(f"/api/connections/{conn_id}/objects", params={"schema": "public"})
    assert resp.status_code == 200, resp.text
    objects = resp.json()["objects"]
    names = {o["name"] for o in objects}
    assert "database_connections" in names
    kinds = {o["kind"] for o in objects}
    assert kinds <= {"table", "view"}


async def test_browse_endpoints_404_for_unknown_connection(client):
    resp = await client.get("/api/connections/999999/schemas")
    assert resp.status_code == 404
    resp = await client.get("/api/connections/999999/objects")
    assert resp.status_code == 404
    resp = await client.get("/api/connections/999999/files")
    assert resp.status_code == 404
