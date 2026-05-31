# Store Intelligence API

End-to-end retail analytics pipeline — from raw CCTV footage to live store metrics.

Built for Purplle Tech Challenge 2026 — Round 2.

## Quick Start (5 commands)

```bash
git clone <your-repo-url> store-intelligence && cd store-intelligence
cp .env.example .env
docker compose build
docker compose up -d
curl http://localhost:8000/health
```

No database setup required. SQLite is created automatically on first run.

## Live Dashboard

Open in browser after `docker compose up`:

```
http://localhost:8000/dashboard
```

Shows live: unique visitors, conversion funnel, zone heatmap, anomalies — auto-refreshing every 5 seconds.

## Running the Detection Pipeline

Install pipeline dependencies:

```bash
cd pipeline
pip install -r requirements.txt
```

Prepare dataset from raw POS CSV:

```bash
python prepare_data.py --raw-csv "../data/Brigade_Bangalore_10_April_26.csv"
```

Process all CCTV clips and emit events to the API:

```bash
python detect.py --video "../data/CCTV/CAM 1.mp4" --camera CAM_1 --layout "../data/store_layout.json" --output "../data/detected_events.jsonl" --api http://localhost:8000

python detect.py --video "../data/CCTV/CAM 2.mp4" --camera CAM_2 --layout "../data/store_layout.json" --output "../data/detected_events.jsonl" --api http://localhost:8000

python detect.py --video "../data/CCTV/CAM 3.mp4" --camera CAM_3 --layout "../data/store_layout.json" --output "../data/detected_events.jsonl" --api http://localhost:8000

python detect.py --video "../data/CCTV/CAM 5.mp4" --camera CAM_5 --layout "../data/store_layout.json" --output "../data/detected_events.jsonl" --api http://localhost:8000
```

CAM_4 is a stockroom camera with no customer-facing activity — skipped by design.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/events/ingest` | Ingest up to 500 events. Idempotent by event_id. |
| GET | `/stores/{id}/metrics` | Unique visitors, conversion rate, dwell, queue depth |
| GET | `/stores/{id}/funnel` | Entry → Zone → Billing → Purchase with drop-off % |
| GET | `/stores/{id}/heatmap` | Zone visit frequency normalised 0–100 |
| GET | `/stores/{id}/anomalies` | Queue spike, dead zone, conversion drop |
| GET | `/health` | DB status, last event time, STALE_FEED warning |
| GET | `/dashboard` | Live web dashboard |

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ --cov=app --cov-report=term-missing
```

Expected: 38 passed, 70% coverage.

## Running Assertions

```bash
python data/assertions.py
```

Requires API running on `http://localhost:8000`.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite path | `sqlite+aiosqlite:///./data/store_intelligence.db` |
| `API_HOST` | Host to bind | `0.0.0.0` |
| `API_PORT` | Port | `8000` |
| `LOG_LEVEL` | Logging level | `info` |
| `STORE_LAYOUT_PATH` | Path to store layout JSON | `./data/store_layout.json` |
| `POS_DATA_PATH` | Path to POS transactions CSV | `./data/pos_transactions.csv` |
| `STALE_FEED_THRESHOLD_MINUTES` | Minutes before feed marked stale | `10` |

## Project Structure

```
store-intelligence/
├── pipeline/
│   ├── detect.py          # YOLOv8n detection + ByteTrack tracking
│   ├── tracker.py         # Track management and Re-ID
│   ├── emit.py            # Event schema emission
│   ├── prepare_data.py    # Dataset preparation from raw CSV
│   └── requirements.txt   # CV dependencies
├── app/
│   ├── main.py            # FastAPI app + structured logging middleware
│   ├── models.py          # SQLAlchemy ORM
│   ├── schemas.py         # Pydantic event schema
│   ├── database.py        # Async SQLite engine
│   ├── config.py          # Settings from .env
│   ├── ingestion.py       # Batch ingest with deduplication
│   ├── metrics.py         # Real-time metric computation
│   ├── funnel.py          # Conversion funnel logic
│   ├── anomalies.py       # Anomaly detection
│   └── routers/
│       ├── events.py      # POST /events/ingest
│       ├── stores.py      # GET /stores/{id}/*
│       └── health.py      # GET /health + GET /dashboard
├── tests/
│   ├── conftest.py
│   ├── test_ingest.py
│   ├── test_metrics.py
│   ├── test_funnel.py
│   ├── test_anomalies.py
│   ├── test_health.py
│   └── test_stores.py
├── dashboard/
│   └── index.html         # Live web dashboard
├── docs/
│   ├── DESIGN.md          # Architecture + AI-assisted decisions
│   └── CHOICES.md         # Model selection, schema design, API decisions
├── data/
│   ├── store_layout.json
│   ├── pos_transactions.csv
│   ├── sample_events.jsonl
│   └── assertions.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Detection Pipeline Notes

- **Model:** YOLOv8n — person class only, confidence threshold 0.35
- **Tracking:** supervision ByteTrack, processes every 3rd frame (10fps effective)
- **Staff detection:** HSV colour histogram on upper body — grey/white uniform = staff
- **Zone classification:** Normalised bounding box centroid mapped to zone regions per camera
- **Timestamps:** Clips are replayed as today's date starting at 10:00 UTC for real-time metric compatibility

## Architecture

See `docs/DESIGN.md` for full architecture overview and AI-assisted decisions.
See `docs/CHOICES.md` for model selection, schema design, and API architecture decisions.