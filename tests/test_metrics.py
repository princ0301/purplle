# PROMPT: Generate pytest async tests for GET /stores/{id}/metrics endpoint.
# Cover: zero traffic, unique visitors, staff exclusion, dwell computation, queue depth, abandonment.
# CHANGES MADE: Used make_event helper, tested staff exclusion explicitly,
# added edge case for store with no events. Updated store ID to ST1008.

import pytest
from tests.conftest import make_event
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.asyncio


async def test_metrics_empty_store(client):
    r = await client.get("/stores/STORE_EMPTY/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["unique_visitors"] == 0
    assert body["conversion_rate"] == 0.0


async def test_metrics_unique_visitors(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_m01"),
        make_event("ENTRY", visitor_id="VIS_m02"),
        make_event("ENTRY", visitor_id="VIS_m03"),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/metrics")
    assert r.json()["unique_visitors"] == 3


async def test_metrics_staff_excluded(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_cust01", is_staff=False),
        make_event("ENTRY", visitor_id="VIS_staff01", is_staff=True),
        make_event("ENTRY", visitor_id="VIS_staff02", is_staff=True),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/metrics")
    assert r.json()["unique_visitors"] == 1


async def test_metrics_required_fields(client):
    r = await client.get("/stores/ST1008/metrics")
    body = r.json()
    for field in ["unique_visitors", "conversion_rate", "avg_dwell_per_zone", "queue_depth", "abandonment_rate"]:
        assert field in body


async def test_metrics_queue_depth(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_q01"),
        make_event("BILLING_QUEUE_JOIN", visitor_id="VIS_q01", zone_id="BILLING_ZONE", queue_depth=4),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/metrics")
    assert r.json()["queue_depth"] == 4


async def test_metrics_abandonment_rate(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_ab01"),
        make_event("BILLING_QUEUE_JOIN", visitor_id="VIS_ab01", zone_id="BILLING_ZONE", queue_depth=2),
        make_event("BILLING_QUEUE_ABANDON", visitor_id="VIS_ab01", zone_id="BILLING_ZONE"),
        make_event("ENTRY", visitor_id="VIS_ab02"),
        make_event("BILLING_QUEUE_JOIN", visitor_id="VIS_ab02", zone_id="BILLING_ZONE", queue_depth=2),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/metrics")
    assert r.json()["abandonment_rate"] == 0.5


async def test_metrics_avg_dwell(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_dw01"),
        make_event("ZONE_DWELL", visitor_id="VIS_dw01", zone_id="SKINCARE_WALL", dwell_ms=60000),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/metrics")
    assert "SKINCARE_WALL" in r.json()["avg_dwell_per_zone"]


async def test_metrics_falls_back_to_latest_event_day(client):
    old_ts = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = [
        make_event("ENTRY", visitor_id="VIS_old01", timestamp=old_ts),
        make_event("ZONE_DWELL", visitor_id="VIS_old01", zone_id="SKINCARE_WALL", dwell_ms=45000, timestamp=old_ts),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/metrics")
    body = r.json()
    assert body["unique_visitors"] == 1
    assert body["is_fallback"] is True
