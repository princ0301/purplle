import json
import uuid
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict


DWELL_EMIT_INTERVAL_MS = 30000


class EventEmitter:
    def __init__(self, store_id: str, camera_id: str, output_path: str, api_url: str = None):
        self.store_id = store_id
        self.camera_id = camera_id
        self.output_path = output_path
        self.api_url = api_url
        self.events: list[dict] = []
        self.event_count = 0

        self.active_tracks: dict[int, dict] = {}
        self.visitor_map: dict[int, str] = {}
        self.exited_visitors: set[str] = set()
        self.zone_entry_time: dict[int, datetime] = {}
        self.last_dwell_emit: dict[int, datetime] = {}
        self.current_zone: dict[int, str] = {}
        self.session_seq: dict[str, int] = defaultdict(int)

        self._out_file = open(output_path, 'a')

    def _visitor_id(self, track_id: int) -> str:
        if track_id not in self.visitor_map:
            self.visitor_map[track_id] = "VIS_" + uuid.uuid4().hex[:6]
        return self.visitor_map[track_id]

    def _seq(self, visitor_id: str) -> int:
        seq = self.session_seq[visitor_id]
        self.session_seq[visitor_id] += 1
        return seq

    def _make_event(self, event_type: str, visitor_id: str, zone_id=None,
                    dwell_ms=0, confidence=0.9, is_staff=False,
                    timestamp=None, queue_depth=None, sku_zone=None) -> dict:
        return {
            "event_id": str(uuid.uuid4()),
            "store_id": self.store_id,
            "camera_id": self.camera_id,
            "visitor_id": visitor_id,
            "event_type": event_type,
            "timestamp": (timestamp or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "zone_id": zone_id,
            "dwell_ms": dwell_ms,
            "is_staff": bool(is_staff),
            "confidence": round(confidence, 3),
            "metadata": {
                "queue_depth": queue_depth,
                "sku_zone": sku_zone,
                "session_seq": self._seq(visitor_id),
            }
        }

    def _emit(self, event: dict):
        self.events.append(event)
        self._out_file.write(json.dumps(event) + '\n')
        self._out_file.flush()
        self.event_count += 1

    def process_detection(self, track_id: int, bbox: list, confidence: float,
                          zone_id: str, is_staff: bool, timestamp: datetime,
                          camera_id: str, frame_shape: tuple):
        visitor_id = self._visitor_id(track_id)
        h = frame_shape[0]

        # ENTRY — new track on entry camera
        if track_id not in self.active_tracks:
            self.active_tracks[track_id] = {
                "first_seen": timestamp,
                "bbox": bbox,
                "is_staff": is_staff,
            }
            if camera_id in {"CAM_2"}:
                event_type = "REENTRY" if visitor_id in self.exited_visitors else "ENTRY"
                event = self._make_event(event_type, visitor_id,
                                         confidence=confidence, is_staff=is_staff,
                                         timestamp=timestamp)
                self._emit(event)

        # Zone tracking
        prev_zone = self.current_zone.get(track_id)

        if zone_id and zone_id != prev_zone:
            # ZONE_EXIT from previous zone
            if prev_zone:
                entry_time = self.zone_entry_time.get(track_id, timestamp)
                dwell_ms = int((timestamp - entry_time).total_seconds() * 1000)
                exit_evt = self._make_event("ZONE_EXIT", visitor_id, zone_id=prev_zone,
                                            dwell_ms=dwell_ms, confidence=confidence,
                                            is_staff=is_staff, timestamp=timestamp)
                self._emit(exit_evt)

            # ZONE_ENTER new zone
            self.current_zone[track_id] = zone_id
            self.zone_entry_time[track_id] = timestamp
            self.last_dwell_emit[track_id] = timestamp

            enter_evt = self._make_event("ZONE_ENTER", visitor_id, zone_id=zone_id,
                                         confidence=confidence, is_staff=is_staff,
                                         timestamp=timestamp)
            self._emit(enter_evt)

            # BILLING_QUEUE_JOIN
            if zone_id == "BILLING_ZONE" and not is_staff:
                queue_depth = self._estimate_queue_depth(timestamp)
                if queue_depth > 0:
                    q_evt = self._make_event("BILLING_QUEUE_JOIN", visitor_id,
                                             zone_id=zone_id, confidence=confidence,
                                             is_staff=False, timestamp=timestamp,
                                             queue_depth=queue_depth)
                    self._emit(q_evt)

        # ZONE_DWELL — every 30s of continuous dwell
        if zone_id and track_id in self.zone_entry_time:
            entry_time = self.zone_entry_time[track_id]
            last_dwell = self.last_dwell_emit.get(track_id, entry_time)
            elapsed_ms = int((timestamp - entry_time).total_seconds() * 1000)
            since_last = int((timestamp - last_dwell).total_seconds() * 1000)

            if elapsed_ms >= DWELL_EMIT_INTERVAL_MS and since_last >= DWELL_EMIT_INTERVAL_MS:
                dwell_evt = self._make_event("ZONE_DWELL", visitor_id, zone_id=zone_id,
                                             dwell_ms=elapsed_ms, confidence=confidence,
                                             is_staff=is_staff, timestamp=timestamp)
                self._emit(dwell_evt)
                self.last_dwell_emit[track_id] = timestamp

    def _estimate_queue_depth(self, timestamp: datetime) -> int:
        window_start = timestamp - timedelta(seconds=60)
        in_billing = sum(
            1 for tid, info in self.active_tracks.items()
            if self.current_zone.get(tid) == "BILLING_ZONE"
            and not info.get("is_staff", False)
        )
        return max(0, in_billing)

    def finalize(self, clip_end_timestamp: datetime):
        for track_id, info in self.active_tracks.items():
            visitor_id = self._visitor_id(track_id)
            is_staff = info.get("is_staff", False)
            zone = self.current_zone.get(track_id)

            if zone:
                entry_time = self.zone_entry_time.get(track_id, info["first_seen"])
                dwell_ms = int((clip_end_timestamp - entry_time).total_seconds() * 1000)
                self._emit(self._make_event("ZONE_EXIT", visitor_id, zone_id=zone,
                                            dwell_ms=dwell_ms, is_staff=is_staff,
                                            timestamp=clip_end_timestamp))

            self._emit(self._make_event("EXIT", visitor_id, is_staff=is_staff,
                                        timestamp=clip_end_timestamp))
            self.exited_visitors.add(visitor_id)

        self._out_file.close()

    def flush_to_api(self, batch_size: int = 100):
        if not self.api_url or not self.events:
            return
        import requests
        for i in range(0, len(self.events), batch_size):
            batch = self.events[i:i + batch_size]
            try:
                r = requests.post(
                    f"{self.api_url}/events/ingest",
                    json={"events": batch},
                    timeout=10
                )
                print(f"  Flushed {len(batch)} events → {r.status_code}")
            except Exception as e:
                print(f"  Flush failed: {e}")