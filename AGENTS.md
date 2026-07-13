# AGENTS.md

## Module Map

- `app/main.py`: FastAPI app, lifespan, routes, and exception handlers.
- `app/core/`: settings, security, and logging.
- `app/schemas/`: request enums and response models.
- `app/services/`: video handling, pose adapters, kinematics, quality, screening, and response mapping.
- `app/models/`: keypoint constants and task configuration.
- `app/utils/`: math and file helpers.
- `tests/`: API contract, auth, response mapper, and kinematics tests.

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

## Scope Note

### Browser Video Playback Fix

- Changed files: `app/main.py`, `app/static/index.html`, `app/static/app.js`.
- What each file does: `main.py` serves the annotated MP4; `index.html` defines the result video player; `app.js` assigns and reloads the generated video URL.
- What changed: served annotated videos with `Content-Disposition: inline`, added browser playback attributes/source metadata, and explicitly called `load()` after receiving the result URL.
- Current progress: annotated skeleton videos should render and play in the demo UI instead of being treated as downloads.
- Remaining: verify with a real RTMPose inference run in the target browser; codec support may still depend on the local OpenCV build.

V1 is a local decision-support/demo service. It is not a clinical diagnosis system.

## Task Sync Note

The movement task set must stay in sync across three files:

- This repo: `app/models/task_config.py`
- Frontend: `movementTasks.ts`
- Backend: `movement_tasks.py`
