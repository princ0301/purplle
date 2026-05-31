# PROMPT: Generate pytest async tests for GET /stores/{id}/funnel endpoint.
# Cover: empty store, stage structure, drop-off calculation, re-entry deduplication, all-staff clip.
# CHANGES MADE: Added re-entry test to verify visitor not double counted,
# added all-staff edge case, updated store ID to ST1008.

import pytest
from tests.conftest import make_event

pytestmark = pytest.mark.asyncio


async def test_funnel_empty_store(client):
    r = await client.get("/stores/STORE_EMPTY/funnel")
    assert r.status_code == 200
    body = r.json()
    assert body["overall_conversion"] == 0.0
    assert len(body["stages"]) == 4


async def test_funnel_stage_structure(client):
    r = await client.get("/stores/ST1008/funnel")
    stages = r.json()["stages"]
    stage_names = [s["stage"] for s in stages]
    assert stage_names == ["entry", "zone_visit", "billing_queue", "purchase"]


async def test_funnel_drop_off(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_f01"),
        make_event("ENTRY", visitor_id="VIS_f02"),
        make_event("ZONE_ENTER", visitor_id="VIS_f01", zone_id="SKINCARE_WALL"),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/funnel")
    stages = {s["stage"]: s for s in r.json()["stages"]}
    assert stages["entry"]["visitors"] == 2
    assert stages["zone_visit"]["visitors"] == 1
    assert stages["zone_visit"]["drop_off_pct"] == 0.5


async def test_funnel_reentry_no_double_count(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_re01"),
        make_event("EXIT", visitor_id="VIS_re01"),
        make_event("REENTRY", visitor_id="VIS_re01"),
        make_event("EXIT", visitor_id="VIS_re01"),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/funnel")
    stages = {s["stage"]: s for s in r.json()["stages"]}
    assert stages["entry"]["visitors"] == 1


async def test_funnel_all_staff_clip(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_st01", is_staff=True),
        make_event("ENTRY", visitor_id="VIS_st02", is_staff=True),
        make_event("ZONE_ENTER", visitor_id="VIS_st01", zone_id="BILLING_ZONE", is_staff=True),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/funnel")
    stages = {s["stage"]: s for s in r.json()["stages"]}
    assert stages["entry"]["visitors"] == 0


async def test_funnel_overall_conversion(client):
    events = [
        make_event("ENTRY", visitor_id="VIS_conv01"),
        make_event("ENTRY", visitor_id="VIS_conv02"),
        make_event("ZONE_ENTER", visitor_id="VIS_conv01", zone_id="BILLING_ZONE"),
        make_event("ZONE_ENTER", visitor_id="VIS_conv02", zone_id="BILLING_ZONE"),
    ]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get("/stores/ST1008/funnel")
    body = r.json()
    assert body["overall_conversion"] == 0.0