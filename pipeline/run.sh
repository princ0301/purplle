#!/bin/bash

VIDEOS_DIR="${1:-../data/CCTV}"
DATA_DIR="${2:-../data}"
API_URL="${3:-http://localhost:8000}"
LAYOUT="$DATA_DIR/store_layout.json"
OUTPUT="$DATA_DIR/detected_events.jsonl"

> "$OUTPUT"

declare -A CAM_MAP=(
    ["CAM 1.mp4"]="CAM_1"
    ["CAM 2.mp4"]="CAM_2"
    ["CAM 3.mp4"]="CAM_3"
    ["CAM 4.mp4"]="CAM_4"
    ["CAM 5.mp4"]="CAM_5"
)

for filename in "${!CAM_MAP[@]}"; do
    camera_id="${CAM_MAP[$filename]}"
    video_path="$VIDEOS_DIR/$filename"
    if [ -f "$video_path" ]; then
        echo "Processing $camera_id..."
        python detect.py \
            --video "$video_path" \
            --camera "$camera_id" \
            --layout "$LAYOUT" \
            --output "$OUTPUT" \
            --api "$API_URL"
    else
        echo "Skipping $filename (not found)"
    fi
done

echo "All done. Events saved to $OUTPUT"