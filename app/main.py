import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import events, health, stores
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialised")
    yield
    logger.info("Shutting down")


app = FastAPI(title="Store Intelligence API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    start = time.time()
    request.state.trace_id = trace_id

    response: Response = await call_next(request)

    latency_ms = round((time.time() - start) * 1000, 2)
    store_id = request.path_params.get("store_id", "-")

    logger.info(
        '{"trace_id":"%s","store_id":"%s","endpoint":"%s","method":"%s","latency_ms":%s,"status_code":%d}',
        trace_id, store_id, request.url.path, request.method, latency_ms, response.status_code,
    )
    response.headers["X-Trace-Id"] = trace_id
    return response


app.include_router(events.router, tags=["events"])
app.include_router(health.router, tags=["health"])
app.include_router(stores.router, tags=["stores"])
