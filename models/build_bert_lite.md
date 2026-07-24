# Exporting MotionBERT to ONNX (uv workflow)

There is **no official ONNX release** of MotionBERT. The authors publish only
PyTorch `.bin` checkpoints, so you export it yourself from the repo + weights.

The model takes **2D keypoints**, not images — no image preprocessing gets baked
into the graph, which makes the export unusually clean.

| | |
|---|---|
| Repo | https://github.com/Walter0807/MotionBERT |
| Weights | https://huggingface.co/walterzhu/MotionBERT |
| Input | `[batch, frames, 17, 3]` — x, y, confidence (H36M joint order) |
| Output | `[batch, frames, 17, 3]` — x, y, z |
| Max frames | 243 (temporal positional embedding length) |

---

```bash
# Clone the repo
cd models
git clone https://github.com/Walter0807/MotionBERT.git
cd MotionBERT

# Create venv
uv venv --python 3.11
source .venv/bin/activate
## for Windows
uv venv --python 3.11
. .\.venv\Scripts\activate

# install dependencies
uv pip install torch --torch-backend=cpu
uv pip install numpy pyyaml easydict onnx onnxruntime onnxsim onnxscript

# Download weight for Lite Mode
mkdir -p checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite

curl -L -o checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin \
  https://huggingface.co/walterzhu/MotionBERT/resolve/main/checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin
# In windows:
$dir = "checkpoint\pose3d\FT_MB_lite_MB_ft_h36m_global_lite"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest `
  -Uri "https://huggingface.co/walterzhu/MotionBERT/resolve/main/checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin" `
  -OutFile "$dir\best_epoch.bin"

# copy the script into the project
cp ../export_motionbert_onnx.py .

# export using python script
python export_motionbert_onnx.py \
  --config configs/pose3d/MB_ft_h36m_global_lite.yaml \
  --ckpt   checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin \
  --out    motionbert_lite.onnx
# In windows:
python export_motionbert_onnx.py `
  --config configs/pose3d/MB_ft_h36m_global_lite.yaml `
  --ckpt   checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin `
  --out    motionbert_lite.onnx

# simplify the model
onnxsim motionbert_lite.onnx motionbert_lite_sim.onnx

cd .. ## go to ./models
mv ./MotionBERT/motionbert_lite_sim.onnx ./target
# Then you can safely remove models/MotionBert
rm -rf MotionBert

# verify
uv run python verify.py
```