# Store Intelligence System — Architecture Overview

## System Summary

This system ingests raw CCTV footage from a physical retail store and produces
real-time business analytics via a REST API. The pipeline runs in two stages:
batch detection from video clips, and live querying of computed metrics.

## Pipeline Architecture

```
CCTV Clips (MP4)
      │
      ▼
Detection Layer (pipeline/)
  - YOLOv8n person detection per frame
  - ByteTrack multi-object tracking
  - Zone classification via bounding box position
  - Staff detection via upper-body colour histogram
  - Event schema emission (ENTRY, EXIT, ZONE_ENTER, ZONE_DWELL, etc.)
      │
      ▼
POST /events/ingest (batch, idempotent)
      │
      ▼
SQLite Database (data/store_intelligence.db)
      │
      ▼
Intelligence API (app/)
  - /metrics   → unique visitors, conversion rate, dwell, queue
  - /funnel    → Entry → Zone → Billing → Purchase
  - /heatmap   → zone visit frequency normalised 0-100
  - /anomalies → queue spike, dead zone, conversion drop
  - /health    → db status, stale feed detection
```

## Component Breakdown

### Detection Layer

**`pipeline/detect.py`** — Main orchestration. Reads video frames, runs YOLOv8n
inference every 3rd frame (10fps effective), maps detections to store zones
using normalised bounding box centroids, calls tracker and emitter.

**`pipeline/tracker.py`** — Wraps supervision ByteTrack. Maintains track
history for direction inference. Each track_id maps to a persistent visitor_id
via the emitter.

**`pipeline/emit.py`** — Stateful event emitter. Tracks zone entry times,
emits ZONE_DWELL every 30 seconds of continuous presence, handles
BILLING_QUEUE_JOIN when multiple visitors are in billing zone simultaneously,
emits EXIT for all active tracks at clip end.

**`pipeline/prepare_data.py`** — Data preparation script. Converts raw POS CSV
(line-item format) to transaction-level format, generates store_layout.json
from store metadata, regenerates sample_events.jsonl with today's timestamps.

### Intelligence API

Built with FastAPI + async SQLAlchemy + SQLite.

**`app/ingestion.py`** — Batch ingest with event_id deduplication. Safe to
call multiple times with the same payload.

**`app/metrics.py`** — Queries today's non-staff events. Conversion rate
computed by correlating billing zone presence with POS transaction timestamps
using a 5-minute window.

**`app/funnel.py`** — Session-based funnel. Each unique visitor_id counted
once per stage. REENTRY events do not create new visitor counts.

**`app/anomalies.py`** — Three anomaly types: BILLING_QUEUE_SPIKE (queue depth
threshold), DEAD_ZONE (no zone activity in 30 minutes), CONVERSION_DROP
(today vs 7-day average).

**`app/routers/health.py`** — Checks last event timestamp per store. Flags
STALE_FEED if no events received in the last 10 minutes.

### Production Features

- Structured JSON logging on every request with trace_id, store_id, endpoint,
  latency_ms, status_code
- HTTP 503 with structured body on database failure
- Idempotent ingest via event_id primary key
- Docker single-command deployment: `docker compose up`
- 38 tests, 70% statement coverage

## AI-Assisted Decisions

### 1. Zone Classification Approach

I consulted Claude on whether to use a VLM (GPT-4V or Claude Vision) for zone
classification versus a rule-based bounding box approach. The AI suggested
VLM-based classification would be more accurate but introduced latency and cost
per frame. I agreed with its reasoning and chose rule-based classification using
normalised bounding box centroids mapped to zone polygons. For a 2.5-minute
clip at 10fps effective this is fast enough and fully deterministic.

### 2. Database Choice

I asked Claude to evaluate SQLite vs PostgreSQL for this challenge. It correctly
identified that SQLite is sufficient for the event volumes involved (under 10k
events per store per day) and eliminates operational complexity. The tradeoff
is that SQLite does not support concurrent writes from multiple detection
processes. I documented this and mitigated it by running detection sequentially
per camera.

### 3. Staff Detection Strategy

I used Claude to evaluate torchreid-based re-identification versus colour
histogram staff detection. The AI noted that torchreid requires a labelled
staff gallery which we do not have. I overrode its initial suggestion of
semi-supervised re-ID and chose HSV colour histogram on the upper body region
instead, specifically targeting the grey/white uniform colours visible in
CAM_1. This is fast, requires no training data, and is explainable.