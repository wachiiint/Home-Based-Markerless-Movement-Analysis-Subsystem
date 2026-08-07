# RTMPose Movement Analysis Service

A local FastAPI service for markerless movement analysis with RTMPose, supporting home-based
sarcopenia screening. It accepts a short video of a patient performing one prescribed leg movement
and returns joint angles, range of motion, smoothness, and a quality-graded screening indicator,
plus an annotated skeleton video and a 3D motion simulation.

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

Full installation, GPU, and 3D setup instructions are in [docs2/06-setup.md](docs2/06-setup.md).

## Documentation

Everything lives in **[`docs2/`](docs2/)**. Start with the specification, or jump to the planning
document to see what is being built next.

| # | Doc | What it covers |
|---|-----|----------------|
| 00 | [Glossary](docs2/00-glossary.md) | Every clinical and technical term used |
| 01 | [Specification](docs2/01-specification.md) | **Start here** — what the project is, why, and its architecture |
| 02 | [Pipeline](docs2/02-pipeline.md) | The patient workflow and the technical data pipeline |
| 03 | [API Contract](docs2/03-api-contract.md) | Request and response formats |
| 04 | [Planning](docs2/04-planning.md) | **What comes next** — phases, tasks, risk, effort |
| 05 | [User Manual](docs2/05-user-manual.md) | How to perform, record, and read each movement test |
| 06 | [Setup](docs2/06-setup.md) | Install and run the application |
| 07 | [Evaluation & Limitations](docs2/07-evaluation-and-limitations.md) | Accuracy, validation, and what we can honestly claim |
| 08 | [Spec Alignment](docs2/08-spec-alignment.md) | Status against the advisor's specification |
| 09 | [Calibration Board](docs2/09-calibration-board-optional.md) | The PoC's camera-calibration and metric-scale path |
| 10 | [PoC Conclusion](docs2/10-poc-conclusion.md) | **The result of this round in one read — start here** |

Source material: [Project101_Team5.md](docs2/Project101_Team5.md) is the original project proposal and
clinical requirement.

Contributors working with AI agents: see [AGENTS2.md](AGENTS2.md).
