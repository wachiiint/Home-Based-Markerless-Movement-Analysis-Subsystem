# RTMPose Movement Analysis Service

A local FastAPI service for markerless movement analysis with RTMPose — 2D analysis always, plus
optional single-camera 3D. It accepts an uploaded movement video and returns a JSON assessment
compatible with the existing MediaPipe backend contract.

> **This is a local decision-support / demo service. It is not a clinical diagnosis system,
> and should not be exposed directly to the public internet.**

## Quickstart

```powershell
uv sync
Copy-Item .env.example .env
uv run python -m app          # port via $env:PORT (default 8000)
```

Then open the demo page at [http://127.0.0.1:8000/](http://127.0.0.1:8000/), or check health with
`Invoke-RestMethod http://127.0.0.1:8000/health`.

> Use `uv run python -m app` rather than `uv run uvicorn app.main:app` — the runner bounds
> uvicorn's graceful-shutdown wait so **Ctrl+C actually stops the server** on Windows (plain
> uvicorn hangs at "Shutting down" waiting on an open browser tab's connections). If you do run
> uvicorn directly, add `--timeout-graceful-shutdown 5`.

Full setup, run, GPU, and integration instructions are in
[docs/01-getting-started.md](docs/01-getting-started.md).

## Documentation (read in order)

| # | Doc | What it covers |
|---|-----|----------------|
| 01 | [Getting Started](docs/01-getting-started.md) | Install, configure, run the service and demo UI |
| 02 | [Project Overview](docs/02-project-overview.md) | What it is, where it fits, key terms |
| 03 | [Pipeline](docs/03-pipeline.md) | How a video becomes a risk assessment (the deep dive) |
| 04 | [API Contract](docs/04-api-contract.md) | Request/response shape of the endpoints |
| 05 | [Evaluation Plan](docs/05-evaluation-plan.md) | Tests, acceptance criteria, validation risks |
| 06 | [Implementation Plan](docs/06-implementation-plan.md) | Build phases (historical record) |
| 07 | [Demo User Guide](docs/07-demo-user-guide.md) | Step-by-step: which video to upload, reading results |
| 08 | [Scope v2](docs/08-scope-v2.md) | **Current roadmap and source of truth for what comes next** |

Also: [Calibration Capture](docs/CALIBRATION_CAPTURE.md) — the operator protocol for the optional
ChArUco board path.

The requirement/proposal doc is [docs/Project101_Team5.md](docs/Project101_Team5.md) (the master
clinical spec this service's response mirrors). Contributors working with AI agents: see
[AGENTS.md](AGENTS.md).
