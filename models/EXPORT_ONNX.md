# Exporting MotionBERT weights to ONNX

This service ships the 3D lifter as an ONNX file (`models/motionbert_lite.onnx`).
That file is **not** committed with the upstream weights — there is **no official
ONNX release** of MotionBERT. The authors publish only PyTorch `.bin`
checkpoints, so you export the ONNX yourself from the repo + weights.

This guide reproduces `models/motionbert_lite.onnx` from scratch. Follow it if
the ONNX is missing, or you want to rebuild it with a different config/frame
budget.

> The model consumes **2D keypoints**, not images — no image preprocessing is
> baked into the graph, which keeps the export clean and CPU-friendly.

## What you get

| | |
|---|---|
| Repo | https://github.com/Walter0807/MotionBERT |
| Weights | https://huggingface.co/walterzhu/MotionBERT |
| Input | `[batch, frames, 17, 3]` — x, y, confidence (Human3.6M joint order) |
| Output | `[batch, frames, 17, 3]` — x, y, z (root-relative) |
| Max frames | 243 (fixed temporal positional-embedding length) |

The service's `MotionBertAdapter` reads the ONNX input name dynamically
(`session.get_inputs()[0].name`), so the exported input/output names do **not**
need to match anything — only the tensor **shapes and joint order** matter.

## Prerequisites

- Python 3.11
- [`uv`](https://docs.astral.sh/uv/) (or plain `pip` in a venv)
- ~1 GB free disk (repo + weights + ONNX)
- Network access to GitHub and Hugging Face

---

## Steps

### 1. Clone the MotionBERT repo

```bash
cd models
git clone https://github.com/Walter0807/MotionBERT.git
cd MotionBERT
```

### 2. Create a virtual environment

**Linux / macOS**

```bash
uv venv --python 3.11
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
uv venv --python 3.11
. .\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
uv pip install torch --torch-backend=cpu
uv pip install numpy pyyaml easydict onnx onnxruntime onnxsim onnxscript
```

### 4. Download the Lite checkpoint

We export the **Lite** variant (`FT_MB_lite_MB_ft_h36m_global_lite`, ~64 MB
ONNX) — small and fast enough for CPU inference.

**Linux / macOS**

```bash
mkdir -p checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite
curl -L -o checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin \
  https://huggingface.co/walterzhu/MotionBERT/resolve/main/checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin
```

**Windows (PowerShell)**

```powershell
$dir = "checkpoint\pose3d\FT_MB_lite_MB_ft_h36m_global_lite"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$ProgressPreference = 'SilentlyContinue'   # avoids a slow progress bar
Invoke-WebRequest `
  -Uri "https://huggingface.co/walterzhu/MotionBERT/resolve/main/checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin" `
  -OutFile "$dir\best_epoch.bin"
```

### 5. Run the export script

Copy the export helper (kept next to this doc) into the cloned repo, then run it:

```bash
cp ../export_motionbert_onnx.py .

# Linux / macOS
python export_motionbert_onnx.py \
  --config configs/pose3d/MB_ft_h36m_global_lite.yaml \
  --ckpt   checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin \
  --out    motionbert_lite.onnx
```

```powershell
# Windows (PowerShell)
copy ..\export_motionbert_onnx.py .
python export_motionbert_onnx.py `
  --config configs/pose3d/MB_ft_h36m_global_lite.yaml `
  --ckpt   checkpoint\pose3d\FT_MB_lite_MB_ft_h36m_global_lite\best_epoch.bin `
  --out    motionbert_lite.onnx
```

The script loads the backbone from the config, strips the `module.` prefix left
by the checkpoint's `nn.DataParallel` wrapper, exports with **dynamic** batch and
frame axes (opset 17), and self-verifies that the ONNX output matches the PyTorch
output. Expect near-zero `max abs diff` and a printed `27-frame out` shape
confirming the frame axis is genuinely dynamic.

### 6. (Optional) Simplify the graph

`onnxsim` folds constants and collapses redundant nodes — smaller file, same
math:

```bash
onnxsim motionbert_lite.onnx motionbert_lite_sim.onnx
```

### 7. Move the ONNX into `models/` and clean up

```bash
cd ..            # back to models/
# use the simplified file if you ran step 6, otherwise the plain export:
mv ./MotionBERT/motionbert_lite_sim.onnx ./motionbert_lite.onnx
# or: mv ./MotionBERT/motionbert_lite.onnx ./motionbert_lite.onnx

rm -rf ./MotionBERT   # the cloned repo + weights are no longer needed
```

> The service expects the file at the path set by `MOTIONBERT_MODEL_PATH`
> (default `models/motionbert_lite.onnx` in `.env` / `.env.example`). Rename
> accordingly if you exported a different variant.

### 8. Verify it loads and runs

`models/verify.py` does a self-contained CPU inference smoke test:

```bash
uv run python verify.py
```

Expected output:

```
(1, 243, 17, 3)
self-contained OK
```

> `verify.py` references `motionbert_lite_sim.onnx`. If you skipped the
> `onnxsim` step (step 6), either rename your file to match or edit the filename
> at the top of `verify.py`.

---

## Enabling 3D in the service

Once the ONNX is in place, turn on 3D in your `.env` (it is `false` by default in
`.env.example` as the safe fallback):

```dotenv
ENABLE_3D=true
MOTIONBERT_MODEL_PATH=models/motionbert_lite.onnx
```

On startup `build_lifter()` constructs a `MotionBertAdapter` and runs
`validate_lifter_io()` — an 8-frame smoke test that rejects any export whose
output isn't `(T, 17, 3)` finite values. If the file is missing or fails the
guard, the service logs a warning and **degrades to 2D** rather than crashing,
so a bad or absent ONNX never breaks the endpoint.

## Troubleshooting

- **`missing`/`unexpected` keys printed during export** — a few non-`strict`
  mismatches are expected (the export uses `strict=False`); a large list means
  the config doesn't match the checkpoint. Confirm you paired
  `MB_ft_h36m_global_lite.yaml` with the `FT_MB_lite_*` checkpoint.
- **Large `max abs diff`** — the ONNX diverges from PyTorch; check the opset
  and that `torch`/`onnxruntime` versions are recent.
- **Service falls back to 2D despite the file existing** — check the startup
  log for the `3D lifter unavailable` warning (raised by the I/O guard), and
  confirm `ENABLE_3D=true` and `MOTIONBERT_MODEL_PATH` point at the ONNX.
