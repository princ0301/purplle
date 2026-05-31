import numpy as np
import supervision as sv
from datetime import datetime


class Tracker:
    def __init__(self, max_age: int = 30, min_hits: int = 2):
        self.byte_tracker = sv.ByteTrack(
            track_activation_threshold=0.35,
            lost_track_buffer=max_age,
            minimum_matching_threshold=0.8,
            frame_rate=10,
        )
        self.last_seen: dict[int, datetime] = {}
        self.track_history: dict[int, list] = {}

    def update(self, detections: sv.Detections, frame, timestamp: datetime) -> list[tuple]:
        tracked = self.byte_tracker.update_with_detections(detections)
        results = []

        for i in range(len(tracked)):
            track_id = int(tracked.tracker_id[i])
            bbox = tracked.xyxy[i].tolist()
            confidence = float(tracked.confidence[i]) if tracked.confidence is not None else 0.8

            self.last_seen[track_id] = timestamp

            if track_id not in self.track_history:
                self.track_history[track_id] = []
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            self.track_history[track_id].append((cx, cy, timestamp))

            results.append((track_id, bbox, confidence))

        return results

    def update_empty(self, timestamp: datetime):
        self.byte_tracker.update_with_detections(sv.Detections.empty())

    def get_direction(self, track_id: int, frame_height: float) -> str:
        history = self.track_history.get(track_id, [])
        if len(history) < 3:
            return "unknown"
        start_y = history[0][1]
        end_y = history[-1][1]
        delta = end_y - start_y
        if delta > frame_height * 0.05:
            return "entering"
        elif delta < -frame_height * 0.05:
            return "exiting"
        return "unknown"