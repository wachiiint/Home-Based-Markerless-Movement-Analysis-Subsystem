###### 1. installation
# uv python pin 3.12
uv python install 3.12
export PATH="/home/wachi/.local/bin:$PATH"
# or
uv python update-shell

mkdir pose-detection && cd pose-detection

uv init
uv add mediapipe "opencv-python" numpy
## or
uv pip install opencv-python-headless mediapipe numpy

###### 2.demo
# resource = https://github.com/TitorPs360/mediapipe-pose-estimation-example/blob/main/README.md

# load model 
wget -O pose_landmarker_full.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task

# check camera
ls -l /dev/video* # locate camera
ffplay /dev/video0 # test camera

# run
uv run example3.py