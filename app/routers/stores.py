from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import EventRecord
from app.metrics import get_metrics
from app.funnel import get_funnel
from app.anomalies import get_anomalies
from datetime import datetime, timezone

router = APIRouter()


@router.get("/stores/{store_id}/metrics")
async def store_metrics(store_id: str, db: AsyncSession = Depends(get_db)):
    return await get_metrics(store_id, db)


@router.get("/stores/{store_id}/funnel")
async def store_funnel(store_id: str, db: AsyncSession = Depends(get_db)):
    return await get_funnel(store_id, db)


@router.get("/stores/{store_id}/heatmap")
async def store_heatmap(store_id: str, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    result = await db.execute(
        select(EventRecord)
        .where(EventRecord.store_id == store_id)
        .where(EventRecord.is_staff == False)
        .where(EventRecord.event_type.in_(["ZONE_ENTER", "ZONE_DWELL"]))
        .where(EventRecord.zone_id != None)
        .where(EventRecord.timestamp >= today_start)
    )
    events = result.scalars().all()

    zone_data: dict[str, dict] = {}
    for e in events:
        z = e.zone_id
        if z not in zone_data:
            zone_data[z] = {"visits": 0, "total_dwell_ms": 0, "sku_zone": e.sku_zone}
        if e.event_type == "ZONE_ENTER":
            zone_data[z]["visits"] += 1
        if e.event_type == "ZONE_DWELL" and e.dwell_ms:
            zone_data[z]["total_dwell_ms"] += e.dwell_ms

    if not zone_data:
        return {"store_id": store_id, "zones": [], "data_confidence": "LOW"}

    max_visits = max(z["visits"] for z in zone_data.values()) or 1
    total_sessions = len(set(e.visitor_id for e in events))
    confidence = "LOW" if total_sessions < 20 else "HIGH"

    zones = []
    for zone_id, data in zone_data.items():
        avg_dwell_s = round(data["total_dwell_ms"] / max(data["visits"], 1) / 1000, 1)
        score = round((data["visits"] / max_visits) * 100)
        zones.append({
            "zone_id": zone_id,
            "sku_zone": data["sku_zone"],
            "visits": data["visits"],
            "avg_dwell_seconds": avg_dwell_s,
            "score": score,
        })

    zones.sort(key=lambda z: z["score"], reverse=True)

    return {"store_id": store_id, "zones": zones, "data_confidence": confidence}


@router.get("/stores/{store_id}/anomalies")
async def store_anomalies(store_id: str, db: AsyncSession = Depends(get_db)):
    return await get_anomalies(store_id, db)