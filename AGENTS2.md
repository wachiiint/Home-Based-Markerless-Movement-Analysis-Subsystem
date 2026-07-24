# AGENTS2.md

Context file for AI agents and new contributors. Describes what exists **today**.
Phase-by-phase history lives in git, not here.

---

## Read this first

**`docs2/` is the documentation set and the source of truth.** Do not plan work from this file — it
is a summary and will drift. The authoritative documents are:

| Question | Document |
|----------|----------|
| What is this project and why? | `docs2/01-specification.md` |
| What does a term mean? | `docs2/00-glossary.md` |
| How does it work, stage by stage? | `docs2/02-pipeline.md` |
| What are the request and response formats? | `docs2/03-api-contract.md` |
| **What should I work on next?** | **`docs2/04-planning.md`** |
| How does a patient use it? | `docs2/05-user-manual.md` |
| How do I install and run it? | `docs2/06-setup.md` |
| How accurate is it, and what can we claim? | `docs2/07-evaluation-and-limitations.md` |
| How does it compare to the advisor's spec? | `docs2/08-spec-alignment.md` |

`docs2/` **supersedes the old `docs/` folder**, which has been retired.

---

## What this service is

A local FastAPI service for home-based markerless movement analysis, aimed at sarcopenia screening
support. A patient records a short clip of one prescribed leg movement; the service returns joint
angles, ROM, smoothness, quality metrics, and a screening indicator, plus an annotated skeleton video
and a 3D motion simulation.

**Decision support, not diagnosis.** Runs entirely locally.

---

## Module map

- `app/main.py` — FastAPI app, lifespan, routes, exception handlers.
- `app/__main__.py` — `python -m app` runner; sets `timeout_graceful_shutdown` so Ctrl+C stops the server on Windows.
- `app/core/` — settings (`config.py`), API-key auth (`security.py`), logging.
- `app/schemas/` — request enums (`movement.py`) and response models (`response.py`).
- `app/services/video_io.py`, `video_analysis.py`, `response_mapper.py` — frame sampling, the analysis orchestrator, response assembly.
- `app/services/pose/` — `pose_estimator.py` (RTMPose via rtmlib), `pose_sequence.py`, `subject_selector.py`.
- `app/services/analysis/` — `kinematics.py`, `smoothing.py`, `screening.py`, `smoothness.py`, `symmetry.py`.
- `app/services/calibration/` — ChArUco board handling: rendering, detection, intrinsics/extrinsics, device store, print verification, diagnostics, floor transform, per-session calibration.
- `app/services/lifting/` — Halpe26 to H36M17 conversion, normalisation, `Lifter` protocol with `MotionBertAdapter` and `StubLifter`, `pipeline.py`, 3D angles, metric scale, guards, muscle overlay, viewer export.
- `app/models/` — Halpe26 keypoint constants, task configuration, calibration models.
- `app/tools/` — CLIs: `generate_board`, `calibrate_device`, `extract_gait2392_muscles`.
- `app/utils/math_utils.py` — angle and vector helpers.
- `app/static/` — browser interface (upload, results, 3D viewer with muscle overlay).
- `tests/` — 105 tests covering the API contract, kinematics, lifting, calibration, muscles, smoothness, symmetry.

---

## What works today

- **2D analysis (always).** RTMPose Halpe26 on sampled frames, smoothed angle series, min/max/ROM, screening. Annotated MP4 returned.
- **Both legs analysed on every clip.** Side-prefixed metric keys; risk level from the worse leg.
- **Smoothness.** LDLJ, SPARC, and movement-unit count per side.
- **Symmetry.** Implemented, but scoped to a single clip — which is the wrong basis. Being rebuilt as a cross-recording comparison in P4.
- **Optional 3D.** MotionBERT ONNX lift, 3D hip and knee angles, metric scale, camera-to-floor transform. Best-effort: any failure falls back to 2D and reports the mode. **Frequently falls back in practice.**
- **Optional ChArUco calibration.** Per-device intrinsics and per-session floor plane. Being demoted to optional in P2 — bone length replaces it as the scale source.
- **Muscle overlay.** Five muscle groups per leg on the 3D skeleton, coloured by a kinematic length proxy. Display only — never force or activation.
- **FAKE_MODE.** Contract-shaped response without inference; used by tests.

**Not built:** bone-length input and scale, angle trajectories in the response, angular velocity and
acceleration, the hard-reject quality guard, `tracking_stability_score`, session storage, and the
comparison endpoints. All scheduled in `docs2/04-planning.md`.

**Empty by design:** `gait_parameters` and `compensation`.

---

## Ground-truth facts

- MotionBERT weights: **`models/target/motionbert_lite_sim.onnx`** (~64 MB, gitignored). ONNX input name is `keypoints_2d`.
- `ENABLE_3D` defaults to `false` in `.env.example`; the local `.env` sets it to `true`.
- Sample clips at repo root: `calib.mp4`, `knee_flex_calib.mp4`, `knee_flex_nocalib.mp4`.
- Python 3.11 or newer (3.13 in use). Package manager is `uv`.
- Run with `uv run python -m app`, never `uvicorn` directly — Ctrl+C hangs on Windows otherwise.
- Ankle tasks are **2D permanently** with the current lifter: the H36M-17 skeleton has no toe joint.
- Joint angles are **scale-invariant**, so they stay valid even when metric scale is unavailable.

---

## Conventions

- **Honest naming.** Inferred quantities get the `estimated_` prefix. Never present an estimate as a measurement.
- **Best-effort, never break.** Optional paths degrade to the simpler result. The single deliberate exception is the quality-rejection guard.
- **Testable core.** Analysis code does not import service or presentation code.
- Model weights, exports, and sources live under `models/` (`models/target/` is gitignored).
- **We do not download models or clone repos for the user.** Setup steps are written into docs as CLI guidance.
- Update the affected `docs2/` file in the same change as the code.

---

## Key decisions already made

Do not relitigate these without a reason. Full reasoning is in `docs2/01-specification.md`.

| Decision | Choice |
|----------|--------|
| Metric scale | Hospital-measured **bone lengths**, per side. The ChArUco board is demoted to optional |
| 2D versus 3D | **3D-first as the target**; 2D sagittal is the validated path running today. Report which produced the result |
| Deployment | **Standalone localhost**, with the response kept integration-ready for a future backend |
| History storage | **SQLite**, local, metrics only — never video |
| Symmetry and progress | **Separate query endpoints** over stored results, never computed inside an analysis response |
| Screening layer (5-STS, gait speed, TUG) | **Out of scope** this round |
| CT muscle data | Team 6's work. Out of scope now, not blocked for later |

---

## Task sync note

The movement task set must stay in sync across three files:

- This repo: `app/models/task_config.py`
- Frontend: `movementTasks.ts`
- Backend: `movement_tasks.py`
