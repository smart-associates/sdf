"""Pipeline configuration export/import (issue #21).

Covers the acceptance criteria directly:
- round trip of a job with multiple literal table entries and a per-object filter
- the export payload never carries a connection's plaintext password,
  encrypted blob, or the encryption key itself
- import against an instance missing a referenced connection reports the
  missing name and creates nothing
- re-importing the same document twice is a no-op (no duplicate jobs or rows)
- ambiguous connection/job name resolution is reported, not silently guessed
"""
from sqlalchemy import select

from app.core.config import settings
from app.models.connection import DatabaseConnection
from app.models.job import Job, JobTable
from app.services.encryption import encrypt


async def _seed_connections(db_session, **overrides):
    src = DatabaseConnection(
        name=overrides.get("src_name", "src"), db_type="postgresql", host="srchost", port=5432,
        database="srcdb", username="srcuser", password=encrypt("s3cr3t-password"),
    )
    tgt = DatabaseConnection(
        name=overrides.get("tgt_name", "tgt"), db_type="postgresql", host="tgthost", port=5432,
        database="tgtdb", username="tgtuser", password=encrypt("another-s3cr3t"),
    )
    db_session.add(src)
    db_session.add(tgt)
    await db_session.commit()
    await db_session.refresh(src)
    await db_session.refresh(tgt)
    return src.id, tgt.id


def _rich_job_payload(src_id, tgt_id, name="rich_job"):
    return {
        "name": name,
        "source_connection_id": src_id,
        "target_connection_id": tgt_id,
        "tables": [
            {"object_name": "orders", "schema_name": "sales",
             "table_filter": "status = 'active'", "enabled": True, "position": 0},
            {"object_name": "customers", "schema_name": "sales", "enabled": True, "position": 1},
        ],
        "migration_mode": "append",
        "target_schema": "public",
        "create_target_table": True,
    }


async def _create_job(client, payload):
    resp = await client.post("/api/jobs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_export_import_round_trip(db_session, client):
    src_id, tgt_id = await _seed_connections(db_session)
    created = await _create_job(client, _rich_job_payload(src_id, tgt_id))

    export_resp = await client.get(f"/api/jobs/{created['id']}/export")
    assert export_resp.status_code == 200, export_resp.text
    doc = export_resp.json()
    assert doc["format_version"] == 1
    assert len(doc["jobs"]) == 1
    exported = doc["jobs"][0]
    assert exported["name"] == "rich_job"
    assert exported["target_schema"] == "public"
    assert exported["create_target_table"] is True
    # Connection refs are name+type only — a connection's own metadata is
    # exported/imported separately, not embedded in a job document.
    assert exported["source_connection"] == {"name": "src", "db_type": "postgresql"}
    assert exported["target_connection"] == {"name": "tgt", "db_type": "postgresql"}
    assert "source_connection_id" not in exported
    assert len(exported["tables"]) == 2
    assert any(t.get("table_filter") == "status = 'active'" for t in exported["tables"])

    # delete the original job, then import the exported document back in —
    # the round trip must reproduce every field and every job_tables row
    del_resp = await client.delete(f"/api/jobs/{created['id']}")
    assert del_resp.status_code == 204

    import_resp = await client.post("/api/jobs/import", json=doc)
    assert import_resp.status_code == 200, import_resp.text
    result = import_resp.json()
    assert result["created"] == ["rich_job"]
    assert result["updated"] == []
    assert result["failed"] == []

    reimported = (await db_session.execute(select(Job).where(Job.name == "rich_job"))).scalar_one()
    assert reimported.target_schema == "public"
    assert reimported.create_target_table is True
    rows = (await db_session.execute(
        select(JobTable).where(JobTable.job_id == reimported.id).order_by(JobTable.position)
    )).scalars().all()
    assert len(rows) == 2
    assert rows[0].table_filter == "status = 'active'"


async def test_export_payload_contains_no_credentials(db_session, client):
    src_id, tgt_id = await _seed_connections(db_session)
    created = await _create_job(client, _rich_job_payload(src_id, tgt_id))

    export_resp = await client.get(f"/api/jobs/{created['id']}/export")
    raw = export_resp.text

    assert "s3cr3t-password" not in raw
    assert "another-s3cr3t" not in raw
    assert encrypt("s3cr3t-password") not in raw  # no ciphertext either
    assert "********" not in raw  # not even the mask sentinel
    assert settings.encryption_key not in raw
    assert '"password"' not in raw


async def test_import_missing_connection_reports_and_creates_nothing(db_session, client):
    src_id, tgt_id = await _seed_connections(db_session)
    created = await _create_job(client, _rich_job_payload(src_id, tgt_id))
    doc = (await client.get(f"/api/jobs/{created['id']}/export")).json()

    # simulate a target instance where the source connection doesn't exist
    doc["jobs"][0]["source_connection"]["name"] = "does-not-exist"

    await client.delete(f"/api/jobs/{created['id']}")
    resp = await client.post("/api/jobs/import", json=doc)
    assert resp.status_code == 400
    assert "does-not-exist" in resp.text

    jobs = (await db_session.execute(select(Job))).scalars().all()
    assert jobs == []


async def test_reimporting_same_document_twice_is_a_noop(db_session, client):
    src_id, tgt_id = await _seed_connections(db_session)
    created = await _create_job(client, _rich_job_payload(src_id, tgt_id))
    doc = (await client.get(f"/api/jobs/{created['id']}/export")).json()

    first = await client.post("/api/jobs/import", json=doc)
    assert first.status_code == 200, first.text
    assert first.json()["updated"] == ["rich_job"]  # job already exists (it was never deleted)

    second = await client.post("/api/jobs/import", json=doc)
    assert second.status_code == 200, second.text
    assert second.json()["updated"] == ["rich_job"]
    assert second.json()["created"] == []

    jobs = (await db_session.execute(select(Job).where(Job.name == "rich_job"))).scalars().all()
    assert len(jobs) == 1
    rows = (await db_session.execute(select(JobTable).where(JobTable.job_id == jobs[0].id))).scalars().all()
    assert len(rows) == 2


async def test_ambiguous_connection_name_is_reported_not_guessed(db_session, client):
    src_id, tgt_id = await _seed_connections(db_session)
    # a second connection sharing the source connection's name+type
    dup = DatabaseConnection(name="src", db_type="postgresql", host="other", port=5432, database="d", username="u", password=None)
    db_session.add(dup)
    await db_session.commit()

    created = await _create_job(client, _rich_job_payload(src_id, tgt_id))
    doc = (await client.get(f"/api/jobs/{created['id']}/export")).json()
    await client.delete(f"/api/jobs/{created['id']}")

    resp = await client.post("/api/jobs/import", json=doc)
    assert resp.status_code == 400
    assert "ambiguous" in resp.text

    jobs = (await db_session.execute(select(Job))).scalars().all()
    assert jobs == []


async def test_export_all_jobs(db_session, client):
    src_id, tgt_id = await _seed_connections(db_session)
    await _create_job(client, _rich_job_payload(src_id, tgt_id, name="job_a"))
    await _create_job(client, _rich_job_payload(src_id, tgt_id, name="job_b"))

    resp = await client.get("/api/jobs/export")
    assert resp.status_code == 200, resp.text
    names = {j["name"] for j in resp.json()["jobs"]}
    assert {"job_a", "job_b"} <= names


async def test_import_rejects_unsupported_format_version(client):
    resp = await client.post("/api/jobs/import", json={
        "format_version": 2, "exported_at": "2026-01-01T00:00:00Z", "jobs": [],
    })
    assert resp.status_code == 400
