async def test_create_setting(client):
    resp = await client.post("/api/settings", json={
        "key": "test_key",
        "value": "42",
        "description": "A test setting",
        "data_type": "integer",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"] == "test_key"
    assert data["value"] == "42"
    assert "id" in data


async def test_list_settings(client):
    await client.post("/api/settings", json={"key": "list_test", "value": "v1", "data_type": "string"})
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert any(s["key"] == "list_test" for s in resp.json())


async def test_get_setting(client):
    create_resp = await client.post("/api/settings", json={"key": "get_test", "value": "v", "data_type": "string"})
    setting_id = create_resp.json()["id"]

    resp = await client.get(f"/api/settings/{setting_id}")
    assert resp.status_code == 200
    assert resp.json()["key"] == "get_test"


async def test_get_setting_not_found(client):
    resp = await client.get("/api/settings/99999")
    assert resp.status_code == 404


async def test_update_setting(client):
    create_resp = await client.post("/api/settings", json={"key": "upd_test", "value": "old", "data_type": "string"})
    setting_id = create_resp.json()["id"]

    resp = await client.put(f"/api/settings/{setting_id}", json={"value": "new"})
    assert resp.status_code == 200
    assert resp.json()["value"] == "new"


async def test_delete_setting(client):
    create_resp = await client.post("/api/settings", json={"key": "del_test", "value": "x", "data_type": "string"})
    setting_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/settings/{setting_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/settings/{setting_id}")
    assert resp.status_code == 404
