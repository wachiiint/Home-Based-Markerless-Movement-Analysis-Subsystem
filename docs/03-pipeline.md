# RTMPose Movement Analysis — Pipeline Overview

This document explains the **processing pipeline** and the **data pipeline** of this service,
so a teammate can grasp the big picture quickly before diving into the actual code.

> TL;DR: a patient records a video of a leg movement → the service receives the video → runs 2D
> pose estimation frame by frame → computes joint angles + range of motion (ROM) → screens for
> risk → (if a calibration board is present) lifts the pose to 3D → returns a fixed JSON contract
> for the doctor to review.

---

## 1. System Context

This service is **one microservice** inside a larger system. It never talks to the patient directly.

```
Patient (frontend) ──upload video──▶ Main backend
                                        │  (stores the session, calls this service via MEDIAPIPE_SERVICE_URL)
                                        ▼
                          RTMPose Movement Analysis Service  ◀── (this document)
                                        │  (returns assessment JSON)
                                        ▼
                                     Backend stores the result
                                        ▼
                                 Doctor dashboard (reads risk_level, ROM, quality)
```

- **Entry point:** `POST /api/movement/assess` (requires the `X-Internal-Service-Key` header)
- **Contract:** see [04-api-contract.md](04-api-contract.md) — the response always has 5 top-level keys
- **Demo UI:** `GET /` + `POST /api/demo/assess` (for testing it yourself; lets you view the annotated video)

File: [app/main.py](app/main.py)

---

## 2. High-Level Pipeline (End-to-End)

```
[1] Request comes in       main.py: assess_movement()
       │  validate service key, validate video, normalize view
       ▼
[2] Save a temporary file  video_io.save_upload()
       ▼
[3] Analyze the video      video_analysis.analyze_video()   ◀── the heart of the pipeline
       │
       ├─ Pass 1: 2D pose for every frame + write the annotated video
       ├─ Compute 2D angles + ROM + risk screening
       └─ Pass 2 (optional): lift to 3D if calibration is available
       ▼
[4] Assemble the response  response_mapper.build_assessment_response()
       ▼
[5] Return JSON + delete the temporary file
```

The operating mode is chosen at **startup** (`main.py: lifespan`):
- `FAKE_MODE=true` → returns fake results without loading any model (used for integration testing)
- Normal → always loads RTMPose (2D); loads the 3D lifter **only when** `ENABLE_3D=true` and the weights file passes the guard
- If 3D is unavailable → the system **degrades cleanly to 2D** and never crashes

---

## 3. Data Pipeline — How the Data Transforms

This is the most important part: the data travels from **pixels → joint angles → risk level**.

```
Video (mp4)
   │  read_video_metadata: fps, width, height, duration
   ▼
Sampled frames (reduced to ~frame_sample_fps frames/second)
   │  RTMPose BodyWithFeet inference per frame
   ▼
Keypoints for multiple people (N people × 26 Halpe26 points) + confidence scores
   │  select_main_subject: pick the "main person" (the most prominent subject)
   ▼
PoseSequence: 2D pose of a single person per frame (T frames)   ◀── the central data structure
   │
   ├──────────────── 2D path (always runs) ─────────────────┐
   │                                                         │
   │  _choose_side: pick the left/right side with higher confidence
   │  _angle_for_frame: three_point_angle() per frame        │
   │  exponential_moving_average: smoothing                  │
   │  range_of_motion: min/max/ROM                           │
   │  screen_rom: risk_level + confidence + flags            │
   │                                                         ▼
   │                                              clinical_metrics (2D)
   │
   └──────────────── 3D path (optional) ────────────────────┐
      (only when a lifter + calibration are available)       │
      sequence_to_arrays: fill gaps for frames with no person │
      halpe26_to_h36m17: convert skeleton 26→17 points        │
      normalize_screen_coordinates                            │
      MotionBERT lift: 2D → 3D (T,17,3) root-relative          │
      bone_length_consistency guard: discard if the lift is garbage │
      angle_series_3d + smoothing + ROM                       │
      resolve_metric_scale: find mm/unit from the floor or from height │
                                                              ▼
                                              joint_angles_3d + scale
```

### 3.1 Key Data Structures

| Structure | File | Meaning |
|-----------|------|---------|
| `FramePose2D` | [pose_sequence.py](app/services/pose/pose_sequence.py) | 2D pose of the main person for 1 frame (keypoints, scores, or None if no person is found) |
| `PoseSequence` | [pose_sequence.py](app/services/pose/pose_sequence.py) | all frames combined + the video's width/height |
| `Lifted3DSequence` | [lifting/pipeline.py](app/services/lifting/pipeline.py) | 3D keypoints (T,17,3) + a mask of which frames are real |
| `CameraCalibration` | [models/calibration.py](app/models/calibration.py) | intrinsics K, distortion, floor plane, board pose |
| `MovementAssessmentResponse` | [schemas/response.py](app/schemas/response.py) | the JSON contract returned to the caller |

### 3.2 Pass 1 in Detail (2D — always runs)

File: `_collect_pose_sequence()` in [video_analysis.py](app/services/video_analysis.py:52)

1. Open the video with OpenCV, create a `VideoWriter` for the annotated video
2. **Sample frames**: skip frames down to ~`frame_sample_fps` frames/second (reduces load)
3. For each sampled frame:
   - Call `frame_observer` (if calibration is on) to look for the ChArUco board
   - `estimator.infer(frame)` → keypoints + scores for everyone in the frame
   - `select_main_subject` → pick the main person
   - Draw the skeleton (`draw_skeleton`) onto the frame, then write it to the output video
   - Append a `FramePose2D` to the list
4. Return the `PoseSequence`

> **Why two passes?** Because the 3D lifter (MotionBERT) needs the **entire sequence of frames**
> at once. So we collect the whole 2D sequence first, then lift to 3D in a single step.

### 3.3 Angle Computation (2D)

- **Each task** (e.g. `knee_flexion`) defines in [task_config.py](app/models/task_config.py) which 3 points
  to use: a vertex + 2 rays. For example, the knee = the angle between hip–knee–ankle.
- `three_point_angle` → the angle in degrees per frame
- Any frame with confidence below the threshold is discarded (counted as an "invalid frame")
- `exponential_moving_average` reduces noise → `range_of_motion` gives min/max/ROM

### 3.4 Risk Screening

File: [screening.py](app/services/analysis/screening.py)

```
if valid_frame_ratio is low  → flag "low_valid_frame_ratio"
if mean confidence is low     → flag "low_keypoint_confidence"

risk = high      if any flag is set, or ROM < borderline
     = moderate  if ROM < expected
     = low        if none of the above apply

confidence_score = 0.5*valid_frame_ratio + 0.5*mean_confidence  (0..1)
```

> Planned change (P0 in [08-scope-v2.md](08-scope-v2.md)): the blend becomes
> `0.40*valid_frame_ratio + 0.40*mean_confidence + 0.20*tracking_stability_score`, and a hard-reject
> guard rejects the assessment outright below the quality floor. The formula above is what runs today.

The per-task `expected_rom_deg` / `borderline_rom_deg` values live in [task_config.py](app/models/task_config.py)

---

## 4. The 3D Path (Phase D) — In Detail

Everything lives in `_augment_with_3d()` at [video_analysis.py:120](app/services/video_analysis.py:120).
Design principle: **best-effort, never raises** — if anything breaks, it falls back to the 2D result.

### 4.1 Calibration (per session) — optional

> **Status:** the ChArUco board is an **optional** path. Angles, ROM, smoothness, symmetry, and
> screening never need it. Per [08-scope-v2.md](08-scope-v2.md), hospital-measured **bone lengths**
> become the primary metric-scale source (work item A), after which the board's remaining job is the
> floor plane and the 6DoF transform. This section describes what runs today.

File: [calibration/session.py](app/services/calibration/session.py)

- During Pass 1, every frame is fed into `SessionCalibrator.observe()` to look for the **ChArUco board**
  (a printed A4 sheet)
- It keeps the frame where the most board corners were detected
- `finalize()`:
  - Pulls the **camera intrinsics** from `DeviceStore` (identifies the camera by metadata / resolution)
  - Recovers the board's pose → yields the **floor plane** + a reprojection error
  - If the reprojection error is high (>3px) or the camera was never calibrated → warning / turn 3D off

> **What the board does — and doesn't:**
> - ✅ Gives the floor / 6DoF transform, and today also **real-world scale** (mm). For this, the board
>   must be visible **in the patient clip** (it's how we find the floor).
> - ❌ Does **not** help the 3D lift. MotionBERT never sees the board — it's used only *after* lifting,
>   to add scale. (Joint *angles* are scale-free, so they don't need the board either.)
> - Camera **focal length** comes from a *separate* calibration clip, not the patient clip.
> - In short: **patient-clip board = where the floor is (scale); calibration clip = focal length.**

### 4.2 Lifting 2D → 3D

Files: [lifting/pipeline.py](app/services/lifting/pipeline.py) + [lifting/lifter.py](app/services/lifting/lifter.py)

1. `sequence_to_arrays`: convert to a dense array (T,26,2) + fill empty frames with the nearest frame + a mask
2. `halpe26_to_h36m17`: convert the skeleton from 26 points (RTMPose) → 17 points (H36M, which MotionBERT expects)
3. `normalize_screen_coordinates`: normalize the pixel coordinates
4. `MotionBertAdapter.lift`: ONNX inference → 3D (T,17,3), root-relative (no real-world units yet)
5. **Guard** `bone_length_consistency`: if bone lengths aren't consistent, the lift is garbage → discard, fall back to 2D

> `StubLifter` exists only to test the pipeline without weights — **do not use it for real results**.
> `validate_lifter_io` smoke-tests the ONNX I/O shapes at startup to prevent "silently wrong" output.

### 4.3 Metric Scale — Giving the 3D Real Units (mm)

File: [lifting/metric_scale.py](app/services/lifting/metric_scale.py)

The 3D output is unitless, so we need to find **mm per 1 unit**:
- **Primary (`feet_floor`)**: cast a ray from the left/right ankle pixels down to the floor plane → get a real
  distance, and compare it to the same distance in the skeleton
- **Fallback (`subject_height`)**: scale so that the head-to-foot distance equals the height the patient
  entered (`subject_height_mm`)
- If both are available and they differ by >15% → warning `scale_uncertain`

> Planned (work item A in [08-scope-v2.md](08-scope-v2.md)): a hospital-measured **bone length**
> (known femur mm ÷ lifted femur units, per side) becomes the primary source, ahead of both paths
> above. It needs no board and no floor plane.

### 4.4 3D Angles + 6DoF Transform

- `angle_series_3d`: compute joint angles from the 3D skeleton (for supported tasks) → placed in
  `joint_angles_3d` (keys ending in `_3d`)
- `camera_to_floor_6dof`: the matrix that transforms coordinates from the camera frame → the floor frame
  (placed in `transformation_matrix_6dof`)
- The ankle task still uses the 2D angle even when calibration succeeds (`supports_3d_angle` = false)

### 4.5 Muscle Overlay (display only)

The 3D viewer can overlay the major lower-limb muscles (`app/services/lifting/muscles.py` →
`pose_3d` payload → `viewer3d.js`). It shows muscle **length/geometry**, never force.

- **Why not force:** a single camera has no ground-reaction force, so muscle force/activation is not
  computable — full stop. Length and *strain* (ΔL/L₀), though, are purely kinematic, so those we can
  show.
- **Shape vs colour:** each muscle is routed through *anchors* (a fraction along a bone), so it bends
  with the limb; colour is a per-frame length proxy (contracted → stretched) from the joint angle.
- **Anatomy source:** anchor placement comes from a built-in approximation, or from the OpenSim
  **gait2392** model when `models/target/gait2392_muscles.json` is present. Produce that file (offline, no
  OpenSim runtime) by downloading a gait2392 `.osim` yourself and running:
  ```powershell
  uv run python -m app.tools.extract_gait2392_muscles --osim models/target/gait2392_simbody.osim
  ```

**Limitations (read before trusting it):**
- gait2392 gives anatomically-real *paths*, but its muscles depend on full 3D, multi-DOF kinematics.
  A single-camera 17-joint lift reliably observes only **sagittal hip/knee flexion** — so the quad and
  hamstring length reads are reasonable; anything driven by rotation, ab/adduction, or the foot is
  under-observed and only indicative.
- This is therefore a **kinematic length estimate, not a validated gait2392 simulation.** The overlay
  is labeled as such in the UI; do not present it as measured muscle mechanics.

**Opinion:** the honest, useful version of this feature is exactly this — sagittal-plane length/strain
of the flexion/extension muscles, gait2392 for geometry, clearly labeled. Going further (true muscle
force/load) needs a force plate and is out of scope for a single camera, no model can fix that.

### 4.6 When 3D falls back to 2D

The result is **always valid 2D**; metric 3D only turns on when everything lines up. It stays 2D if
**any** of these is true:

- 3D disabled, or the MotionBERT weights fail the startup guard
- **No ChArUco board detected** in the patient clip
- **Camera not calibrated / resolution mismatch** — the device id includes the video resolution, so a
  clip at a different resolution reads as "not calibrated"
- Calibration clip was a different resolution/orientation (intrinsics "stale")
- Task is **ankle** (no toe joint in the 17-joint skeleton)
- No usable leg found
- **Lift flagged unreliable** — bone lengths jitter too much (a noisy monocular lift)
- Any error in the 3D step (caught → 2D)

> A missing/uncertain **scale** is only a *warning*, not a rollback — the 3D angles still compute. And
> the display 3D skeleton (+ muscle overlay) can still render even while the clinical mode is 2D.

---

## 5. Response Structure (Output)

Files: [response_mapper.py](app/services/response_mapper.py), [schemas/response.py](app/schemas/response.py)

```jsonc
{
  "session_id": "rtmpose-<uuid>",
  "video_metadata": {
    "duration_sec", "fps", "view", "task_type",
    "processed_frames", "sampled_fps", "analyzed_side"
  },
  "clinical_metrics": {
    "joint_angles":     { "<task>_max_deg", "<task>_min_deg", "<task>_rom_deg" },  // 2D
    "joint_angles_3d":  { "..._3d": ... },      // empty if 3D did not run
    "scale_mm_per_unit", "scale_source",        // null if there is no scale
    "pose_quality": { "mean_keypoint_confidence", "valid_frame_ratio", "occlusion_warning" }
  },
  "screening_result": { "risk_level", "confidence_score", "flags": [] },
  "transformation_matrix_6dof": {...} | null,
  "analysis_mode": "2d" | "3d",         // which mode actually finished
  "board_diagnostics": {...} | null,    // result of looking for the ChArUco board
  "guard_warnings": []                  // various warnings (scale, lift, reproj)
}
```

**Point to remember:** `analysis_mode` tells you the **actual result** you got (2d/3d). Even with
`ENABLE_3D=true`, if the board/calibration/guard doesn't pass, you get `"2d"`, and `guard_warnings`
explains why.

---

## 6. Important Config (env)

See [app/core/config.py](app/core/config.py) and `.env.example`

| Variable | Effect on the pipeline |
|----------|------------------------|
| `FAKE_MODE` | skip all models, return fake results |
| `ENABLE_3D` | enable the 3D path (still needs weights + calibration) |
| `MOTIONBERT_MODEL_PATH` | the lifter's ONNX file |
| `DEVICE` | `cpu` / `cuda:0` / `auto` |
| `FRAME_SAMPLE_FPS` | reduce the number of frames processed |
| `MIN_KEYPOINT_CONFIDENCE` | threshold for dropping low-confidence points |
| `SMOOTHING_ALPHA` | the EMA smoothing factor |
| `MIN_VALID_FRAME_RATIO` | the quality-flag threshold |
| `SERVICE_API_KEY` | key for internal auth |

---

## 7. Quick Recap to Remember

1. **Two passes**: pass 1 collects 2D for the whole video (+ the annotated video), pass 2 lifts to 3D in one step
2. **2D always runs, 3D is a bonus** that degrades cleanly — it never crashes because of 3D
3. **The core of the data** is `PoseSequence` (a single person's 2D pose per frame) → everything builds on it
4. **Screening** produces risk/confidence/flags from ROM + pose quality
5. **The contract is always the same 5 keys** — the backend/doctor can rely on it

Files worth reading side by side: [video_analysis.py](app/services/video_analysis.py) (the orchestrator) and this document.
