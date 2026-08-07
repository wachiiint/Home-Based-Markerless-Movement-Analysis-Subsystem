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

A local FastAPI service for home-based markerless movement analysis. Sarcopenia screening in the
elderly is the first use case; the final goal is a movement-analysis tool usable with anyone. A
patient records a short clip of one prescribed leg movement; the service returns joint angles, ROM,
smoothness, quality metrics, and a screening indicator, plus an annotated skeleton video and a 3D
motion simulation.

**Decision support, not diagnosis.** Runs entirely locally.

---

## Module map

- `app/main.py` — FastAPI app, lifespan, routes, exception handlers.
- `app/__main__.py` — `python -m app` runner; sets `timeout_graceful_shutdown` so Ctrl+C stops the server on Windows.
- `app/core/` — settings (`config.py`), API-key auth (`security.py`), logging.
- `app/schemas/` — request enums (`movement.py`) and response models (`response.py`).
- `app/services/video_io.py`, `video_analysis.py`, `response_mapper.py` — frame sampling, the analysis orchestrator, response assembly.
- `app/services/csv_export.py` — flat CSV views of the export payloads.
- `app/services/session_store.py` — the local store of completed analyses under `data/sessions/`.
- `app/services/pose/` — `pose_estimator.py` (RTMPose via rtmlib), `pose_sequence.py`, `subject_selector.py`, `pose2d_export.py`.
- `app/services/analysis/` — `kinematics.py`, `smoothing.py`, `screening.py`, `smoothness.py`, `symmetry.py` (single-clip, superseded), `asymmetry.py` (across two recordings).
- `app/services/asymmetry_report.py` — the seam between the session store and `analysis/asymmetry.py`.
- `app/services/calibration/` — ChArUco board handling: rendering, detection, intrinsics/extrinsics, device store, print verification, diagnostics, floor transform, per-session calibration.
- `app/services/lifting/` — Halpe26 to H36M17 conversion, normalisation, `Lifter` protocol with `MotionBertAdapter` and `StubLifter`, `pipeline.py`, 3D angles, metric scale, guards, muscle overlay, viewer export.
- `app/models/` — Halpe26 keypoint constants, task configuration, calibration models.
- `app/tools/` — CLIs: `generate_board`, `calibrate_device`, `extract_gait2392_muscles`.
- `app/utils/math_utils.py` — angle and vector helpers.
- `app/static/` — browser interface. `index.html`/`app.js` is the analysis page (upload, results,
  3D viewer with muscle overlay); `calibrate.html`/`calibrate.js` is the separate `/calibrate` page;
  `compare.html`/`compare.js` is the `/compare` page, which picks two stored sessions and reads the
  difference between the legs. `anglechart.js` is the angle-through-time graph, shared by both pages;
  `viewer3d.js` is the 3D skeleton renderer, likewise.
- `tests/` — 192 tests covering the API contract, kinematics, lifting, calibration, muscles, smoothness, symmetry, asymmetry, trajectory, exports, session storage.

---

## What works today

- **2D analysis (always).** RTMPose Halpe26 on sampled frames, smoothed angle series, min/max/ROM, screening. Annotated MP4 returned.
- **Outlier rejection on the angle series.** Hampel filter (local median/MAD) before smoothing, so a
  few frames of left/right tracking swap cannot corrupt min/max/ROM. Heavy rejection is reported as
  `heavy_tracking_noise` rather than hidden. Does **not** catch a swap that outlasts the window.
- **Both legs analysed on every clip.** Side-prefixed metric keys. The request's mandatory `side` says
  which leg was instructed; **only that leg is screened**, the other is a contralateral reference.
  A mismatch between the declared side and the leg that actually moved is reported, never auto-corrected.
- **Smoothness.** LDLJ, SPARC, and movement-unit count per side.
- **Angle trajectory and its graph.** The response carries a top-level `trajectory` — the smoothed
  angle per sampled frame for both legs on one time axis, `null` where a leg was not confidently
  visible. It is the same series min/max/ROM were read from, so the graph and the numbers agree. The
  demo UI plots it as inline SVG (no chart library) with a hover readout, and offers it as its own
  per-frame CSV; the metrics CSV deliberately leaves it out.
- **Asymmetry across two recordings.** One clip per leg, each contributing **only** the leg it was
  instructed to move — the far leg in a lateral view is occluded and foreshortened, so pairing it
  against the near leg measures camera distance as much as the patient. `GET /api/demo/compare` and
  its own `/compare` page. Uses the Zifchock symmetry angle (bounded ±50%, no reference leg needed —
  in bilateral decline there is no sound limb to divide by) and reports the plain difference beside
  it. A mismatched pair — different patient, task, view, or two clips of the same leg — is **refused**,
  not reported. **No threshold and no verdict**, and none until the test–retest repeatability study
  says how much of a gap is filming noise. The old single-clip `symmetry_index_score` is still in the
  analysis response and is still wrongly scoped; it is superseded and slated for removal in P4.
  The page also carries the angle graph — one line per leg, each from its own clip, on a shared axis
  but **not a shared clock** (the caveat is printed under the chart) — and the 3D viewer, which shows
  **one recording at a time** behind a left/right selector rather than overlaying the two skeletons.
- **Optional 3D.** MotionBERT ONNX lift, 3D hip and knee angles, metric scale, camera-to-floor transform. Best-effort: any failure falls back to 2D and reports the mode. **Frequently falls back in practice.**
- **Optional ChArUco calibration.** Per-device intrinsics and per-session floor plane. Runs from its
  own UI page at `/calibrate` (or the `calibrate_device` CLI), not from the analysis page. **Staying
  as the PoC's calibration and metric-scale path** (2026-08-07) — the earlier plan to demote it in
  favour of bone lengths is postponed to the prototype phase.
- **Muscle overlay.** Five muscle groups per leg on the 3D skeleton, coloured by a kinematic length proxy. Display only — never force or activation.
- **Artifact export from the demo UI.** The `03 / ANALYSIS` panel offers the assessment metrics, the
  plotted angle series, the raw 2D keypoint sequence (Halpe26 pixel coords, scores, skeleton edges, plus the settings needed to replay
  the run), and the 3D skeleton — each as **CSV**, the format a person opens and reads. The complete
  JSON record is still written and served, but its URL travels in the response instead of getting a
  button. CSV is a lossy view generated per request from the stored JSON (`csv_export.py`); it drops
  topology and settings and so cannot replay a run. **Re-importing a saved file is not built** — export only.
- **Results are stored and kept.** Every completed analysis is written to
  `data/sessions/<patient_id>/<timestamp>-<session_id>/` and summarised in an append-only
  `index.jsonl` (`session_store.py`). The demo page has a history list: `GET /api/demo/sessions`
  lists them, `GET /api/demo/sessions/{id}` reopens one in the same payload shape a fresh analysis
  returns, so past and new results render through one code path. Nothing expires
  (`DEMO_RESULT_TTL_SECONDS=0`); the TTL is a setting, not a deleted code path. The **uploaded clip is
  never stored**; the annotated render is, unless `KEEP_ANNOTATED_VIDEO=false`. This file store **is**
  the storage — the once-planned SQLite layer was cancelled on 2026-08-07.
  **Progress comparison between sessions is not built** — the asymmetry half of P4 has shipped (see
  above); comparing a session against an earlier baseline of the same leg has not.
- **FAKE_MODE.** Contract-shaped response without inference; used by tests.

**Not built:** bone-length input and scale, angular velocity and acceleration, the hard-reject
quality guard, `tracking_stability_score`, re-import of exported results, and comparison against a
patient's own history. See `docs2/04-planning.md` section 0 for what still closes the PoC.

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
| Target population | **Elderly sarcopenia screening first; final goal is anyone** (advisor, 2026-08-04). ROM thresholds are confirmed for the elderly only — other populations are a backlog item |
| Metric scale | **ChArUco board for the PoC** (re-adopted 2026-08-07). Hospital-measured bone lengths per side move to the prototype phase; MRI import stays in the backlog |
| 2D versus 3D | **3D-first as the target**; 2D sagittal is the validated path running today. Report which produced the result |
| Deployment | **Standalone localhost**, with the response kept integration-ready for a future backend |
| Project phase | **Proof of concept, concluding** (2026-08-07). Demonstrated: camera-only movement analysis for tele-rehabilitation. Next: a prototype-phase proposal mixing the PoC summary with the professor's proposal (IMU ground truth, keypoint model training, a more solid application) |
| History storage | **Local files plus export/re-import** (options B + D, 2026-08-07). SQLite cancelled — the file store under `data/sessions/` is the storage. Metrics and renders only, never the uploaded clip |
| Symmetry and progress | **Separate query endpoints** over stored results, never computed inside an analysis response |
| Screening layer (5-STS, gait speed, TUG) | **Out of scope** this round |
| CT muscle data | Team 6's work. Out of scope now, not blocked for later |

---

## Task sync note

The movement task set must stay in sync across three files:

- This repo: `app/models/task_config.py`
- Frontend: `movementTasks.ts`
- Backend: `movement_tasks.py`
