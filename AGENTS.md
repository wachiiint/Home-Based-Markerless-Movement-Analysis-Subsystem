# AGENTS.md

## Module Map

- `app/main.py`: FastAPI app, lifespan, routes, and exception handlers.
- `app/__main__.py`: `python -m app` server runner; sets `timeout_graceful_shutdown` so Ctrl+C stops the server on Windows.
- `app/core/`: settings, security, and logging.
- `app/schemas/`: request enums and response models.
- `app/services/`: video handling, pose adapters, kinematics, quality, screening, and response mapping.
- `app/services/calibration/`: ChArUco-on-A4 detection, intrinsics/extrinsics, print-verify, board diagnostics, floor transform, and per-session calibration.
- `app/services/lifting/`: Halpe26->H36M17 conversion, normalization, MotionBERT/stub lifters, 3D angles, metric scale, and guards.
- `app/models/`: keypoint constants, task configuration, and calibration models.
- `app/tools/`: CLI utilities — `generate_board` (ChArUco A4 PDF), `calibrate_device` (per-device intrinsics), and `extract_gait2392_muscles` (OpenSim gait2392 `.osim` → muscle-anchor JSON for the viewer overlay).
- `app/utils/`: math and file helpers.
- `tests/`: API contract, auth, response mapper, kinematics, lifting, board render, and 3D video-analysis tests.

## Current Work Log

### Phase 1-2 Scaffold and API Skeleton

- Changed files: all initial project files under `rtmpose-movement-analysis-service/`.
- What each file does: docs define setup, API contract, project flow, implementation plan, and evaluation plan; app modules implement config, auth, response schemas, and a `FAKE_MODE` contract response.
- What changed: created a new standalone FastAPI repository from scratch through Phase 2.
- Current progress: scaffold and API-compatible skeleton are implemented; `uv run pytest` passes with 9 tests.
- Remaining: RTMPose video inference, biomechanics processing, quality metrics, and full test implementation in later phases.

### Phase 3-4 RTMPose Demo UI

- Changed files: `app/main.py`, `app/core/config.py`, `app/schemas/response.py`, `app/services/pose_estimator.py`, `app/services/video_io.py`, `app/services/video_analysis.py`, `app/services/subject_selector.py`, `app/static/index.html`, `app/static/styles.css`, `app/static/app.js`, `.env.example`, `README.md`, and demo tests.
- What each file does: the service modules load RTMPose, process sampled video frames, compute angles/quality/screening, and store temporary annotated output; static files provide the browser test workflow; docs describe local setup and limits.
- What changed: implemented real `rtmlib.BodyWithFeet` inference, skeleton-overlay MP4 generation, ROM analysis, temporary result URLs, browser-safe demo endpoints, responsive upload/results UI, and configuration for upload/result limits.
- Current progress: local web demo and real inference pipeline are implemented; existing API contract tests pass.
- Remaining: run an end-to-end real-model test with network/model cache available and tune inference speed/thresholds against more movement samples.

### 3D Roadmap Phase A-C (single-camera 3D groundwork)

- Goal: extend the 2D pipeline toward single-camera 3D + CT-driven muscle simulation. Each phase is standalone and not yet wired into `analyze_video`.
- Phase A (`app/services/pose_sequence.py`, `video_analysis.py`): split `analyze_video` into two passes; pass 1 collects the full-clip main-subject 2D poses into a `PoseSequence`, pass 2 computes angles from it. Behavior/API unchanged.
- Foot-index bugfix (`app/models/keypoints.py`): the Halpe26 foot indices were shifted by the head/neck/hip block, so ankle tasks measured the angle from the head; corrected to the authoritative order (big_toe 20/21, small_toe 22/23, heel 24/25) and added HEAD/NECK/HIP/NOSE/ELBOW/WRIST constants.
- Phase B (`app/services/calibration/`, `app/models/calibration.py`): ChArUco-on-A4 calibration. Per-device intrinsics (persisted, resolution-keyed, stale on mismatch) + per-session extrinsics/floor plane; print-verify corrects printer scaling; detection is separated from pose/intrinsic math so metric recovery is testable via synthetic projection. Requires `opencv-contrib-python` (aruco).
- Phase C (`app/services/lifting/`): Halpe26->H36M17 conversion (mid-spine synthesised), screen-coordinate normalization, a `Lifter` protocol with a `MotionBertAdapter` (ONNX I/O contract, needs weights) and a `StubLifter`, and a pipeline bridging `PoseSequence` -> convert -> normalize -> lift.
- Phase D (`video_analysis.py`, `response_mapper.py`, `main.py`, `app/services/lifting/{angles_3d,metric_scale,guards}.py`, `app/services/calibration/{session,board_diagnostics,transform}.py`): wires calibration + lifting into `analyze_video`. D1 startup wiring + ONNX-validation guard; D2 per-session ChArUco calibration with board diagnostics; D3 metric scale (feet ray-plane + height fallback + cross-check guard); D4 3D hip/knee angles (ankle stays 2D); D5 camera->floor 6DoF + schema; D6 assembly with graceful 2D fallback + `analysis_mode` flag + bone-length guard. All 3D work is best-effort/try-guarded so the endpoint always returns the 2D result. New response fields (additive): `analysis_mode`, `clinical_metrics.joint_angles_3d`/`scale_mm_per_unit`/`scale_source`, real `transformation_matrix_6dof`, `board_diagnostics`, `guard_warnings`; request gained optional `subject_height_mm`.
- Status update (2026-07-22): both former blockers are now cleared — see "3D Enablement & Calibration Validation" below. MotionBERT weights are present and 3D runs end-to-end. The print-scale direction bug and the make/model device-id gap are now **fixed**; the resolution-match constraint and Phase E remain. `smoothness` is now populated (see "Smoothness" below).

### 3D Enablement & Calibration Validation (2026-07-22)

- Weights present: `models/motionbert_lite.onnx` (64 MB). `.env` sets `ENABLE_3D=true` + `MOTIONBERT_MODEL_PATH=models/motionbert_lite.onnx` (`.env.example` keeps `ENABLE_3D=false` as the safe default). ONNX input name is `keypoints_2d`; `validate_lifter_io()` passes; `build_lifter` returns a working `MotionBertAdapter` and `pose_3d` is populated end-to-end.
- First successful metric-3D run (clip3.mp4, 1080x1920, seated knee extension, board flat on floor): `analysis_mode=3d`, `joint_angles_3d={knee_flexion_max 173.59, min 71.83, rom 101.76}` (sensible), real `transformation_matrix_6dof` present, `scale_mm_per_unit=2419 (feet_floor)`, `board_diagnostics.recommendation=ok` (board detected in 150/152 frames). Two non-blocking `guard_warnings`: device_id derived from resolution only (low confidence), and scale_uncertain (feet-floor 2419 vs height 2015.7 differ ~17%). Joint angles are scale-invariant, so they are trustworthy despite the scale uncertainty.
- Integration gaps:
  1. (SURFACED, not eliminated) Resolution must match between the calibration clip and the patient clip because `device_id` is keyed on resolution (width×height are hashed into the id); the board also only reads reliably at 1080p (540p oblique gave 0 markers). Calibrate at the same resolution as the patient clip. The demo no longer fails *silently*: the device picker warns before submit when the selected device's resolution ≠ the uploaded clip's, and the analysis panel shows a post-run notice (from `guard_warnings`/`board_diagnostics`) explaining any 2D fallback — see "Calibration Guard Surfacing" below.
  2. (FIXED) make/model device-id gap: the assess request now accepts optional `device_make`/`device_model` form fields (`main.py`), passed through `analyze_video` into `extract_capture_metadata`, so a device calibrated with `--make/--model` matches without the resolution_only workaround.
  3. (FIXED) print-scale direction: `print_verify.compute_print_scale` now returns `factor = measured/nominal` (was `nominal/measured`), with an updated docstring and the `test_print_scale_direction_recovers_metric_translation` synthetic-projection regression test.
- Test clips on disk: `clip.mp4` (540p, patient sitting, no board), `clip2.mp4` (540p, knee ext, board oblique/unreadable), `clip3.mp4` (1080p, knee ext, board readable — the good patient clip), `calib.mp4` (1080p, multi-angle calibration clip).
- Remaining: Phase E (motion export + muscle params schema); the muscle-overlay demo (M-A, in progress).

### Ctrl+C Shutdown Fix (2026-07-23)

- Changed files: `app/__main__.py` (new), `README.md`, `docs/01-getting-started.md`.
- Symptom: on Windows, `uv run uvicorn app.main:app` hung at "Shutting down" after Ctrl+C and the
  shell had to be killed. Cause: uvicorn's default `timeout_graceful_shutdown=None` waits forever for
  lingering connections, and an open browser tab / paused `<video>` (keep-alive + range requests)
  never closes on its own. The signal *was* received (shutdown started) — it just never finished.
- Fix: a `python -m app` runner calls `uvicorn.run(..., timeout_graceful_shutdown=5)` so Ctrl+C
  force-closes stragglers after 5s. Docs now recommend `uv run python -m app` (PORT env var);
  the raw-uvicorn alternative gets `--timeout-graceful-shutdown 5`.
- The `ConnectionResetError [WinError 10054]` traceback on video seek is separate and harmless
  (ProactorEventLoop noise when the browser resets a range-request socket), not the hang.

### Calibration Guard Surfacing (2026-07-23)

- Changed files: `app/static/{index.html,app.js,styles.css}` only (no backend change — the warnings
  already existed in `CameraCalibration.warnings` -> `guard_warnings`, they just were not shown).
- Problem: `guard_warnings`, `board_diagnostics`, and `analysis_mode` were all in the payload but the
  demo rendered none of them, so a calibrated-3D run that fell back to 2D (most often a resolution
  mismatch — `device_id` hashes width×height, so a different resolution = "device not calibrated")
  looked like a silent, unexplained 2D result.
- What changed:
  - Proactive: the 01/INPUT device picker stores each device's `image_size` on the option and, on
    file/device change, compares it to the uploaded clip's `videoWidth×videoHeight`; a mismatch shows
    an amber hint *before* submit. Best-effort (browser dims can differ from the backend for rotated
    clips); the authoritative reason still comes post-run.
  - Post-run: `renderAnalysisNotice` shows a green "Metric 3D active" note when `analysis_mode==3d`,
    or an amber "2D analysis — metric 3D unavailable: <reasons>" note built from `guard_warnings` +
    `board_diagnostics.message` otherwise.

### Muscle Overlay (M-A) (2026-07-23)

- Changed files: `app/services/lifting/muscles.py` (new), `app/services/lifting/pose3d_export.py`,
  `app/static/{viewer3d.js,index.html,app.js,styles.css}`, `tests/test_muscles.py` (new).
- What it does: a labeled, kinematic **muscle-length overlay** on the 3D skeleton viewer.
  `compute_muscle_overlay(keypoints_3d)` models 5 major lower-limb muscles per leg (quadriceps,
  hamstrings, gastrocnemius, iliopsoas, gluteals) as length proxies driven by the H36M17 joint angles
  (knee = angle(hip,knee,ankle); hip = angle(thorax,hip,knee)). Each muscle's length is min-max
  normalized to `[0, 1]` over the clip and ships in the `pose_3d` payload under `muscles`.
- Honesty: DISPLAY ONLY and explicitly a *geometry* proxy — a single camera has no GRF, so muscle
  *force/activation* is not computed. Physiological length *direction* is correct (a knee extensor
  stretches as the knee flexes); the drawn tube geometry is illustrative. Kept out of
  `MovementAssessmentResponse`; rides only the demo display payload.
- Viewer (`viewer3d.js`): each muscle is a smooth **curved tube** (CatmullRom through its anchors)
  with a tendon→belly→tendon radius taper and a sideways belly bulge — reads as muscle, not a stick.
  Colored contracted (warm) → stretched (cool) per frame. Toggle button + gradient legend; hidden
  unless the payload carries muscles (any real lift does — calibration not required, only the lift).
  The synthetic "Preview 3D" sample (`sample_skeleton.js`) mirrors the same `muscles`/anchor structure
  in JS (mirroring `muscles.py` — keep in sync), so the overlay shows without a real clip.

### Muscle Anatomy: anchors + gait2392 (2026-07-23)

- Changed files: `app/services/lifting/muscles.py`, `app/tools/extract_gait2392_muscles.py` (new),
  `app/static/{viewer3d.js,sample_skeleton.js}`, `tests/test_muscles.py`, `docs/03-pipeline.md`.
- Shape/colour decoupled: **shape** = ordered *anchors*, each a fraction `t` along a bone segment
  (`[jointA, jointB, t]`) so the path bends with the limb (along-bone placement is the
  single-camera-robust coordinate); **colour** = the same angle-driven length proxy as before.
  Payload per muscle is now `{name, side, anchors, bulge, length}` (was `{joints, offset, length}`).
- Anatomy source: `active_muscles()` loads `models/gait2392_muscles.json` if present, else a built-in
  anatomically-*approximate* table. The JSON is produced offline (no OpenSim runtime) by
  `app/tools/extract_gait2392_muscles.py --osim gait2392_simbody.osim` — it parses the `.osim` XML,
  keeps a curated muscle set (`_CURATED`), and projects each path point onto the matching bone as a
  fraction `t`. gait2392 `.osim` is NOT fetched by us (guide-don't-fetch); the user downloads it and
  the JSON lands under `models/` (models-dir convention). Path override via `GAIT2392_MUSCLES_PATH`.
- Honest scope (see `docs/03-pipeline.md` §4.5): gait2392 gives real *paths*, but its muscles need
  full 3D multi-DOF kinematics; the single-camera lift only reliably observes sagittal hip/knee
  flexion → quad/hamstring reads reasonable, rotation/abduction/foot muscles indicative only. It's a
  kinematic length estimate, **not** a validated gait2392 simulation. Force needs a force plate — out
  of scope no matter the model.
- Tests (`test_muscles.py`): existing length-direction/static/both-legs/empty tests + anchor-shape
  checks + `extract()` against a synthetic `.osim` + gait2392-table override via env.
- Extractor dedup fix: it stripped `_r`/`_l` and matched both, emitting every muscle twice (10 vs 5);
  now skips `_l` (geometry is side-agnostic — the app draws both legs itself). Regression-tested.
- **Validated end-to-end (2026-07-23):** real run of `knee_flex_calib.mp4` with the calibrated
  `samsung s22` device (1080×1920) → 2D both legs correct (left knee ROM 95.3°, right 112.8°),
  `analyzed_side=both`, symmetry 0.084; the `pose_3d` payload carried all 5 gait2392 muscle groups
  ×2 legs, anchors matching `models/target/gait2392_muscles.json`, and rendered in the viewer.
  Metric 3D stayed 2D on this clip (monocular lift flagged: `l_femur cv=0.30`) — graceful fallback as
  designed; muscles/overlay ride the lift regardless (shown with the "unreliable" flag).
- **Status: M-A muscle overlay (built-in + gait2392) is DONE.**

### Smoothness (2026-07-22)

- Changed files: `app/services/analysis/smoothness.py` (new), `video_analysis.py`, `response_mapper.py`,
  `app/static/app.js`, `tests/test_smoothness.py` (new).
- What it does: fills the previously-empty `clinical_metrics.smoothness` field from the per-frame
  joint-angle series (single-camera-safe — no GRF needed). Reports `sparc` (spectral arc length; less
  negative = smoother), `log_dimensionless_jerk` (higher = smoother), `n_movement_units` (speed peaks),
  and `n_samples`. Computed on the EMA-smoothed angle series at `frame_sample_fps`; returns `{}` when
  there are too few frames or no movement (stays a best-effort placeholder). Shown in the demo analysis
  panel. `build_fake_response` leaves it `{}`. (As of the both-legs change it is nested per side:
  `{"left": {...}, "right": {...}}`.)
- Remaining placeholders (still empty by design): `gait_parameters` (needs a walking task +
  foot-contact detection), `compensation` (multi-joint). See the roadmap table below.

### Symmetry (2026-07-23)

- Changed files: `app/services/analysis/symmetry.py` (new), `video_analysis.py`, `response_mapper.py`,
  `app/static/app.js`, `tests/test_symmetry.py` (new), `tests/test_video_analysis_3d.py`.
- What it does: fills `clinical_metrics.symmetry_index_score` with a normalized left/right asymmetry
  index in `[0, 1]` — `|ROM_left - ROM_right| / (ROM_left + ROM_right)` (Robinson & Herzog Symmetry
  Index rescaled from percent; `SI% = score * 200`). `0.0` = both legs swept an identical range;
  toward `1.0` = one leg did nearly all the moving.
- Side-select refactor (the Q2 dependency): per-side ROM is computed once for both legs and reused by
  side selection and symmetry. (Superseded by the both-legs change below: this now lives in
  `_analyze_both_legs`/`LegAnalysis`, and `_select_analyzed_side` takes that per-leg dict.) Per-side
  ROM is measured on the EMA-smoothed series (matches the reported ROM).
- Honest abstention: `compute_symmetry` returns `None` unless BOTH legs performed the movement
  (each side's ROM ≥ the task's `borderline_rom_deg` and ≥ 4 valid frames). The unilateral task set
  moves one leg while the other rests, so it abstains for those clips rather than reporting a spurious
  ~1.0; it yields a real number only when both legs move (future bilateral task or a patient
  exercising both sides in one clip). Shown as "Asymmetry (L/R) %" in the demo panel.
  `build_fake_response` leaves it `None`.

### Both-Legs Reporting (2026-07-23)

- Changed files: `video_analysis.py`, `response_mapper.py`, `app/static/{app.js,index.html,styles.css}`,
  `tests/test_video_analysis_3d.py`.
- Rationale: finding "the" exercised leg and reporting only it hides the other side from the clinician.
  We now analyze BOTH legs and report each; the doctor reads left vs right and decides. (The request/UI
  still carry no `side` input — there was never one — so nothing about the instructed side is lost.)
- What changed:
  - `_analyze_leg` / `_analyze_both_legs` compute full per-leg 2D analysis (min/max/ROM, per-leg
    valid-frame ratio + confidence, per-leg smoothness) for each usable leg. `LegAnalysis` is the
    single source of truth for the report, side selection, symmetry, and screening.
  - `clinical_metrics.joint_angles` now has **side-prefixed keys** (`left_knee_rom_deg`,
    `right_knee_rom_deg`, …) — still `dict[str, float]`, so the contract shape is unchanged.
    `response_mapper` gained a `joint_angles_override` param; the single-side form still serves
    `build_fake_response` and the contract test.
  - `smoothness` is now nested per side (`{"left": {...}, "right": {...}}`).
  - Screening (`_screen_both_legs`): each leg is screened; the top-line `risk_level` is the **worse**
    leg, and `flags` are side-tagged (e.g. `right: rom_below_borderline`).
  - `video_metadata.analyzed_side` is `"both"` when two legs are usable, else the single side.
  - `_select_analyzed_side` is kept but demoted to picking a *primary* leg (larger ROM) only for the
    3D-viewer highlight and the representative `pose_quality` reading.
  - `joint_angles_3d` also reports **both legs** (side-prefixed `_3d` keys, e.g.
    `left_knee_rom_deg_3d`): `_augment_with_3d` takes `report_sides` and loops the usable legs
    (H36M17 carries both). Surfaced as "… (3D)" rows in the Panel 3 table when calibrated.
  - Demo Panel 3 (`03 / ANALYSIS`) is now a compact, scrollable **Left vs Right comparison table**
    (`renderComparison` in `app.js`, `.compare-table` CSS), replacing the flat metric grid.

## Roadmap / Task Plan (2026-07-22)

Plain-language: single camera gives **no ground reaction force**, so real muscle *force/activation* is
not computable — muscle work here is kinematic (geometry/angle-driven) only. Joint *angles* are
scale-invariant, so they are trustworthy regardless of the metric-scale path.

| ID | Task | Effort | Depends on | Risk | Priority | Benefit | Done |
|----|------|--------|-----------|------|----------|---------|------|
| F1 | Fix print-scale direction bug | ~0.5d | — | Low | High | Correct metric distances | [x] |
| F2 | Surface per-frame angle trajectory | ~0.5–1d | — | Low | High | Unlocks smoothness + motion export | [x] |
| Q1 | `smoothness` from angle curve (SPARC/LDLJ/units) | ~1–2d | F2 | Low–Med | High | Fills a real placeholder, clinically meaningful | [x] |
| Q2 | `symmetry_index_score` (both sides) | ~2–3d | side-select refactor | Med | Medium | Left/right asymmetry indicator | [x] |
| Q3 | `gait_parameters` (cadence, step/stride) | ~4–6d | new walking task + foot-contact + F1 | High | Low | Only meaningful for gait clips | [ ] |
| Q4 | `compensation` (trunk lean, hip hike) | ~3–5d | multi-joint analysis | High | Low | Fuzzy clinical definition | [ ] |
| M-A | Visual muscle overlay on 3D skeleton (kinematic proxy, labeled) | ~3–5d | working 3D viewer | Med | High (demo) | Impressive demo now, no OpenSim needed | [x] |
| M-B | OpenSim `gait2392` **kinematics-only** export — IK + muscle length/moment-arm (`.mot` + muscle-param schema), **no force** | ~1.5–3wk | F2, marker/coord map, OpenSim dep | High | Medium | Scientifically-grounded muscle data | [ ] |
| BH | Highlight the detected ChArUco board in the annotated video (+ optional floor marker in the 3D viewer) | ~1–2d | session calibrator | Low | Medium (UX) | Lets the user see the board is being read | [ ] |
| CT | CT-driven muscle F0 (PCSA) | — | CT scan (unavailable) | — | Deferred | Patient-specific muscle force | [ ] |

Notes: `pose_quality` is already computed (not a placeholder). Muscle *force* needs GRF/force plate →
out of scope for single camera; both M-A and M-B show muscle *geometry/length*, not force. The board
gives **scale/floor only** — it does not feed the 3D lift (see `docs/03-pipeline.md` §4.1, §4.6).

## Scope Note

### Browser Video Playback Fix

- Changed files: `app/main.py`, `app/static/index.html`, `app/static/app.js`.
- What each file does: `main.py` serves the annotated MP4; `index.html` defines the result video player; `app.js` assigns and reloads the generated video URL.
- What changed: served annotated videos with `Content-Disposition: inline`, added browser playback attributes/source metadata, and explicitly called `load()` after receiving the result URL.
- Current progress: annotated skeleton videos should render and play in the demo UI instead of being treated as downloads.
- Remaining: verify with a real RTMPose inference run in the target browser; codec support may still depend on the local OpenCV build.

This is a local decision-support/demo service. It has grown past the original v1 scope — it now does
2D + single-camera 3D, ChArUco calibration, smoothness, left/right symmetry, and both-legs reporting.
It is still **not** a clinical diagnosis system.

### Literature Review and Master Requirement Alignment

- Changed files: `docs/Project101_Team5.md`, `docs/Project101_Team5.pdf` (restored from `main`), `EVALUATION_PLAN.md`.
- What each file does: `Project101_Team5.md`/`.pdf` is the Team 5 project proposal defining the full
  clinical feature set and the `clinical_metrics`/`screening_result`/`transformation_matrix_6dof`
  JSON contract that this service's `app/schemas/response.py` already mirrors in shape (this branch
  had dropped `docs/` when the RTMPose edition was split out from scratch); `EVALUATION_PLAN.md` now
  records literature-derived validation risks under "Literature-Informed Validation Risks".
- What changed: reviewed six published papers on smartphone/webcam movement assessment, pose
  estimation accuracy, real-time musculoskeletal analysis, and Hill-type muscle model instability
  (`dump/paper/Lower-limb tele-assessment manuscripts/`), and cross-checked their findings against
  `app/services/kinematics.py`, `screening.py`, `smoothing.py`, and `app/models/task_config.py`.
- Current progress: risks and the master requirement doc are documented; no changes to the
  inference/screening pipeline itself.
- Remaining: decide whether to add a per-joint/view correction step before
  `three_point_angle` -> `screen_rom`, and whether/how to empirically validate
  `expected_rom_deg`/`borderline_rom_deg` in `task_config.py`. Of the master schema's initially-empty
  fields, `smoothness` and `symmetry_index_score` are now populated (see the sections above);
  `gait_parameters` and `compensation` remain empty by design (see the roadmap table).

## Task Sync Note

The movement task set must stay in sync across three files:

- This repo: `app/models/task_config.py`
- Frontend: `movementTasks.ts`
- Backend: `movement_tasks.py`
