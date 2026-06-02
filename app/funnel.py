from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import EventRecord
from app.time_windows import get_event_window
from datetime import datetime, timedelta
import csv
import os


async def get_funnel(store_id: str, db: AsyncSession) -> dict:
    window = await get_event_window(store_id, db)

    result = await db.execute(
        select(EventRecord)
        .where(EventRecord.store_id == store_id)
        .where(EventRecord.is_staff.is_(False))
        .where(EventRecord.timestamp >= window.start)
        .where(EventRecord.timestamp <= window.end)
        .order_by(EventRecord.timestamp)
    )
    events = result.scalars().all()

    entered = set()
    zone_visitors = set()
    billing_visitors = set()

    for e in events:
        if e.event_type == "ENTRY":
            entered.add(e.visitor_id)
        elif e.event_type == "ZONE_ENTER" and e.zone_id not in (None, "ENTRY_ZONE"):
            zone_visitors.add(e.visitor_id)
        if e.zone_id == "BILLING_ZONE":
            billing_visitors.add(e.visitor_id)

    purchased = await _visitors_who_purchased(store_id, billing_visitors, events)

    total = len(entered)

    def drop_off(current, previous):
        if previous == 0:
            return 0.0
        return round((previous - current) / previous, 4)

    stages = [
        {"stage": "entry", "label": "Store Entry", "visitors": total, "drop_off_pct": 0.0},
        {"stage": "zone_visit", "label": "Zone Visit", "visitors": len(zone_visitors), "drop_off_pct": drop_off(len(zone_visitors), total)},
        {"stage": "billing_queue", "label": "Billing Queue", "visitors": len(billing_visitors), "drop_off_pct": drop_off(len(billing_visitors), len(zone_visitors))},
        {"stage": "purchase", "label": "Purchase", "visitors": len(purchased), "drop_off_pct": drop_off(len(purchased), len(billing_visitors))},
    ]

    return {
        "store_id": store_id,
        "date": window.date.isoformat(),
        "is_fallback": window.is_fallback,
        "stages": stages,
        "overall_conversion": round(len(purchased) / total, 4) if total > 0 else 0.0,
    }


async def _visitors_who_purchased(store_id: str, billing_visitors: set, events: list) -> set:
    pos_path = os.getenv("POS_DATA_PATH", "./data/pos_transactions.csv")
    if not os.path.exists(pos_path) or not billing_visitors:
        return set()

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
        return set()

    billing_events = [
        e for e in events
        if e.visitor_id in billing_visitors and e.zone_id == "BILLING_ZONE"
    ]

    purchased = set()
    for txn_time in transactions:
        window_start = txn_time - timedelta(minutes=5)
        for e in billing_events:
            ts = e.timestamp
            if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            if window_start <= ts <= txn_time:
                purchased.add(e.visitor_id)

    return purchased
