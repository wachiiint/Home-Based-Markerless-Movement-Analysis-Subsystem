# RTMPose Movement Analysis Service

A local FastAPI service for markerless movement analysis with RTMPose. It accepts a short video of a
patient performing one prescribed leg movement and returns joint angles, range of motion,
smoothness, and a quality-graded screening indicator, plus an annotated skeleton video and a 3D
motion simulation. Sarcopenia screening in the elderly is the first use case; the final goal is a
movement-analysis tool usable with anyone.

**Project status: the proof-of-concept round is concluding** — what it demonstrates and what comes
next is in [docs2/10-poc-conclusion.md](docs2/10-poc-conclusion.md).

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

Everything lives in **[`docs2/`](docs2/)**. New to the project? Read the PoC conclusion first, then
follow its links.

| # | Doc | What it covers |
|---|-----|----------------|
| 10 | [PoC Conclusion](docs2/10-poc-conclusion.md) | **Start here** — the result of this round in one read |
| 00 | [Glossary](docs2/00-glossary.md) | Every clinical and technical term used |
| 01 | [Specification](docs2/01-specification.md) | What the project is, why, and its architecture |
| 02 | [Pipeline](docs2/02-pipeline.md) | The patient workflow and the technical data pipeline |
| 03 | [API Contract](docs2/03-api-contract.md) | The `v1` API design, and how the running API differs |
| 04 | [Planning](docs2/04-planning.md) | What remains to close the PoC, and what carries to the prototype |
| 05 | [User Manual](docs2/05-user-manual.md) | How to perform, record, and read each movement test |
| 06 | [Setup](docs2/06-setup.md) | Install and run the application |
| 07 | [Evaluation & Limitations](docs2/07-evaluation-and-limitations.md) | Accuracy, validation, and what we can honestly claim |
| 08 | [Spec Alignment](docs2/08-spec-alignment.md) | Status against the advisor's specification |
| 09 | [Calibration Board](docs2/09-calibration-board-optional.md) | The PoC's camera-calibration and metric-scale path |

Source material: [Project101_Team5.md](docs2/Project101_Team5.md) is the original project proposal and
clinical requirement.

Contributors working with AI agents: see [AGENTS2.md](AGENTS2.md).
