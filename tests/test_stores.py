# PROMPT: Generate pytest async tests for heatmap and store edge cases.
# Cover: heatmap structure, score range, data_confidence flag, staff exclusion.
# CHANGES MADE: Updated store ID to ST1008.

import pytest
from tests.conftest import make_event

pytestmark = pytest.mark.asyncio


async def test_heatmap_empty_store(client):
    r = await client.get("/stores/STORE_EMPTY/heatmap")
    assert r.status_code == 200
    body = r.json()
    assert body["zones"] == []
    assert body["data_confidence"] == "LOW"


async def test_heatmap_returns_zones(client):
    events = [
        make_event("ZONE_ENTER", visitor_id="VIS_hm01", zone_id="SKINCARE_WALL", camera_id="CAM_1"),
        make_event("ZONE_ENTER", visitor_id="VIS_hm01", zone_id="MAKEUP_TABLE", camera_id="CAM_1"),
        make_event("ZONE_DWELL", visitor_id="VIS_hm01", zone_id="SKINCARE_WALL", dwell_ms=45000),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/heatmap")
    body = r.json()
    assert len(body["zones"]) >= 1
    zone_ids = [z["zone_id"] for z in body["zones"]]
    assert "SKINCARE_WALL" in zone_ids


async def test_heatmap_score_range(client):
    events = [
        make_event("ZONE_ENTER", visitor_id="VIS_hm02", zone_id="SKINCARE_WALL", camera_id="CAM_1"),
        make_event("ZONE_ENTER", visitor_id="VIS_hm03", zone_id="GOODVIBES_ZONE", camera_id="CAM_3"),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/heatmap")
    for zone in r.json()["zones"]:
        assert 0 <= zone["score"] <= 100


async def test_heatmap_top_zone_score_100(client):
    events = [
        make_event("ZONE_ENTER", visitor_id="VIS_hm04", zone_id="SKINCARE_WALL", camera_id="CAM_1"),
        make_event("ZONE_ENTER", visitor_id="VIS_hm05", zone_id="SKINCARE_WALL", camera_id="CAM_1"),
        make_event("ZONE_ENTER", visitor_id="VIS_hm06", zone_id="GOODVIBES_ZONE", camera_id="CAM_3"),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/heatmap")
    zones = r.json()["zones"]
    assert zones[0]["score"] == 100


async def test_heatmap_data_confidence_low(client):
    events = [make_event("ZONE_ENTER", visitor_id=f"VIS_hm{i:02d}", zone_id="SKINCARE_WALL") for i in range(5)]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/heatmap")
    assert r.json()["data_confidence"] == "LOW"


async def test_heatmap_staff_excluded(client):
    events = [
        make_event("ZONE_ENTER", visitor_id="VIS_cust01", zone_id="SKINCARE_WALL", is_staff=False),
        make_event("ZONE_ENTER", visitor_id="VIS_stf01", zone_id="SKINCARE_WALL", is_staff=True),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/heatmap")
    skincare = next((z for z in r.json()["zones"] if z["zone_id"] == "SKINCARE_WALL"), None)
    assert skincare is not None
    assert skincare["visits"] == 1