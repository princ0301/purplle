from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventRecord


@dataclass(frozen=True)
class EventWindow:
    start: datetime
    end: datetime
    date: date
    is_fallback: bool


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _day_window(day: date, is_fallback: bool) -> EventWindow:
    return EventWindow(
        start=datetime.combine(day, time.min),
        end=datetime.combine(day, time.max),
        date=day,
        is_fallback=is_fallback,
    )


async def get_event_window(store_id: str, db: AsyncSession) -> EventWindow:
    today = datetime.now(timezone.utc).date()
    today_window = _day_window(today, is_fallback=False)

    today_count = await db.execute(
        select(func.count())
        .select_from(EventRecord)
        .where(EventRecord.store_id == store_id)
        .where(EventRecord.timestamp >= today_window.start)
        .where(EventRecord.timestamp <= today_window.end)
    )
    if today_count.scalar_one() > 0:
        return today_window

    latest = await db.execute(
        select(func.max(EventRecord.timestamp))
        .where(EventRecord.store_id == store_id)
    )
    latest_timestamp = latest.scalar_one_or_none()
    if latest_timestamp is None:
        return today_window

    return _day_window(_as_naive_utc(latest_timestamp).date(), is_fallback=True)
