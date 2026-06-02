from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import EventRecord
from app.time_windows import get_event_window
from datetime import datetime, timedelta
import csv
import os
import logging

logger = logging.getLogger(__name__)


async def get_metrics(store_id: str, db: AsyncSession) -> dict:
    window = await get_event_window(store_id, db)

    result = await db.execute(
        select(EventRecord)
        .where(EventRecord.store_id == store_id)
        .where(EventRecord.is_staff.is_(False))
        .where(EventRecord.timestamp >= window.start)
        .where(EventRecord.timestamp <= window.end)
    )
    events = result.scalars().all()

    if not events:
        return {
            "store_id": store_id,
            "date": window.date.isoformat(),
            "is_fallback": window.is_fallback,
            "unique_visitors": 0,
            "conversion_rate": 0.0,
            "avg_dwell_per_zone": {},
            "queue_depth": 0,
            "abandonment_rate": 0.0,
        }

    visitor_ids = set(e.visitor_id for e in events if e.event_type == "ENTRY")
    unique_visitors = len(visitor_ids)

    zone_dwells: dict[str, list[int]] = {}
    for e in events:
        if e.event_type == "ZONE_DWELL" and e.zone_id and e.dwell_ms > 0:
            zone_dwells.setdefault(e.zone_id, []).append(e.dwell_ms)

    avg_dwell = {
        zone: round(sum(dwells) / len(dwells) / 1000, 1)
        for zone, dwells in zone_dwells.items()
    }

    queue_events = [e for e in events if e.event_type == "BILLING_QUEUE_JOIN" and e.queue_depth is not None]
    current_queue = queue_events[-1].queue_depth if queue_events else 0

    joins = len([e for e in events if e.event_type == "BILLING_QUEUE_JOIN"])
    abandons = len([e for e in events if e.event_type == "BILLING_QUEUE_ABANDON"])
    abandonment_rate = round(abandons / joins, 4) if joins > 0 else 0.0

    conversion_rate = await _compute_conversion_rate(store_id, events, unique_visitors)

    return {
        "store_id": store_id,
        "date": window.date.isoformat(),
        "is_fallback": window.is_fallback,
        "unique_visitors": unique_visitors,
        "conversion_rate": conversion_rate,
        "avg_dwell_per_zone": avg_dwell,
        "queue_depth": current_queue,
        "abandonment_rate": abandonment_rate,
    }


async def _compute_conversion_rate(store_id: str, events: list, unique_visitors: int) -> float:
    if unique_visitors == 0:
        return 0.0

    pos_path = os.getenv("POS_DATA_PATH", "./data/pos_transactions.csv")
    if not os.path.exists(pos_path):
        return 0.0

    transactions = []
    with open(pos_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["store_id"] == store_id:
                try:
                    ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                    ts = ts.replace(tzinfo=None)
                    transactions.append(ts)
                except Exception:
                    continue

    if not transactions:
        return 0.0

    billing_events = [
        e for e in events
        if e.zone_id == "BILLING_ZONE" and e.event_type in ("ZONE_ENTER", "ZONE_DWELL")
    ]

    converted_visitors = set()
    for txn_time in transactions:
        window_start = txn_time - timedelta(minutes=5)
        for e in billing_events:
            ts = e.timestamp
            if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            if window_start <= ts <= txn_time:
                converted_visitors.add(e.visitor_id)

    return round(len(converted_visitors) / unique_visitors, 4)
