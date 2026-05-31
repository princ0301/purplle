# PROMPT: Generate pytest async tests for a FastAPI ingest endpoint.
# Cover: valid batch, idempotency, malformed events, partial success, staff flag, batch limit.
# CHANGES MADE: Used conftest fixtures, adjusted store_id to STORE_BLR_001,
# added edge case for empty events list, used make_event helper.

import pytest
import uuid
from tests.conftest import make_event

pytestmark = pytest.mark.asyncio


async def test_ingest_valid_events(client):
    events = [make_event("ENTRY"), make_event("EXIT")]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 2
    assert body["duplicates"] == 0
    assert body["errors"] == 0


async def test_ingest_idempotency(client):
    event = make_event("ENTRY", visitor_id="VIS_idem01")
    payload = {"events": [event]}
    r1 = await client.post("/events/ingest", json=payload)
    r2 = await client.post("/events/ingest", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["duplicates"] == 1
    assert r2.json()["accepted"] == 0


async def test_ingest_partial_malformed(client):
    valid = make_event("ENTRY", visitor_id="VIS_partial01")
    malformed = {"event_id": "not-a-uuid", "store_id": "STORE_BLR_001"}
    r = await client.post("/events/ingest", json={"events": [valid, malformed]})
    assert r.status_code == 422


async def test_ingest_staff_event(client):
    event = make_event("ENTRY", visitor_id="VIS_staff01", is_staff=True)
    r = await client.post("/events/ingest", json={"events": [event]})
    assert r.status_code == 200
    assert r.json()["accepted"] == 1


async def test_ingest_empty_batch(client):
    r = await client.post("/events/ingest", json={"events": []})
    assert r.status_code == 200
    assert r.json()["accepted"] == 0


async def test_ingest_all_event_types(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_all01"),
        make_event("ZONE_ENTER", visitor_id="VIS_all01", zone_id="SKINCARE_WALL", camera_id="CAM_1"),
        make_event("ZONE_DWELL", visitor_id="VIS_all01", zone_id="SKINCARE_WALL", dwell_ms=35000),
        make_event("ZONE_EXIT", visitor_id="VIS_all01", zone_id="SKINCARE_WALL"),
        make_event("BILLING_QUEUE_JOIN", visitor_id="VIS_all01", zone_id="BILLING_ZONE", queue_depth=2),
        make_event("BILLING_QUEUE_ABANDON", visitor_id="VIS_all01", zone_id="BILLING_ZONE"),
        make_event("REENTRY", visitor_id="VIS_all01"),
        make_event("EXIT", visitor_id="VIS_all01"),
    ]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.status_code == 200
    assert r.json()["accepted"] == 8


async def test_ingest_dedup_multiple(client):
    event_id = str(uuid.uuid4())
    event = make_event("ENTRY", visitor_id="VIS_dedup01")
    event["event_id"] = event_id

    await client.post("/events/ingest", json={"events": [event]})
    await client.post("/events/ingest", json={"events": [event]})
    r = await client.post("/events/ingest", json={"events": [event]})
    assert r.json()["duplicates"] == 1
    assert r.json()["accepted"] == 0