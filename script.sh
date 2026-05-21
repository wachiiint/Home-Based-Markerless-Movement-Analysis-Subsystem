###### 1. installation
# uv python pin 3.12
uv python install 3.12
export PATH="/home/wachi/.local/bin:$PATH"
# or
uv python update-shell

mkdir pose-detection && cd pose-detection

uv init
uv add mediapipe "opencv-python" numpy


###### 2.demo
# resource = https://github.com/TitorPs360/mediapipe-pose-estimation-example/blob/main/README.md
uv run example3.py