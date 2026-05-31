from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import IngestRequest, IngestResponse
from app.ingestion import ingest_batch
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/events/ingest", response_model=IngestResponse)
async def ingest_events(payload: IngestRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await ingest_batch(payload.events, db)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("Ingest failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail={"error": "Database unavailable", "message": str(e)}
        )
    return IngestResponse(**result)