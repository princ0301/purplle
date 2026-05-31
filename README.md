# Store Intelligence API

End-to-end retail analytics pipeline from raw CCTV footage to live store metrics.

Built for Purplle Tech Challenge 2026, Round 2.

## Quick Start

Run the API from a clean clone:

```bash
git clone <your-repo-url> store-intelligence
cd store-intelligence
docker compose build
docker compose up -d
curl http://localhost:8000/health
```

No separate database setup is required. SQLite is created automatically in
`data/store_intelligence.db`.

## Live Dashboard

Open after `docker compose up`:

```text
http://localhost:8000/dashboard
```

The dashboard refreshes every 5 seconds and shows unique visitors, conversion
funnel, zone heatmap, queue status, and anomalies.

## Running the Detection Pipeline

Install CV dependencies:

```bash
cd pipeline
pip install -r requirements.txt
```

Prepare data files from the provided raw POS CSV:

```bash
python prepare_data.py --raw-csv "../data/Brigade_Bangalore_10_April_26 (1)bc6219c.csv"
```

Start the API:

```bash
cd ..
docker compose up -d
```

Process the CCTV clips and flush events into the API:

```bash
cd pipeline
run.bat
```

Or run a single clip manually:

```bash
python detect.py --video "../data/CCTV/CAM 1.mp4" --camera CAM_1 --layout "../data/store_layout.json" --output "../data/detected_events.jsonl" --api http://localhost:8000
```

The detector emits JSONL events to `data/detected_events.jsonl` and posts them
to `POST /events/ingest` when `--api` is provided.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/events/ingest` | Ingest up to 500 events, idempotent by `event_id` |
| GET | `/stores/{id}/metrics` | Unique visitors, conversion rate, dwell, queue depth |
| GET | `/stores/{id}/funnel` | Entry to zone to billing to purchase funnel |
| GET | `/stores/{id}/heatmap` | Zone visit frequency normalized 0-100 |
| GET | `/stores/{id}/anomalies` | Queue spike, dead zone, conversion drop |
| GET | `/health` | DB status, last event time, stale feed warning |
| GET | `/dashboard` | Live web dashboard |

Example:

```bash
curl http://localhost:8000/stores/ST1008/metrics
```

The API handles unknown or empty stores by returning valid zero-valued JSON
instead of crashing.

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ --cov=app --cov-report=term-missing
```

Current expected result: 38 tests passing with at least 70% statement coverage.

## Running Provided Assertions

```bash
python data/assertions.py
```

This expects the API to be running at `http://localhost:8000`.

## Environment Variables

Defaults are provided in code and in `docker-compose.yml`; `.env` is optional.
Use `.env.example` if you want to override settings locally.

| Variable | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLite database URL | `sqlite+aiosqlite:///./data/store_intelligence.db` |
| `API_HOST` | Host to bind | `0.0.0.0` |
| `API_PORT` | Port | `8000` |
| `LOG_LEVEL` | Logging level | `info` |
| `STORE_LAYOUT_PATH` | Store layout JSON path | `./data/store_layout.json` |
| `POS_DATA_PATH` | POS transactions CSV path | `./data/pos_transactions.csv` |
| `STALE_FEED_THRESHOLD_MINUTES` | Minutes before feed is stale | `10` |

## Project Structure

```text
store-intelligence/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── ingestion.py
│   ├── metrics.py
│   ├── funnel.py
│   ├── anomalies.py
│   └── routers/
├── dashboard/
│   ├── index.html
│   ├── style/style.css
│   └── script/script.js
├── data/
│   ├── store_layout.json
│   ├── pos_transactions.csv
│   ├── sample_events.jsonl
│   └── assertions.py
├── docs/
│   ├── DESIGN.md
│   └── CHOICES.md
├── pipeline/
│   ├── detect.py
│   ├── tracker.py
│   ├── emit.py
│   ├── prepare_data.py
│   ├── run.bat
│   └── requirements.txt
├── tests/
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Detection Pipeline Notes

- Model: YOLOv8n, person class only, low threshold to retain occluded detections.
- Tracking: ByteTrack through `supervision`, with track IDs mapped to visitor IDs.
- Zone classification: bounding box centroid mapped to configured camera zones.
- Staff detection: upper-body color heuristic for visible uniform colors.
- Timestamps: clip frame offsets are mapped to today's UTC date so API metrics
  work with real-time "today" windows.

## Design Documents

- `docs/DESIGN.md` explains the architecture and AI-assisted decisions.
- `docs/CHOICES.md` explains model selection, event schema design, and API
  architecture trade-offs.
