# RTMPose Movement Analysis Service

A local FastAPI service for 2D markerless movement analysis with RTMPose. It accepts an uploaded movement video and returns a JSON response compatible with the existing MediaPipe assessment backend contract.

Version 1 is a local decision-support/demo service. It is not a clinical diagnosis system.

## Setup

```powershell
uv sync
Copy-Item .env.example .env
uv run uvicorn app.main:app --port 8000
```

Open the test page at [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Keep `FAKE_MODE=false` to run real RTMPose inference. The first startup downloads the RTMPose/YOLOX ONNX models; later startups reuse the local rtmlib cache.

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Assessment request:

```bash
curl -F patient_id=PT-001 \
  -F task_type=knee_flexion \
  -F view=lateral \
  -F file=@clip.mp4 \
  -H "X-Internal-Service-Key: dev-local-analysis-key" \
  http://127.0.0.1:8000/api/movement/assess
```

## Environment

See `.env.example` for all options. Important settings:

- `SERVICE_API_KEY`: internal server-to-server API key.
- `FAKE_MODE=true`: skips RTMPose loading and returns deterministic valid data for integration tests.
- `DEVICE=auto`: uses `cuda:0` when available, otherwise CPU.
- `MODEL_BACKEND=rtmlib`: default pose backend.
- `ENABLE_3D`: turns on the 2D->3D lifting path (see [3D lifting](#3d-lifting) below). Off by default; falls back to 2D cleanly if weights are missing or fail validation.
- `MOTIONBERT_MODEL_PATH`: path to the MotionBERT ONNX export used for lifting.

## 3D lifting

The service can optionally lift the 2D pose to 3D with MotionBERT. Two things come out of one lift, and only the first needs a calibrated board:

- **Display coordinates** (demo UI only): a root-relative 3D skeleton for the viewer described below. Needs only the lifter -- no calibration required. Not a clinical measurement.
- **Metric 3D** (`joint_angles_3d`, `scale_mm_per_unit`, `transformation_matrix_6dof` in the API response): additionally requires a calibrated ChArUco board in frame and a task with a defined 3D angle (hip/knee; ankle stays 2D). See `docs/PIPELINE.md` for the full calibration and lifting pipeline.

3D is best-effort throughout: if the lifter, board, or guards are unavailable, the service degrades to the 2D result and never raises. `analysis_mode` in the response tells you which one actually happened, and `guard_warnings` explains why 3D was skipped when it was.

To enable:

```env
ENABLE_3D=true
MOTIONBERT_MODEL_PATH=models/motionbert_lite.onnx
```

Model weights are not committed to the repo (`models/`, `*.onnx` are gitignored) -- obtain or export them separately.

## Windows GPU Notes

The default dependency is `onnxruntime` for CPU. To use CUDA, remove it and install `onnxruntime-gpu` with CUDA/cuDNN versions that match ONNXRuntime. Do not install `onnxruntime` and `onnxruntime-gpu` together because they conflict.

## Integration

Existing backend `.env`:

```env
MEDIAPIPE_SERVICE_URL=http://127.0.0.1:8000
MEDIAPIPE_API_KEY=dev-local-analysis-key
MEDIAPIPE_REQUEST_TIMEOUT_SECONDS=300
```

The service key is internal only. Never send it to a browser.

## Demo UI

The browser page uses the same-origin `/api/demo/assess` endpoint, so it does not need or expose `SERVICE_API_KEY`. It shows the uploaded video, the annotated skeleton video, ROM metrics, pose quality, and screening output. Demo files are temporary and expire after `DEMO_RESULT_TTL_SECONDS` (one hour by default). The generated video is sampled at `FRAME_SAMPLE_FPS` and does not include the original audio.

When `ENABLE_3D=true`, the demo also renders a 3D skeleton viewer (Three.js, bundled locally under `app/static/vendor/` -- no CDN calls) fed by a `pose3d.json` file served alongside the annotated video. Drag to rotate, scroll to zoom, and use the frame slider/play button to scrub the motion. A yellow warning banner appears when the lift fails its bone-length consistency guard -- the shape is still shown for illustration, but flagged as unreliable rather than hidden. This viewer is display-only: for a clip to also get metric 3D numbers in the API response, a calibrated ChArUco board must be visible in frame (see [3D lifting](#3d-lifting)).

To run the demo UI (e.g. on port 8011):

```powershell
uv run uvicorn app.main:app --port 8011
```

Then open [http://127.0.0.1:8011/](http://127.0.0.1:8011/). Keep `FAKE_MODE=false` in `.env` to run real RTMPose inference.

The UI is a local decision-support demo only. It is not a clinical diagnosis system and should not be exposed directly to the public internet.
