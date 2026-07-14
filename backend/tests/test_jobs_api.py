"""API tests for the job_tables selection model on the jobs endpoints."""


async def _make_conn(client, name):
    resp = await client.post("/api/connections", json={
        "name": name, "db_type": "filesystem", "database": f"/tmp/{name}",
        "staging_format": "parquet",
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
