import cv2
import json
import uuid
import numpy as np
from datetime import datetime, timezone, timedelta
from ultralytics import YOLO
import supervision as sv

from tracker import Tracker
from emit import EventEmitter


CAMERA_ZONE_MAP = {
    "CAM_1": ["SKINCARE_WALL", "MAKEUP_TABLE", "FLOOR_CENTER", "BILLING_ZONE"],
    "CAM_2": ["ENTRY_ZONE", "FLOOR_CENTER"],
    "CAM_3": ["FACESHOP_ZONE", "GOODVIBES_ZONE", "DERMA_ZONE"],
    "CAM_4": ["STOCKROOM"],
    "CAM_5": ["FLOOR_CENTER", "ROTATING_STAND", "MAKEUP_TABLE"],
}


def load_store_layout(layout_path: str) -> dict:
    with open(layout_path) as f:
        return json.load(f)


def get_clip_start_time(video_path: str, layout: dict) -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=10, minute=0, second=0, microsecond=0)


def frame_to_timestamp(clip_start: datetime, frame_idx: int, fps: float) -> datetime:
    return clip_start + timedelta(seconds=frame_idx / fps)


def detect_staff(frame: np.ndarray, bbox: list) -> bool:
    x1, y1, x2, y2 = [int(v) for v in bbox]
    h = y2 - y1
    upper_y2 = y1 + int(h * 0.5)
    upper_body = frame[y1:upper_y2, x1:x2]
    if upper_body.size == 0:
        return False
    hsv = cv2.cvtColor(upper_body, cv2.COLOR_BGR2HSV)
    gray_mask = cv2.inRange(hsv, np.array([0, 0, 150]), np.array([180, 40, 255]))
    ratio = np.sum(gray_mask > 0) / max(gray_mask.size, 1)
    return ratio > 0.45


def get_zone_for_bbox(bbox: list, camera_id: str, frame_shape: tuple) -> str | None:
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    h, w = frame_shape[:2]
    nx = cx / w
    ny = cy / h

    if camera_id == "CAM_1":
        if nx < 0.35:
            return "SKINCARE_WALL"
        elif nx > 0.75 and ny < 0.5:
            return "BILLING_ZONE"
        elif nx > 0.70 and ny >= 0.5:
            return "MAKEUP_TABLE"
        return "FLOOR_CENTER"

    if camera_id == "CAM_2":
        if ny > 0.7:
            return "ENTRY_ZONE"
        return "FLOOR_CENTER"

    if camera_id == "CAM_3":
        if nx < 0.33:
            return "FACESHOP_ZONE"
        elif nx < 0.66:
            return "GOODVIBES_ZONE"
        return "DERMA_ZONE"

    if camera_id == "CAM_4":
        return "STOCKROOM"

    if camera_id == "CAM_5":
        if 0.4 < nx < 0.6 and 0.4 < ny < 0.6:
            return "ROTATING_STAND"
        return "FLOOR_CENTER"

    zones = CAMERA_ZONE_MAP.get(camera_id, [])
    return zones[0] if zones else None


def process_video(
    video_path: str,
    camera_id: str,
    store_id: str,
    layout: dict,
    output_path: str,
    api_url: str = None,
    conf_threshold: float = 0.35,
):
    if camera_id == "CAM_4":
        print(f"Skipping {camera_id} — stockroom camera, not customer-facing")
        return 0

    model = YOLO("yolov8n.pt")
    tracker = Tracker()
    emitter = EventEmitter(
        store_id=store_id,
        camera_id=camera_id,
        output_path=output_path,
        api_url=api_url,
    )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    clip_start = get_clip_start_time(video_path, layout)
    frame_idx = 0
    skip_frames = 3

    print(f"Processing {camera_id} — {video_path} ({total_frames} frames @ {fps:.1f}fps)")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        if frame_idx % skip_frames != 0:
            continue

        timestamp = frame_to_timestamp(clip_start, frame_idx, fps)
        results = model(frame, classes=[0], conf=conf_threshold, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)

        if len(detections) == 0:
            tracker.update_empty(timestamp)
            continue

        tracked = tracker.update(detections, frame, timestamp)

        for track_id, bbox, confidence in tracked:
            is_staff = bool(detect_staff(frame, bbox))
            zone = get_zone_for_bbox(bbox, camera_id, frame.shape)
            emitter.process_detection(
                track_id=track_id,
                bbox=bbox,
                confidence=confidence,
                zone_id=zone,
                is_staff=is_staff,
                timestamp=timestamp,
                camera_id=camera_id,
                frame_shape=frame.shape,
            )

    cap.release()
    emitter.finalize(
        clip_end_timestamp=frame_to_timestamp(clip_start, frame_idx, fps)
    )

    if api_url:
        emitter.flush_to_api()

    print(f"Done {camera_id} — {emitter.event_count} events emitted")
    return emitter.event_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run person detection on a CCTV clip")
    parser.add_argument('--video', required=True, help='Path to video file')
    parser.add_argument('--camera', required=True, help='Camera ID e.g. CAM_1')
    parser.add_argument('--layout', default='../data/store_layout.json')
    parser.add_argument('--output', default='../data/detected_events.jsonl')
    parser.add_argument('--api', default=None, help='API base URL to flush events')
    parser.add_argument('--conf', type=float, default=0.35)
    args = parser.parse_args()

    layout = load_store_layout(args.layout)
    store_id = layout['store_id']

    process_video(
        video_path=args.video,
        camera_id=args.camera,
        store_id=store_id,
        layout=layout,
        output_path=args.output,
        api_url=args.api,
        conf_threshold=args.conf,
    )