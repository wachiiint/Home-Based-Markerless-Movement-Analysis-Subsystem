# **Project Proposal: Home-Based Markerless Movement Analysis Subsystem (Team 5\)**

**ทีมที่รับผิดชอบ:** Team 5 (Movement Analysis & Tele-Rehabilitation Subsystem)

**อาจารย์ที่ปรึกษาโครงการ:** รศ.ดร.พิษณุ คนองชัยยศ

**ปีการศึกษา:** ภาคฤดูร้อน ปีการศึกษา 2568 (Academic Year 2025-2026)

Please refer to this [documentation](https://docs.google.com/document/d/1FwNN-6pO3VHI83-pHLqGwRwWsl01FDhgPUOuc7VpYjs/edit?tab=t.hmk1jutsczvc)

## project structure
```
├── data/                         # Secure storage for patient CSVs/Videos (PDPA compliant)
├── src/
│   ├── __init__.py
│   ├── analytics.py              # Layer 3: Kinematic calculations (Angles, Smoothness, Gait)
│   ├── filters.py                # Layer 2: EMA Smoothing layer
│   ├── pipeline.py               # Coordinates MediaPipe frame-by-frame video processing
│   └── screening.py              # Layer 4: Rule-based flagging (Impairments, Compensation)
├── main.py                       # FastAPI Application Orchestrator (API Gate)
├── pose_landmarker_full.task
├── pyproject.toml
└── uv.lock
```

## init
### configuration for uv environment
```sh
uv python install 3.12
export PATH="/home/wachi/.local/bin:$PATH"
# or
uv python update-shell

mkdir pose-detection && cd pose-detection

uv init
uv add mediapipe "opencv-python" numpy
## or
# uv pip install opencv-python-headless mediapipe numpy
uv add streamlit 


# Add FastAPI and Uvicorn package dependencies via uv
uv add fastapi uvicorn python-multipart
```
### test webcam demo
```sh
# resource = https://github.com/TitorPs360/mediapipe-pose-estimation-example/blob/main/README.md

# load model 
wget -O pose_landmarker_full.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task

# check camera
ls -l /dev/video* # locate camera
ffplay /dev/video0 # test camera

# run
uv run simple_demo.py
```

## how to use 

### 1. open backend server
This is to test API call

open server
```sh
# Fire up the backend development server
uv run uvicorn main:app --reload
```

TEST API
Method A: The Interactive Interactive Dashboard (Easiest & Best for Demos)

FastAPI automatically builds an interactive web testing portal out-of-the-box.

1. Open your web browser and go to: http://127.0.0.1:8000/docs
2. You will see a clean, professional documentation screen showing your /api/movement/assess endpoint.
3. Click the POST row to expand it, then click the "Try it out" button on the right.
4. Fill in the form fields:
```
    patient_id: PT-001
    task_type: gait_walk
    view: lateral
    file: Click "Choose File" and select the data/pun1.mp4 video inside your project folder
```
5. Scroll down and hit the big blue "Execute" button.

Method B: Trigger it via Terminal (Using curl)
Bash
```sh
curl -X 'POST' \
  'http://127.0.0.1:8000/api/movement/assess' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'patient_id=PT-001' \
  -F 'task_type=gait_walk' \
  -F 'view=lateral' \
  -F 'file=@data/pun1.mp4'
```

### 2. run testing streamlit
This is to test the working graphic pipeline
```sh
uv run streamlit run streamlit_app.py
```
