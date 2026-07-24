# 06 — Setup

> How to install and run the application on your own machine.
> Written for a teammate starting from nothing. Commands are given for **Windows PowerShell** first,
> since that is what the team uses, with macOS and Linux equivalents where they differ.

**This describes the application as it exists today.** Steps that will change as planned work lands
are marked at the end, in part 9.

---

## 1. What you need

| Requirement | Notes |
|-------------|-------|
| **Python 3.11 or newer** | 3.13 is what the team runs. Check with `python --version` |
| **uv** | The package manager this project uses. Installation below |
| **git** | To get the code |
| **About 5 GB free disk** | Mostly the virtual environment and downloaded models |
| **A webcam-quality video to test with** | Sample clips are in the repository root |
| *(Optional)* **NVIDIA GPU** | Everything runs on CPU. A GPU makes analysis faster, nothing more |

### Installing uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen the terminal afterwards, then check it worked:

```powershell
uv --version
```

---

## 2. Install

```powershell
git clone <repository-url>
cd Home-Based-Markerless-Movement-Analysis-Subsystem
uv sync
```

`uv sync` reads `pyproject.toml`, creates a virtual environment in `.venv`, and installs everything.
It takes a few minutes the first time.

Then create your configuration file from the template:

```powershell
Copy-Item .env.example .env
```

macOS and Linux: `cp .env.example .env`

The defaults work. You only edit `.env` when turning on 3D — see part 5.

---

## 3. Run it

```powershell
uv run python -m app
```

The service starts on port 8000. To use a different port:

```powershell
$env:PORT=8011; uv run python -m app
```

> **Use `python -m app`, not `uvicorn` directly.** The runner sets a shutdown timeout so that
> **Ctrl+C actually stops the server on Windows**. Plain uvicorn hangs at "Shutting down" waiting for
> an open browser tab to close its connection. If you do run uvicorn yourself, add
> `--timeout-graceful-shutdown 5`.

---

## 4. Check it works

**Health check:**

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

macOS and Linux: `curl http://127.0.0.1:8000/health`

You should see the status, the selected device, and whether the model loaded.

**Browser interface:** open [http://127.0.0.1:8000/](http://127.0.0.1:8000/), upload one of the
sample clips from the repository root, and check that you get an annotated video and metrics back.

> **The first real analysis is slow.** RTMPose downloads its weights automatically on first use —
> you never fetch them by hand. Later runs are much faster.

### What `model_loaded: true` actually means

- It tracks only the **2D pose model**, which downloads automatically.
- It does **not** track the optional 3D model. A missing 3D model does not change it.
- With `FAKE_MODE=true` it reports `true` without loading anything at all. That mode exists for
  testing the interface without running inference.

---

## 5. Optional — enable 3D

3D lifting is off by default. Without it you still get joint angles, ROM, smoothness, and screening;
you do not get the 3D motion simulation or measurements in millimetres.

The 3D model is **MotionBERT-Lite**. Its authors publish PyTorch weights, not the ONNX format this
project needs, so this is a one-time export you run yourself.

**Follow [models/build_bert_lite.md](../models/build_bert_lite.md)** for the download and export
steps. The result belongs at `models/target/motionbert_lite_sim.onnx` — roughly 64 MB, and not
committed to the repository.

Then edit `.env`:

```env
ENABLE_3D=true
MOTIONBERT_MODEL_PATH=models/target/motionbert_lite_sim.onnx
```

Restart the service. On startup it smoke-tests the export: if the model's inputs and outputs do not
match what is expected, **3D is refused and the service falls back to 2D** rather than producing
silent nonsense. Watch the startup log to confirm which happened.

### Optional — realistic muscle anatomy

The muscle overlay works out of the box using a built-in approximate anatomy table. For anatomically
sourced muscle paths, follow [models/get_gait2392.md](../models/get_gait2392.md) to obtain the
OpenSim `gait2392` model, then convert it:

```powershell
uv run python -m app.tools.extract_gait2392_muscles --osim models/target/gait2392_simbody.osim
```

This produces `models/target/gait2392_muscles.json`, which the application picks up automatically.

---

## 6. Run the tests

```powershell
uv run pytest
```

The whole suite runs in under a minute and needs no model weights or network access. Run it before
and after any change — if it was green before and red after, you broke something.

```powershell
uv run pytest -q                          # quieter output
uv run pytest tests/test_kinematics.py    # one file
uv run pytest -k symmetry                 # tests matching a name
```

One test is skipped automatically when the 3D model file is absent. That is expected.

---

## 7. Configuration reference

Everything in `.env`. Defaults are sensible; change them only with a reason.

| Setting | Default | What it does |
|---------|---------|--------------|
| `SERVICE_API_KEY` | `dev-local-analysis-key` | The key callers must send. Change it if the machine is not private |
| `DEVICE` | `auto` | `auto`, `cpu`, or `cuda:0` |
| `POSE_MODEL` | `rtmpose-m` | Which RTMPose size to use |
| `RTMLIB_MODE` | `balanced` | Trade-off between speed and accuracy |
| `FRAME_SAMPLE_FPS` | `10` | Frames analysed per second of video. Higher is slower and more detailed |
| `MIN_KEYPOINT_CONFIDENCE` | `0.4` | Below this, a detected joint is treated as unusable |
| `MIN_VALID_FRAME_RATIO` | `0.6` | Below this proportion of usable frames, quality is flagged |
| `SMOOTHING_ALPHA` | `0.4` | Smoothing strength on the angle series. Lower is smoother but laggier |
| `ENABLE_3D` | `false` | Turns on 3D lifting |
| `MOTIONBERT_MODEL_PATH` | *(empty)* | Where the 3D model file lives |
| `FAKE_MODE` | `false` | Returns a fake result without running inference. For interface testing |
| `DEMO_MAX_UPLOAD_MB` | `100` | Largest accepted upload |
| `DEMO_RESULT_TTL_SECONDS` | `3600` | How long generated videos stay available |
| `LOG_LEVEL` | `INFO` | `DEBUG` for much more detail |

---

## 8. Troubleshooting

| Problem | Cause and fix |
|---------|---------------|
| `uv: command not found` | The terminal was open before uv was installed. Close and reopen it |
| First analysis hangs for minutes | RTMPose is downloading its weights. Normal once, needs internet |
| Ctrl+C does not stop the server | You ran `uvicorn` directly. Use `uv run python -m app` |
| `curl` behaves strangely in PowerShell | In PowerShell `curl` is an alias for `Invoke-WebRequest`. Use `curl.exe` explicitly |
| Port already in use | Another copy is running, or something else holds the port. Use `$env:PORT=8011` |
| Analysis is very slow | Normal on CPU. Lower `FRAME_SAMPLE_FPS`, or use a shorter clip |
| Results always come back 2D | `ENABLE_3D` is false, the model file is missing, or the reconstruction failed its check. Read the startup log |
| Import errors after pulling changes | Dependencies changed. Run `uv sync` again |
| Tests fail on a clean checkout | Report it. A clean checkout should always be green |

### Reading the startup log

The service prints one line on startup showing the device, whether the pose model loaded, and whether
3D is active. If 3D was refused, the reason appears here. This is the fastest way to find out why
results are not what you expect.

---

## 9. What changes as planned work lands

These steps do not exist yet. They are listed so this document can be updated in the same change that
adds them — see [04-planning.md](04-planning.md).

| Planned work | New setup step |
|--------------|----------------|
| SQLite storage (P2) | A database file is created on first run. Its location becomes a setting, and backing it up means copying one file |
| Bone-length patient records (P2) | Each patient's measurements are entered once through the interface before metric 3D works for them |
| Calibration board becomes optional (P2) | The board printing and device calibration steps disappear from normal use |

---

## Related documents

| Document | Purpose |
|----------|---------|
| [00-glossary.md](00-glossary.md) | Definitions of every term used |
| [01-specification.md](01-specification.md) | What the project is and why |
| [02-pipeline.md](02-pipeline.md) | Patient workflow and the technical data pipeline |
| [03-api-contract.md](03-api-contract.md) | Request and response formats |
| [04-planning.md](04-planning.md) | Phases, tasks, risk, effort, benefit |
| [05-user-manual.md](05-user-manual.md) | How to perform, record, and interpret each task |
| **06-setup.md** | *This document* |
| [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) | Accuracy, validation, and honest limits |
| [08-spec-alignment.md](08-spec-alignment.md) | Status against the advisor's specification |
