# RTMPose Movement Analysis Service

A local FastAPI service for 2D markerless movement analysis with RTMPose. It accepts an uploaded
movement video and returns a JSON assessment compatible with the existing MediaPipe backend contract.

> **Version 1 is a local decision-support / demo service. It is not a clinical diagnosis system,
> and should not be exposed directly to the public internet.**

## Quickstart

```powershell
uv sync
Copy-Item .env.example .env
uv run uvicorn app.main:app --port 8000
```

Then open the demo page at [http://127.0.0.1:8000/](http://127.0.0.1:8000/), or check health with
`Invoke-RestMethod http://127.0.0.1:8000/health`.

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
| 06 | [Implementation Plan](docs/06-implementation-plan.md) | Build phases |

The requirement/proposal doc is [docs/Project101_Team5.md](docs/Project101_Team5.md) (the master
clinical spec this service's response mirrors). Contributors working with AI agents: see
[AGENTS.md](AGENTS.md).
