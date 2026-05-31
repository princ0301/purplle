from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.database import get_db
from app.schemas import HealthResponse, HealthStore
from app.models import EventRecord
from app.config import get_settings
from datetime import datetime, timezone, timedelta

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    db_connected = True
    store_statuses = []

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_connected = False
        return HealthResponse(status="degraded", stores=[], db_connected=False)

    result = await db.execute(
        select(EventRecord.store_id, func.max(EventRecord.timestamp).label("last_event"))
        .group_by(EventRecord.store_id)
    )
    rows = result.all()

    stale_threshold = timedelta(minutes=settings.stale_feed_threshold_minutes)
    now = datetime.now(timezone.utc)

    for store_id, last_event in rows:
        if last_event is None:
            status = "NO_DATA"
        elif (now - last_event.replace(tzinfo=timezone.utc)) > stale_threshold:
            status = "STALE_FEED"
        else:
            status = "OK"

        store_statuses.append(HealthStore(
            store_id=store_id,
            last_event_time=last_event,
            status=status,
        ))

    overall = "ok" if all(s.status == "OK" for s in store_statuses) else "degraded"

    return HealthResponse(
        status=overall,
        stores=store_statuses,
        db_connected=db_connected,
    )

from fastapi.responses import FileResponse
from fastapi import HTTPException
import os

@router.get("/dashboard", include_in_schema=False)
async def dashboard():
    base = os.environ.get("APP_BASE_DIR", "/app")
    path = os.path.join(base, "dashboard", "index.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Dashboard not found at {path}")
    return FileResponse(path)