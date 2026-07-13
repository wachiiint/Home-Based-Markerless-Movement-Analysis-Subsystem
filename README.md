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

The UI is a local decision-support demo only. It is not a clinical diagnosis system and should not be exposed directly to the public internet.
