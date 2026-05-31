from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import EventRecord
from app.schemas import Event
from datetime import timezone
import logging

logger = logging.getLogger(__name__)


async def ingest_batch(events: list[Event], db: AsyncSession) -> dict:
    accepted = 0
    duplicates = 0
    errors = 0
    error_details = []

    incoming_ids = [str(e.event_id) for e in events]
    existing = await db.execute(
        select(EventRecord.event_id).where(EventRecord.event_id.in_(incoming_ids))
    )
    existing_ids = set(existing.scalars().all())

    for event in events:
        try:
            event_id_str = str(event.event_id)
            if event_id_str in existing_ids:
                duplicates += 1
                continue

            ts = event.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            record = EventRecord(
                event_id=event_id_str,
                store_id=event.store_id,
                camera_id=event.camera_id,
                visitor_id=event.visitor_id,
                event_type=event.event_type,
                timestamp=ts,
                zone_id=event.zone_id,
                dwell_ms=event.dwell_ms,
                is_staff=event.is_staff,
                confidence=event.confidence,
                queue_depth=event.metadata.queue_depth,
                sku_zone=event.metadata.sku_zone,
                session_seq=event.metadata.session_seq,
            )
            db.add(record)
            accepted += 1

        except Exception as e:
            errors += 1
            error_details.append(str(e))
            logger.warning("Event rejected: %s", e)

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "errors": errors,
        "error_details": error_details,
    }