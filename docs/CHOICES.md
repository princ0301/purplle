# Engineering Decisions

## Decision 1 — Detection Model: YOLOv8n

### Options Considered
- YOLOv8n (nano) — fast, 6.2MB, 80 COCO classes
- YOLOv8s (small) — more accurate, 4x slower
- RT-DETR — transformer-based, higher accuracy, much slower
- MediaPipe — lightweight but weaker on partial occlusion

### What AI Suggested
Claude suggested YOLOv8s as a better accuracy/speed tradeoff for retail
environments with partial occlusion. It noted that YOLOv8n can miss partially
occluded persons near shelf edges.

### What I Chose and Why
YOLOv8n. The clips are 2.5 minutes at 1080p. On CPU, YOLOv8s takes ~3x longer
per frame. For a take-home challenge running on a laptop, YOLOv8n completes all
5 clips in under 10 minutes total. The detection accuracy is acceptable for
person-class detection in a well-lit retail environment. I process every 3rd
frame (10fps effective) to balance speed and tracking continuity.

The confidence threshold is set at 0.35 rather than the default 0.5 to capture
partial occlusions — low-confidence detections are flagged in the confidence
field rather than dropped.

---

## Decision 2 — Event Schema Design

### Options Considered
- Flat schema with all fields at top level
- Nested metadata object for optional fields
- Separate tables for different event types

### What AI Suggested
Claude suggested a fully flat schema for query performance, arguing that JSON
metadata fields are harder to index. It also suggested separate tables per
event type for type safety.

### What I Chose and Why
Single table with a nested metadata object for optional fields (queue_depth,
sku_zone, session_seq). The reasons:

1. The query patterns are always by store_id + timestamp + event_type — a
   single table with these indexes covers all API endpoints efficiently.
2. Separate tables would require joins for any cross-event-type query such as
   the funnel, which needs ENTRY, ZONE_ENTER, and BILLING_ZONE events together.
3. The metadata fields are genuinely optional and sparse — embedding them in
   the main row as nullable columns (as we do) is a reasonable compromise
   between the flat and nested approaches.

I disagreed with the AI on flat schema because the challenge schema explicitly
specifies a metadata object, and matching the spec exactly is important for
the automated test harness.

---

## Decision 3 — API Architecture: Synchronous Query vs Pre-computed Aggregates

### Options Considered
- Pre-compute metrics on ingest and store aggregates (fast reads, complex writes)
- Query raw events on every API call (simple writes, potentially slow reads)
- Hybrid: cache aggregates with TTL

### What AI Suggested
Claude recommended pre-computing aggregates on ingest for production scale,
arguing that querying raw events at 40 stores in real time would not scale.
It suggested a materialised view pattern updated on each ingest batch.

### What I Chose and Why
Query raw events on every API call. For this challenge the event volume is
under 10k events per store per day. SQLite with indexed timestamp and store_id
columns handles these queries in under 5ms in testing.

The pre-compute approach would add significant complexity: invalidation logic,
aggregate storage schema, handling of late-arriving events and re-ingestion.
The challenge explicitly tests idempotency — pre-computed aggregates make
idempotent re-ingestion much harder to implement correctly.

I noted the AI's point in DESIGN.md as a valid production concern. At 40 live
stores sending events continuously, the first thing that breaks is the raw
query approach — I would migrate to pre-computed aggregates at that scale.
This is exactly the kind of decision I would document and revisit.