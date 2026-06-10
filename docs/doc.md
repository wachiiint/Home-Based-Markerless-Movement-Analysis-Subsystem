# **Project Proposal: Home-Based Markerless Movement Analysis Subsystem (Team 5\)**

**ทีมที่รับผิดชอบ:** Team 5 (Movement Analysis & Tele-Rehabilitation Subsystem)

**อาจารย์ที่ปรึกษาโครงการ:** รศ.ดร.พิษณุ คนองชัยยศ

**ปีการศึกษา:** ภาคฤดูร้อน ปีการศึกษา 2568 (Academic Year 2025-2026)


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
### run webcam demo
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


### run backend
```sh
# Fire up the backend development server
uv run uvicorn main:app --reload
```

### run testing streamlit
```sh
uv run streamlit run streamlit_app.py
```
