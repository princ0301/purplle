# PROMPT: Generate pytest async tests for a FastAPI health endpoint.
# Cover: returns 200, required fields present, db_connected true, stores list structure.
# CHANGES MADE: Updated store ID to ST1008.

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_returns_200(client):
    r = await client.get("/health")
    assert r.status_code == 200


async def test_health_required_fields(client):
    r = await client.get("/health")
    body = r.json()
    assert "status" in body
    assert "db_connected" in body
    assert "stores" in body


async def test_health_db_connected(client):
    r = await client.get("/health")
    assert r.json()["db_connected"] is True


async def test_health_status_ok_no_stores(client):
    r = await client.get("/health")
    assert r.json()["status"] == "ok"


async def test_health_shows_store_after_ingest(client):
    from tests.conftest import make_event
    event = make_event("ENTRY", visitor_id="VIS_health01")
    await client.post("/events/ingest", json={"events": [event]})
    r = await client.get("/health")
    body = r.json()
    store_ids = [s["store_id"] for s in body["stores"]]
    assert "ST1008" in store_ids


async def test_health_store_has_required_fields(client):
    from tests.conftest import make_event
    event = make_event("ENTRY", visitor_id="VIS_health02")
    await client.post("/events/ingest", json={"events": [event]})
    r = await client.get("/health")
    store = r.json()["stores"][0]
    assert "store_id" in store
    assert "status" in store
    assert "last_event_time" in store