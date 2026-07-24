# AGENTS.md

Current-state reference for agents working in this repo. It describes what exists **today**.
Historical phase-by-phase changelogs live in git history, not here.

**Roadmap / source of truth for what comes next: `docs/08-scope-v2.md`.**
That document supersedes any older roadmap. Do not plan work from this file.

## What this service is

A local FastAPI service for home-based markerless movement analysis. A patient records a short
movement clip on a phone; the service returns joint angles, ROM, quality metrics, and a screening
result, plus an annotated skeleton video and an optional 3D viewer.

It is a **decision-support / demo** service, not a clinical diagnosis system.

## Module map

- `app/main.py` — FastAPI app, lifespan, routes, exception handlers.
- `app/__main__.py` — `python -m app` runner; sets `timeout_graceful_shutdown` so Ctrl+C stops the server on Windows.
- `app/core/` — settings (`config.py`), API-key auth (`security.py`), logging.
- `app/schemas/` — request enums (`movement.py`) and response models (`response.py`).
- `app/services/video_io.py`, `video_analysis.py`, `response_mapper.py` — frame sampling, the analysis orchestrator, and response assembly.
- `app/services/pose/` — `pose_estimator.py` (RTMPose via rtmlib), `pose_sequence.py` (full-clip 2D pose collection), `subject_selector.py` (main-subject choice).
- `app/services/analysis/` — `kinematics.py`, `smoothing.py`, `screening.py`, `smoothness.py`, `symmetry.py`.
- `app/services/calibration/` — ChArUco-on-A4: board rendering/geometry, detection + intrinsics/extrinsics (`charuco_calibrator.py`), device identity/persistence (`device_id.py`, `device_store.py`), print-scale verification, board diagnostics, floor transform, per-session calibration (`session.py`).
- `app/services/lifting/` — Halpe26→H36M17 conversion, normalization, `Lifter` protocol with `MotionBertAdapter` + `StubLifter`, `pipeline.py`, 3D angles, metric scale, guards, muscle overlay (`muscles.py`), viewer export (`pose3d_export.py`).
- `app/models/` — Halpe26 keypoint constants, task configuration, calibration models.
- `app/tools/` — CLIs: `generate_board` (ChArUco A4 PDF), `calibrate_device` (per-device intrinsics), `extract_gait2392_muscles` (OpenSim `.osim` → muscle-anchor JSON).
- `app/utils/math_utils.py` — angle/vector helpers used by `kinematics.py`.
- `app/static/` — browser demo UI (upload → results, 3D viewer with muscle overlay).
- `tests/` — 104 tests: API contract, auth, response mapper, kinematics, lifting, calibration/board, muscles, smoothness, symmetry, 3D video analysis.

## What works today

- **2D analysis (always on).** RTMPose (rtmlib `BodyWithFeet`, Halpe26) on sampled frames → EMA-smoothed joint-angle series → min/max/ROM → screening. Annotated skeleton MP4 served back to the demo.
- **Both-legs reporting.** Every clip analyzes left and right; `clinical_metrics.joint_angles` uses side-prefixed keys (`left_knee_rom_deg`, …). Top-line `risk_level` is the worse leg; flags are side-tagged. `analyzed_side` is `"both"` when two legs are usable.
- **Smoothness.** SPARC, log-dimensionless jerk, and movement-unit count per side, from the angle series.
- **Symmetry.** `symmetry_index_score` in `[0, 1]`; abstains (returns `None`) unless both legs actually moved, so unilateral tasks don't report a spurious value.
- **Optional 3D (feature-flagged).** MotionBERT ONNX lift → 3D hip/knee angles (ankle stays 2D), metric scale, camera→floor 6DoF. Entirely best-effort: any failure falls back to the 2D result and sets `analysis_mode`.
- **Optional ChArUco calibration.** Per-device intrinsics (persisted, resolution-keyed) + per-session extrinsics/floor plane. Gives **scale and floor only** — it does not feed the lift.
- **Muscle overlay (M-A, display only).** Five lower-limb muscle groups per leg drawn as curved tubes on the 3D skeleton, colored by a kinematic length proxy. Anatomy from `models/target/gait2392_muscles.json` when present, else a built-in approximate table. This is a geometry estimate, **not** force or activation — a single camera has no ground reaction force.
- **FAKE_MODE.** Returns a contract-shaped response without running inference; used by contract/auth/demo tests.

Still empty by design: `gait_parameters` (needs a walking task + foot-contact detection) and
`compensation` (multi-joint).

## Ground-truth facts (verify before trusting older notes)

- MotionBERT weights: **`models/target/motionbert_lite_sim.onnx`** (~64 MB, gitignored). ONNX input name is `keypoints_2d`.
- `ENABLE_3D` defaults to `false` (`.env.example`); the local `.env` sets it to `true`.
- Sample clips at repo root: `calib.mp4` (1080p multi-angle calibration), `knee_flex_calib.mp4` (1080p, board readable), `knee_flex_nocalib.mp4`.
- Calibration and the patient clip must be recorded at the **same resolution** — `device_id` hashes width×height, so a mismatch means "device not calibrated" and a 2D fallback. The demo warns before submit on a mismatch and explains the fallback after the run.
- Joint angles are **scale-invariant**, so they stay trustworthy even when metric scale is uncertain.

## Conventions

- New response fields are **additive**; the five top-level keys of the contract stay stable.
- 3D/calibration/muscle work is best-effort and try-guarded — the endpoint always returns a 2D result.
- Model weights, exports, and sources go under `models/` (`models/target/` is gitignored).
- We do not download models or clone repos for the user; setup steps are written into docs as CLI guidance.

## Task Sync Note

The movement task set must stay in sync across three files:

- This repo: `app/models/task_config.py`
- Frontend: `movementTasks.ts`
- Backend: `movement_tasks.py`
