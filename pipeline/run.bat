@echo off
set VIDEOS_DIR=%1
if "%VIDEOS_DIR%"=="" set VIDEOS_DIR=..\data\CCTV
set DATA_DIR=%2
if "%DATA_DIR%"=="" set DATA_DIR=..\data
set API_URL=%3
if "%API_URL%"=="" set API_URL=http://localhost:8000

python detect.py --video "%VIDEOS_DIR%\CAM 1.mp4" --camera CAM_1 --layout "%DATA_DIR%\store_layout.json" --output "%DATA_DIR%\detected_events.jsonl" --api %API_URL%
python detect.py --video "%VIDEOS_DIR%\CAM 2.mp4" --camera CAM_2 --layout "%DATA_DIR%\store_layout.json" --output "%DATA_DIR%\detected_events.jsonl" --api %API_URL%
python detect.py --video "%VIDEOS_DIR%\CAM 3.mp4" --camera CAM_3 --layout "%DATA_DIR%\store_layout.json" --output "%DATA_DIR%\detected_events.jsonl" --api %API_URL%
python detect.py --video "%VIDEOS_DIR%\CAM 4.mp4" --camera CAM_4 --layout "%DATA_DIR%\store_layout.json" --output "%DATA_DIR%\detected_events.jsonl" --api %API_URL%
python detect.py --video "%VIDEOS_DIR%\CAM 5.mp4" --camera CAM_5 --layout "%DATA_DIR%\store_layout.json" --output "%DATA_DIR%\detected_events.jsonl" --api %API_URL%

echo All done.