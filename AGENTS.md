# AGENTS.md

> ⚠️ **AGENTS: KEEP THIS FILE UP TO DATE.**
> This file is the shared, cross-platform briefing for AI agents working on this repo — it is **not**
> human onboarding docs (those live in `README.md` and `docs/01`–`06`). If you contribute to or
> change the project — new module, moved responsibility, changed invariant, new cross-repo
> dependency — **update this file in the same change**. Keep it concise: describe the *current*
> state, not a history of edits. Do not let it drift.

## Module Map

- `app/main.py`: FastAPI app, lifespan (model/mode selection at startup), routes, exception handlers.
- `app/core/`: settings (`config.py`), security/auth (`security.py`), logging.
- `app/schemas/`: request enums and response models (the API contract lives in `response.py`).
- `app/services/`: the pipeline. Top level: `video_io.py` (input boundary), `video_analysis.py`
  (orchestrator), `response_mapper.py` (contract mapping). Sub-packages: `pose/` (estimator,
  sequence, subject selection, tracking, detector), `analysis/` (kinematics, smoothing, screening,
  quality, task analyzers — shared 2D math), `calibration/` (ChArUco board → camera intrinsics/floor
  plane), and `lifting/` (2D→3D via MotionBERT).
- `app/models/`: keypoint constants (`keypoints.py`) and per-task configuration (`task_config.py`).
- `app/utils/`: math and file helpers.
- `tests/`: API contract, auth, response mapper, kinematics, calibration, and lifting tests.

The orchestrator is `app/services/video_analysis.py`. For the full data flow, read
[docs/03-pipeline.md](docs/03-pipeline.md).

## Architecture Invariants (do not break)

- **2D always runs; 3D is best-effort and never raises.** The 3D path (`ENABLE_3D`) is fully
  try-guarded and falls back to the 2D result if the lifter, board, calibration, or guards are
  unavailable. `analysis_mode` in the response reports which mode actually finished, and
  `guard_warnings` explains any 3D skip. Keep this graceful-degradation property.
- **The response always has the same 5 top-level keys** (`session_id`, `video_metadata`,
  `clinical_metrics`, `screening_result`, `transformation_matrix_6dof`). Fields beyond v1 scope
  (`gait_parameters`, `compensation`, `smoothness`, `symmetry_index_score`) exist in the schema but
  stay empty/`None` — see [docs/05-evaluation-plan.md](docs/05-evaluation-plan.md).
- **3D weights are not committed** (`models/`, `*.onnx` are gitignored). 3D stays off until weights
  are provided via `ENABLE_3D` + `MOTIONBERT_MODEL_PATH`. `StubLifter` is for tests only.
- **V1 is a local decision-support / demo service — not a clinical diagnosis system.** Be cautious
  about changing screening thresholds or angle math; see the validation risks in
  [docs/05-evaluation-plan.md](docs/05-evaluation-plan.md).

## Cross-Repo Task Sync

The movement task set **must stay in sync across three repos**:

- This repo: `app/models/task_config.py`
- Frontend: `movementTasks.ts`
- Backend: `movement_tasks.py`

Changing a task here is **not** self-contained — update the other two.

## Requirement Reference

`docs/Project101_Team5.md` (+ `.pdf`) is the Team 5 project proposal — the master doctor-facing
`clinical_metrics` / `screening_result` / `transformation_matrix_6dof` spec that `app/schemas/response.py`
mirrors in shape. Treat it as the source of truth for the contract; **do not edit it**.
