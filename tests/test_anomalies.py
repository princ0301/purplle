# PROMPT: Generate pytest async tests for GET /stores/{id}/anomalies endpoint.
# Cover: empty store, response structure, queue spike WARN, queue spike CRITICAL,
# dead zone detection, severity values.
# CHANGES MADE: Updated store ID to ST1008, verified suggested_action field present.

import pytest
from tests.conftest import make_event

pytestmark = pytest.mark.asyncio


async def test_anomalies_empty_store(client):
    r = await client.get("/stores/STORE_EMPTY/anomalies")
    assert r.status_code == 200
    assert r.json()["anomalies"] == []


async def test_anomalies_response_structure(client):
    r = await client.get("/stores/ST1008/anomalies")
    body = r.json()
    assert "store_id" in body
    assert "checked_at" in body
    assert "anomalies" in body


async def test_anomalies_queue_spike_warn(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_qs01"),
        make_event("BILLING_QUEUE_JOIN", visitor_id="VIS_qs01", zone_id="BILLING_ZONE", queue_depth=3),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/anomalies")
    anomalies = r.json()["anomalies"]
    queue_anomalies = [a for a in anomalies if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"]
    assert len(queue_anomalies) == 1
    assert queue_anomalies[0]["severity"] == "WARN"


async def test_anomalies_queue_spike_critical(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_qs02"),
        make_event("BILLING_QUEUE_JOIN", visitor_id="VIS_qs02", zone_id="BILLING_ZONE", queue_depth=6),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/anomalies")
    anomalies = r.json()["anomalies"]
    queue_anomalies = [a for a in anomalies if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"]
    assert queue_anomalies[0]["severity"] == "CRITICAL"


async def test_anomalies_severity_values(client):
    r = await client.get("/stores/ST1008/anomalies")
    for anomaly in r.json()["anomalies"]:
        assert anomaly["severity"] in ["INFO", "WARN", "CRITICAL"]


async def test_anomalies_suggested_action_present(client):
    events = [
        make_event("BILLING_QUEUE_JOIN", visitor_id="VIS_sa01", zone_id="BILLING_ZONE", queue_depth=5),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/anomalies")
    for anomaly in r.json()["anomalies"]:
        assert "suggested_action" in anomaly
        assert len(anomaly["suggested_action"]) > 0