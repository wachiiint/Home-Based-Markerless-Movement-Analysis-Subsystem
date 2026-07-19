# 01 — Getting Started

This guide takes you from a fresh clone to a running service. If you just want to understand what
the project *is* first, read [02-project-overview.md](02-project-overview.md) before setting up.

---

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** — the package/dependency manager this project uses
- Windows, macOS, or Linux (commands below are shown for **PowerShell on Windows**)
- A GPU is **optional**. The service runs on CPU by default.

---

## 1. Install

```powershell
uv sync
Copy-Item .env.example .env
```

`uv sync` creates the virtual environment and installs everything from `uv.lock`.
Copying `.env.example` to `.env` gives you a working default configuration.

---

## 2. Configure (`.env`)

The defaults work out of the box. The settings you are most likely to touch:

| Variable | What it does |
|----------|--------------|
| `FAKE_MODE` | `true` = skip the ML model entirely and return valid fake data (great for a first run / integration testing). `false` = run real RTMPose inference. |
| `SERVICE_API_KEY` | The internal server-to-server key. The default is `dev-local-analysis-key`. |
| `DEVICE` | `auto` (default) uses the GPU if available, otherwise CPU. Can be forced to `cpu` or `cuda:0`. |
| `ENABLE_3D` | Turn on the optional 2D→3D lifting path (off by default). |

See `.env.example` for the full list, and [03-pipeline.md](03-pipeline.md) for how each one
affects the pipeline.

> **Tip:** For your very first run, leave `FAKE_MODE=true`. It starts instantly and needs no model
> download, so you can confirm the server and API work before dealing with ML dependencies.

---

## 3. Run the service

```powershell
uv run uvicorn app.main:app --port 8000
```

With `FAKE_MODE=false`, the **first** startup downloads the RTMPose/YOLOX ONNX models. Later
startups reuse the local `rtmlib` cache, so they are fast.

Check that it is alive:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

You should see the status, selected device, and whether the model is loaded.

> **What does `model_loaded: true` actually mean?**
> - With **`FAKE_MODE=true`**, health reports `model_loaded: true` **without loading any model** — it
>   is a simulated "ready" signal for backend integration testing. Set `FAKE_MODE=false` to run real
>   inference.
> - `model_loaded` tracks only the **2D RTMPose model**, which `rtmlib` **downloads automatically**
>   on the first real run — you never fetch it by hand.
> - It does **not** track the optional MotionBERT 3D model (`models/motionbert_lite.onnx`). That one
>   is separate, only loads when `ENABLE_3D=true`, and is not reflected in the health check. So a
>   missing MotionBERT file does not change `model_loaded`.

---

## 4. Run the demo UI (optional, recommended)

The browser demo lets you upload a video and see the annotated skeleton, ROM metrics, pose quality,
and screening output. It uses a same-origin endpoint and does **not** expose the service key.

```powershell
uv run uvicorn app.main:app --port 8011
```

Then open [http://127.0.0.1:8011/](http://127.0.0.1:8011/). Keep `FAKE_MODE=false` to see real
inference. Demo files are temporary and expire after `DEMO_RESULT_TTL_SECONDS` (one hour by default).

---

## 5. Call the API directly (optional)

The real integration endpoint requires the internal key header.

**PowerShell (Windows).** Call `curl.exe` explicitly — in PowerShell, plain `curl` is an alias for
`Invoke-WebRequest` and will not understand these flags. Note the backtick (`` ` ``) line
continuation, not a backslash:

```powershell
curl.exe -F patient_id=PT-001 `
  -F task_type=knee_flexion `
  -F view=lateral `
  -F file=@clip2.mp4 `
  -H "X-Internal-Service-Key: dev-local-analysis-key" `
  http://127.0.0.1:8000/api/movement/assess
```

**macOS / Linux (bash):**

```bash
curl -F patient_id=PT-001 \
  -F task_type=knee_flexion \
  -F view=lateral \
  -F file=@clip.mp4 \
  -H "X-Internal-Service-Key: dev-local-analysis-key" \
  http://127.0.0.1:8000/api/movement/assess
```

The full request/response shape is documented in [04-api-contract.md](04-api-contract.md).

---

## Enabling 3D (optional)

3D lifting is off by default and is **best-effort**: if weights, the calibration board, or the
safety guards are missing, the service silently falls back to the 2D result. To turn it on:

```env
ENABLE_3D=true
MOTIONBERT_MODEL_PATH=models/motionbert_lite.onnx
```

Model weights are **not** committed to the repo (`models/` and `*.onnx` are gitignored) — obtain or
export them separately. See [03-pipeline.md](03-pipeline.md) for how the 3D path works and what a
metric 3D result additionally requires (a calibrated ChArUco board in frame).

---

## Using the GPU

**Having a GPU is not enough** — the default dependency is the CPU-only `onnxruntime` package, which
cannot see your GPU. With it installed, `/health` will report `device: cpu` even with `DEVICE=auto`
and a capable GPU, because ONNX Runtime never exposes a CUDA provider to choose from.

To confirm what ONNX Runtime can see:

```powershell
uv run python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

If the list does **not** include `CUDAExecutionProvider`, the service will always fall back to CPU.
To enable the GPU:

```powershell
uv pip uninstall onnxruntime
uv pip install onnxruntime-gpu
```

- Do **not** keep both `onnxruntime` and `onnxruntime-gpu` installed — they conflict.
- You also need **CUDA + cuDNN runtime libraries** installed and version-matched to your ONNX Runtime
  version, or `CUDAExecutionProvider` still will not appear.
- Once the provider shows up, `DEVICE=auto` selects `cuda:0` automatically. Re-check `/health` to
  confirm `device: cuda:0`. (Note: with `FAKE_MODE=true` no inference runs, so device choice only
  matters once `FAKE_MODE=false`.)

---

## Connecting the main backend

The existing backend calls this service as its MediaPipe-compatible analysis service. In the
backend's `.env`:

```env
MEDIAPIPE_SERVICE_URL=http://127.0.0.1:8000
MEDIAPIPE_API_KEY=dev-local-analysis-key
MEDIAPIPE_REQUEST_TIMEOUT_SECONDS=300
```

The service key is **internal only** — never send it to a browser.

---

**Next:** [02-project-overview.md](02-project-overview.md) for how this fits into the larger system,
then [03-pipeline.md](03-pipeline.md) for how the analysis actually works.
