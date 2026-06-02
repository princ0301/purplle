from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import EventRecord
from app.time_windows import get_event_window
from datetime import datetime, timezone, timedelta


async def get_anomalies(store_id: str, db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window = await get_event_window(store_id, db)
    window_7d = window.start - timedelta(days=7)

    result = await db.execute(
        select(EventRecord)
        .where(EventRecord.store_id == store_id)
        .where(EventRecord.timestamp >= window.start)
        .where(EventRecord.timestamp <= window.end)
    )
    today_events = result.scalars().all()

    result_7d = await db.execute(
        select(EventRecord)
        .where(EventRecord.store_id == store_id)
        .where(EventRecord.is_staff.is_(False))
        .where(EventRecord.timestamp >= window_7d)
        .where(EventRecord.timestamp < window.start)
    )
    historical_events = result_7d.scalars().all()

    anomalies = []
    anomalies += _check_queue_spike(today_events, now)
    anomalies += _check_dead_zones(today_events, now - timedelta(minutes=30))
    anomalies += _check_conversion_drop(today_events, historical_events)

    return {
        "store_id": store_id,
        "date": window.date.isoformat(),
        "is_fallback": window.is_fallback,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "anomalies": anomalies,
    }


def _check_queue_spike(events: list, now: datetime) -> list:
    recent = [
        e for e in events
        if e.event_type == "BILLING_QUEUE_JOIN"
        and e.queue_depth is not None
        and e.timestamp >= now - timedelta(minutes=10)
    ]
    if not recent:
        return []

    max_depth = max(e.queue_depth for e in recent)

    if max_depth >= 5:
        severity = "CRITICAL"
    elif max_depth >= 3:
        severity = "WARN"
    else:
        return []

    return [{
        "anomaly_type": "BILLING_QUEUE_SPIKE",
        "severity": severity,
        "detail": f"Queue depth reached {max_depth} in the last 10 minutes",
        "suggested_action": "Open an additional billing counter or redirect customers.",
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }]


def _check_dead_zones(events: list, since: datetime) -> list:
    all_zones = set(e.zone_id for e in events if e.zone_id)
    recent_zones = set(e.zone_id for e in events if e.zone_id and e.timestamp >= since)
    dead = all_zones - recent_zones

    return [{
        "anomaly_type": "DEAD_ZONE",
        "severity": "INFO",
        "detail": f"No visits in zone {zone} for the last 30 minutes",
        "suggested_action": f"Check camera feed for {zone} or review product placement.",
        "detected_at": datetime.now(timezone.utc).isoformat(),
    } for zone in dead]


def _check_conversion_drop(today_events: list, historical_events: list) -> list:
    def conversion_rate(events):
        customer_events = [e for e in events if not e.is_staff]
        visitors = set(e.visitor_id for e in customer_events if e.event_type == "ENTRY")
        billing = set(e.visitor_id for e in customer_events if e.zone_id == "BILLING_ZONE")
        if not visitors:
            return None
        return len(billing) / len(visitors)

    today_rate = conversion_rate(today_events)
    hist_rate = conversion_rate(historical_events)

    if today_rate is None or hist_rate is None or hist_rate == 0:
        return []

    drop = (hist_rate - today_rate) / hist_rate

    if drop >= 0.3:
        severity = "CRITICAL"
    elif drop >= 0.15:
        severity = "WARN"
    else:
        return []

    return [{
        "anomaly_type": "CONVERSION_DROP",
        "severity": severity,
        "detail": f"Conversion rate dropped {round(drop * 100, 1)}% vs 7-day average ({round(hist_rate * 100, 1)}% → {round(today_rate * 100, 1)}%)",
        "suggested_action": "Review billing queue wait times and staff availability.",
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }]
