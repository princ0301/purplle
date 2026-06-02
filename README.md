# Store Intelligence API

End-to-end retail analytics pipeline that converts anonymized CCTV footage into
structured visitor events, then serves live store metrics through a FastAPI
service and browser dashboard.

Built for Purplle Tech Challenge 2026, Round 2.

## Live Demo

```text
https://store-intelligence-api-1047144688999.asia-south1.run.app
```

| Page | URL |
| --- | --- |
| Dashboard | `https://store-intelligence-api-1047144688999.asia-south1.run.app/dashboard` |
| API docs | `https://store-intelligence-api-1047144688999.asia-south1.run.app/docs` |
| Health | `https://store-intelligence-api-1047144688999.asia-south1.run.app/health` |
| Metrics | `https://store-intelligence-api-1047144688999.asia-south1.run.app/stores/ST1008/metrics` |

## Quick Start

```bash
git clone https://github.com/princ0301/purplle.git
cd purplle
docker compose up --build
curl http://localhost:8000/health
```

Open the local dashboard:

```text
http://localhost:8000/dashboard
```

SQLite is created automatically at `data/store_intelligence.db`.

## Run Without Docker

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/dashboard`.

## Detection Pipeline

Install the computer vision dependencies:

```bash
cd pipeline
pip install -r requirements.txt
```

Prepare store layout, POS transactions, and sample events from the raw POS CSV:

```bash
python prepare_data.py --raw-csv "../data/Brigade_Bangalore_10_April_26 (1)bc6219c.csv"
```

Start the API from the repository root:

```bash
cd ..
docker compose up -d
```

Process all CCTV clips and flush events into the API:

```bash
cd pipeline
run.bat
```

Run one clip manually:

```bash
python detect.py --video "../data/CCTV/CAM 1.mp4" --camera CAM_1 --layout "../data/store_layout.json" --output "../data/detected_events.jsonl" --api http://localhost:8000
```

Output events are written to `data/detected_events.jsonl`. When `--api` is
provided, the same events are posted to `POST /events/ingest`.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/events/ingest` | Batch ingest, up to 500 events, idempotent by `event_id` |
| GET | `/stores/{id}/metrics` | Unique visitors, conversion rate, dwell, queue, abandonment |
| GET | `/stores/{id}/funnel` | Entry to zone visit to billing to purchase funnel |
| GET | `/stores/{id}/heatmap` | Zone visit frequency and dwell, normalized 0-100 |
| GET | `/stores/{id}/anomalies` | Queue spike, dead zone, conversion drop |
| GET | `/health` | DB status, per-store last event time, stale feed warning |
| GET | `/dashboard` | Live browser dashboard |

Example:

```bash
curl http://localhost:8000/stores/ST1008/metrics
```

Unknown or empty stores return valid zero-valued JSON instead of crashing.

## Tests

```bash
pip install -r requirements.txt
pytest tests/ --cov=app --cov-report=term-missing
```

Expected result: 38 tests passing with at least 70% statement coverage.

## Provided Assertions

With the API running locally:

```bash
python data/assertions.py
```

## Environment Variables

Defaults are provided in code and in `docker-compose.yml`; `.env` is optional.

| Variable | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLite database URL | `sqlite+aiosqlite:///./data/store_intelligence.db` |
| `API_HOST` | Host to bind | `0.0.0.0` |
| `API_PORT` | Local API port | `8000` |
| `PORT` | Runtime port for hosted environments | unset locally |
| `LOG_LEVEL` | Logging level | `info` |
| `STORE_LAYOUT_PATH` | Store layout JSON path | `./data/store_layout.json` |
| `POS_DATA_PATH` | POS transactions CSV path | `./data/pos_transactions.csv` |
| `STALE_FEED_THRESHOLD_MINUTES` | Minutes before feed is stale | `10` |

## Project Structure

```text
purplle/
|-- app/                  FastAPI service, ingestion, metrics, anomalies
|-- dashboard/            Static live dashboard
|-- data/                 Store layout, POS data, sample events, assertions
|-- docs/                 DESIGN.md, CHOICES.md, demo notes, presentation
|-- pipeline/             Detection, tracking, event emission scripts
|-- tests/                Async API tests
|-- docker-compose.yml
|-- Dockerfile
`-- requirements.txt
```

## Detection Notes

- YOLOv8n detects people from CCTV frames.
- ByteTrack maintains movement tracks and visitor IDs.
- Camera-aware bounding box centroids map visitors to store zones.
- Upper-body color heuristics flag staff for exclusion from customer metrics.
- Dwell events are emitted every 30 seconds of continuous zone presence.
- POS timestamps are correlated with billing-zone activity to estimate conversion.

## Design Documents

- `docs/DESIGN.md`: architecture and AI-assisted decisions.
- `docs/CHOICES.md`: model, schema, and API trade-offs.
