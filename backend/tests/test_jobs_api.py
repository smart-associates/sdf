"""API tests for the job_tables selection model on the jobs endpoints."""
import getpass


async def _make_conn(client, name, directory=None, staging_format="parquet"):
    resp = await client.post("/api/connections", json={
        "name": name, "db_type": "filesystem", "database": directory or f"/tmp/{name}",
        "staging_format": staging_format,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _job_payload(src, tgt, tables):
    return {
        "name": "job1",
        "source_connection_id": src,
        "target_connection_id": tgt,
        "tables": tables,
        "migration_mode": "append",
        "create_target_table": True,
    }


async def test_create_job_with_tables_roundtrip(client):
    src = await _make_conn(client, "src")
    tgt = await _make_conn(client, "tgt")
    payload = await _job_payload(src, tgt, [
        {"schema_name": "public", "object_name": "users", "table_filter": "id > 1", "position": 0},
        {"object_name": "orders", "position": 1},
    ])
    resp = await client.post("/api/jobs", json=payload)
    assert resp.status_code == 201, resp.text
    job = resp.json()
    assert [t["object_name"] for t in job["tables"]] == ["users", "orders"]
    assert job["tables"][0]["schema_name"] == "public"
    assert job["tables"][0]["table_filter"] == "id > 1"
    assert job["tables"][1]["table_filter"] is None

    # Round-trips on GET
    got = (await client.get(f"/api/jobs/{job['id']}")).json()
    assert [t["object_name"] for t in got["tables"]] == ["users", "orders"]


async def test_create_job_requires_an_enabled_table(client):
    src = await _make_conn(client, "src")
    tgt = await _make_conn(client, "tgt")
    payload = await _job_payload(src, tgt, [
        {"object_name": "orders", "enabled": False, "position": 0},
    ])
    resp = await client.post("/api/jobs", json=payload)
    assert resp.status_code == 422


async def test_update_job_replaces_tables(client):
    src = await _make_conn(client, "src")
    tgt = await _make_conn(client, "tgt")
    created = (await client.post("/api/jobs", json=await _job_payload(
        src, tgt, [{"object_name": "a", "position": 0}]))).json()

    payload = await _job_payload(src, tgt, [
        {"object_name": "b", "position": 0},
        {"object_name": "c", "position": 1},
    ])
    resp = await client.put(f"/api/jobs/{created['id']}", json=payload)
    assert resp.status_code == 200, resp.text
    assert [t["object_name"] for t in resp.json()["tables"]] == ["b", "c"]


async def test_validate_job_resolves_dotted_filesystem_filename(client, tmp_path):
    """A filesystem source file literally named "title.ratings.csv" must be
    resolved by its full stem, not mis-split into a fake "title" schema and
    "ratings" table (issue #10)."""
    (tmp_path / "title.ratings.csv").write_text("id,rating\n1,5\n")
    src = await _make_conn(client, "src", directory=str(tmp_path), staging_format="csv")
    tgt = await _make_conn(client, "tgt", directory=str(tmp_path / "out"))

    created = (await client.post("/api/jobs", json=await _job_payload(
        src, tgt, [{"object_name": "title.ratings", "position": 0}]))).json()

    resp = await client.post(f"/api/jobs/{created['id']}/validate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"][0]["exists"] is True
    assert body["items"][0]["message"] == "CSV file found"
    assert body["valid"] is True


async def _make_pg_conn(client, name):
    """A postgresql connection pointing at this test run's own database — a
    real, already-reachable catalog to validate against."""
    resp = await client.post("/api/connections", json={
        "name": name, "db_type": "postgresql", "host": "/var/run/postgresql",
        "port": 5432, "database": "sdf_test", "username": getpass.getuser(),
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_validate_job_qualifies_bare_entry_against_catalog(client):
    """A bare manual entry that only exists in a non-default schema should be
    qualified against the real source catalog, not read as not-found (issue
    #17)."""
    src = await _make_pg_conn(client, "src")
    tgt = await _make_pg_conn(client, "tgt")

    created = (await client.post("/api/jobs", json=await _job_payload(
        src, tgt, [{"object_name": "database_connections", "position": 0}]))).json()

    resp = await client.post(f"/api/jobs/{created['id']}/validate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"][0]["exists"] is True
    assert body["valid"] is True
    assert body["qualified"] == [{
        "original": "database_connections",
        "schema_name": "public",
        "object_name": "database_connections",
    }]


async def test_validate_job_case_corrects_qualified_entry(client):
    src = await _make_pg_conn(client, "src")
    tgt = await _make_pg_conn(client, "tgt")

    created = (await client.post("/api/jobs", json=await _job_payload(
        src, tgt, [{"schema_name": "Public", "object_name": "DATABASE_CONNECTIONS", "position": 0}]))).json()

    resp = await client.post(f"/api/jobs/{created['id']}/validate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"][0]["exists"] is True
    assert body["qualified"] == [{
        "original": "Public.DATABASE_CONNECTIONS",
        "schema_name": "public",
        "object_name": "database_connections",
    }]


async def test_validate_job_no_qualification_for_filesystem_source(client, tmp_path):
    (tmp_path / "orders.csv").write_text("id\n1\n")
    src = await _make_conn(client, "src", directory=str(tmp_path), staging_format="csv")
    tgt = await _make_conn(client, "tgt", directory=str(tmp_path / "out"))

    created = (await client.post("/api/jobs", json=await _job_payload(
        src, tgt, [{"object_name": "orders", "position": 0}]))).json()

    resp = await client.post(f"/api/jobs/{created['id']}/validate")
    assert resp.status_code == 200, resp.text
    assert resp.json()["qualified"] == []
