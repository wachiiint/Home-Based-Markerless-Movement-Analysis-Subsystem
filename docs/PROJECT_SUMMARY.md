# Home-Based Markerless Movement Analysis — Project Summary
Create date: 23 Jul 2026

*A single consolidated document (README + docs 01–07) for review.*

> **Version 1 is a local decision-support / demo service. It is not a clinical diagnosis
> system, and should not be exposed directly to the public internet.**

---

## 1. What this project is

A local **FastAPI** service for **markerless movement analysis**. A patient records a short
phone video of a leg movement (e.g. a seated knee extension); the service returns a JSON
assessment — joint angles, range of motion (ROM), pose quality, and a risk-screening result —
plus an annotated skeleton video and an optional 3D viewer.

It is built as a drop-in replacement for an existing MediaPipe-based analysis service, so it
returns the **same JSON contract** the main backend already expects.

### Where it fits in the bigger system

This service is **one microservice**. It never talks to the patient directly — the main
backend calls it server-to-server.

```
Patient (frontend) ──upload video──▶ Main backend
                                        │  (stores the session, calls this service
                                        │   via MEDIAPIPE_SERVICE_URL)
                                        ▼
                          Movement Analysis Service  ◀── (this repo)
                                        │  (returns assessment JSON)
                                        ▼
                                     Backend stores the result
                                        ▼
                        Doctor dashboard (reads risk_level, ROM, quality)
```

### Vision / north star (beyond v1)

The screening numbers are the foundation; the intended *differentiators* are visual and
longitudinal:

1. **3D movement viewer (Three.js)** — let a doctor *see* the movement pattern in 3D, not
   just read numbers. Already prototyped (display-only).
2. **Muscle overlay** — overlay lower-limb muscle geometry on the motion, connecting *how the
   patient moves* to *the underlying muscle*.
3. **Before/after comparison** — compare two sessions of one patient to visualise rehab
   progress over time (roadmap).

---

## 2. Key terms (glossary)

| Term | Meaning |
|------|---------|
| **Pose estimation** | Finding body-joint (keypoint) locations in an image. RTMPose does this per frame. |
| **Keypoints** | Detected joint positions (hip, knee, ankle…). Uses the 26-point "Halpe26" set. |
| **ROM (Range of Motion)** | How far a joint moves — max minus min angle across the video. |
| **Screening** | Turning measured angles + pose quality into a `risk_level` (low/moderate/high) + confidence. |
| **3D lifting** | Estimating a 3D pose from the 2D pose (MotionBERT). Off by default, best-effort. |
| **ChArUco board** | A printed calibration pattern. When visible, it recovers real-world scale (mm) + the floor plane. |

---

## 3. How the pipeline works

> **TL;DR:** patient records a video → service runs 2D pose estimation frame by frame →
> computes joint angles + ROM → screens for risk → (if a calibration board is present) lifts
> the pose to 3D → returns a fixed JSON contract for the doctor.

### 3.1 End-to-end flow

```
[1] Request comes in       validate service key, validate video, normalize view
[2] Save a temporary file
[3] Analyze the video      ◀── the heart of the pipeline
       ├─ Pass 1: 2D pose for every frame + write the annotated video
       ├─ Compute 2D angles + ROM + risk screening
       └─ Pass 2 (optional): lift to 3D if calibration is available
[4] Assemble the response
[5] Return JSON + delete the temporary file
```

### 3.2 Data transformation (pixels → risk level)

```
Video (mp4)  →  sampled frames  →  RTMPose keypoints (N people × 26 pts)
   →  select main subject  →  PoseSequence (one person's 2D pose per frame)  ◀── central structure
        ├── 2D path (always runs): pick side → per-frame angle → smoothing → ROM → screening
        └── 3D path (optional): 26→17 skeleton → normalize → MotionBERT lift (T,17,3)
                → bone-length guard → 3D angles + metric scale
```

**Why two passes?** MotionBERT needs the **entire sequence** at once, so we collect the whole
2D sequence first, then lift to 3D in one step.

### 3.3 Angle computation & screening (2D)

- Each task (e.g. `knee_flexion`) defines 3 points: a vertex + 2 rays (knee = hip–knee–ankle).
- `three_point_angle` gives the angle per frame; low-confidence frames are dropped.
- Smoothing (EMA) → ROM (min/max) → risk screening:

```
if valid_frame_ratio low  → flag "low_valid_frame_ratio"
if mean confidence low     → flag "low_keypoint_confidence"

risk = high      if any flag set, or ROM < borderline
     = moderate  if ROM < expected
     = low       otherwise

confidence_score = 0.5*valid_frame_ratio + 0.5*mean_confidence   (0..1)
```

### 3.4 The 3D path (optional, best-effort — never crashes the request)

- **Calibration (per session):** a printed **ChArUco board** in the patient clip recovers the
  **floor plane** and real-world scale. **What the board does — and doesn't:**
  - ✅ Gives **real-world scale (mm)** + the floor / 6DoF transform.
  - ❌ Does **not** help the 3D lift — MotionBERT never sees the board; it's used only *after*
    lifting, to add scale. (Joint *angles* are scale-free, so they don't need the board either.)
  - Camera **focal length** comes from a *separate* one-time calibration clip per device.
- **Lifting:** convert 26→17 skeleton → normalize → MotionBERT ONNX → 3D (root-relative). A
  bone-length consistency guard discards a garbage lift and falls back to 2D.
- **Metric scale (mm per unit):** primary = back-project ankle pixels to the floor plane;
  fallback = scale so head-to-foot equals the patient's entered height. If both disagree by
  >15%, a `scale_uncertain` warning is raised (angles stay valid regardless).
- **3D angles + 6DoF transform** are added; the ankle task stays 2D (no toe joint in 17-point
  skeleton).

**When 3D falls back to 2D** — the result is *always* valid 2D; it stays 2D if any of these
hold: 3D disabled or weights fail the startup guard; no board detected; camera not calibrated
/ resolution mismatch; stale intrinsics; ankle task; no usable leg; lift flagged unreliable;
or any error in the 3D step. A missing/uncertain *scale* is only a warning, not a rollback.

### 3.5 Muscle overlay (display only)

The 3D viewer can overlay major lower-limb muscles (quadriceps, hamstrings, gastrocnemius,
iliopsoas, gluteals). It shows muscle **length/geometry**, never force.

- **Why not force:** a single camera has no ground-reaction force, so muscle force/activation
  is not computable — full stop. Length and *strain* (ΔL/L₀) are purely kinematic, so those we
  can show.
- **Anatomy source:** anchor placement comes from a built-in approximation, or from the
  OpenSim **gait2392** model when its extracted geometry file is present.
- **Limitation:** a single-camera 17-joint lift reliably observes only **sagittal hip/knee
  flexion**, so the quad/hamstring reads are reasonable but anything driven by rotation,
  ab/adduction, or the foot is under-observed. This is a **kinematic length estimate, not a
  validated gait2392 simulation**, and is labelled as such in the UI.

---

## 4. API contract

### `POST /api/movement/assess`

- **Header:** `X-Internal-Service-Key` (constant-time compared to `SERVICE_API_KEY`).
- **Multipart fields:** `patient_id`; `task_type` (one of `hip_flexion`, `hip_extension`,
  `knee_flexion`, `knee_extension`, `ankle_dorsiflexion`, `ankle_plantarflexion`); `view`
  (`frontal`/`lateral`, unknown → `frontal`); `file` (video).

**Success response — always 5 top-level keys:**

```jsonc
{
  "session_id": "rtmpose-<uuid>",
  "video_metadata":  { "duration_sec", "fps", "view", "task_type",
                       "processed_frames", "sampled_fps", "analyzed_side" },
  "clinical_metrics": {
    "joint_angles":     { "<task>_max_deg", "<task>_min_deg", "<task>_rom_deg" },  // 2D
    "joint_angles_3d":  { "..._3d": ... },       // empty if 3D did not run
    "scale_mm_per_unit", "scale_source",         // null if no scale
    "pose_quality": { "mean_keypoint_confidence", "valid_frame_ratio", "occlusion_warning" }
  },
  "screening_result": { "risk_level", "confidence_score", "flags": [] },
  "transformation_matrix_6dof": {...} | null,
  "analysis_mode": "2d" | "3d",         // which mode actually finished
  "board_diagnostics": {...} | null,
  "guard_warnings": []
}
```

`confidence_score` and `mean_keypoint_confidence` are fractions 0–1. `analysis_mode` tells you
the *actual* result: even with `ENABLE_3D=true`, if calibration/guards don't pass you get
`"2d"` and `guard_warnings` explains why.

This is a scoped subset of the master doctor-facing schema (`docs/Project101_Team5.md`). The
response already includes `gait_parameters`, `compensation`, `smoothness`, and
`symmetry_index_score` placeholders to match that schema.

### `GET /health`

```json
{ "status": "ok", "device": "cuda:0", "model_backend": "rtmlib", "model_loaded": true }
```

---

## 5. Getting started (developer)

**Prerequisites:** Python 3.11+, [uv](https://github.com/astral-sh/uv), any OS (commands shown
for PowerShell). GPU optional — runs on CPU by default.

```powershell
uv sync
Copy-Item .env.example .env
uv run python -m app          # port via $env:PORT (default 8000)
```

Open the demo at http://127.0.0.1:8000/, or check `Invoke-RestMethod http://127.0.0.1:8000/health`.

> Use `uv run python -m app` (not plain `uvicorn`): the runner bounds uvicorn's graceful-shutdown
> wait so **Ctrl+C actually stops the server** on Windows. If you run uvicorn directly, add
> `--timeout-graceful-shutdown 5`.

**Key config (`.env`):**

| Variable | What it does |
|----------|--------------|
| `FAKE_MODE` | `true` = skip the ML model, return valid fake data (great first run). `false` = real inference. |
| `SERVICE_API_KEY` | Internal server-to-server key (default `dev-local-analysis-key`, never sent to a browser). |
| `DEVICE` | `auto` (default) / `cpu` / `cuda:0`. |
| `ENABLE_3D` | Turn on the optional 2D→3D lifting path (off by default). |

With `FAKE_MODE=false`, the first startup downloads RTMPose/YOLOX ONNX models; later startups
reuse the cache. GPU needs `onnxruntime-gpu` (not the default CPU-only `onnxruntime`) plus a
version-matched CUDA + cuDNN runtime.

**Enabling 3D** is a one-time *download → export → enable* you run yourself (MotionBERT
publishes PyTorch weights, not ONNX; export lives under `models/`). At startup the export is
smoke-tested with `validate_lifter_io()` — a bad export is *rejected* and the service falls
back to 2D rather than producing silent garbage.

---

## 6. Demo user guide (which video to upload)

| Video | Panel | Required? | What it is |
|-------|-------|-----------|------------|
| **Movement video** | **01 / INPUT** | **Always** | The patient performing the exercise, filmed from the side. |
| **Calibration video** | **00 / CALIBRATION** | **Optional** | A short clip of the printed ChArUco **board** at different angles, **no patient**. Only unlocks millimetre-accurate 3D. |

> **If unsure: just upload the movement video in Panel 01 and press Analyze.** You do *not* need
> calibration to get angles, ROM, screening, smoothness, left/right symmetry, the annotated
> video, or the 3D skeleton + muscle overlay. Calibration only adds real-world **millimetre**
> measurements.

**What you get without calibration:**
- **Panel 02** — your video with the detected skeleton drawn on it (+ download link).
- **Panel 03** — screening risk (driven by the **worse** leg, side-tagged flags), confidence,
  valid-frame ratio, and a **Left vs Right table** of angles/ROM for both legs, plus smoothness
  and a left/right asymmetry index (when both legs moved).
- **Panel 04** — a rotatable 3D pose; a **Muscles** toggle overlays the kinematic muscle-length
  proxy; a **Preview 3D (sample data)** button shows the viewer with no upload.

**Unlocking millimetre 3D (calibration, one-time per camera + resolution):** print the ChArUco
A4 board at 100%, measure the printed 100 mm reference bar, film the board held at several
angles at the **same resolution as your patient clips** (1080p recommended), and calibrate in
Panel 00. **Resolution must match** between calibration and patient clips or the demo warns and
falls back to 2D.

**Recording tips:** one person in frame, whole exercising leg visible throughout; film side-on
(lateral) for knee/hip flexion & extension; steady camera, even lighting, plain background;
move slowly through the full range.

---

## 7. Evaluation & validation

**Tests:** auth rejects missing/wrong keys; API contract returns the 5 keys in `FAKE_MODE`;
unknown task → 400; unreadable video → 422; response mapper emits the documented shape;
kinematics returns known 3-point angles and ROM.

**Acceptance:** runs locally without GPU; uses `cuda:0` when available; `/health` reports device
+ model state; `FAKE_MODE` supports backend integration without ML dependencies.

### Literature-informed validation risks

Reviewed against six papers on smartphone/webcam movement assessment, pose-estimation accuracy,
real-time musculoskeletal simulation, and Hill-type muscle-model instability:

- **Raw 2D joint angles carry systematic, joint-specific bias.** Uncorrected pose angles showed
  RMSE 7.3–15.7° vs. Vicon; error fell below the ~6° clinical bar only after a per-joint,
  per-movement regression correction. This service computes angles directly with no such
  correction yet.
- **ROM peak detection is least reliable at end-of-range**, where the angle trajectory flattens
  near maximal flexion (self-occlusion) — exactly where `range_of_motion` and the risk boundary
  operate.
- **No empirical reliability/validation pipeline exists yet.** Defending
  `expected_rom_deg`/`borderline_rom_deg` empirically (test-retest ICC → correlate against a
  clinical reference → validate on a held-out cohort) is future work.
- **Camera view/orientation is joint-specific** — accuracy depends on sagittal vs coronal view
  and clothing contrast; the demo should steer patients into the validated orientation per task.
- **Muscle force / Hill-type modelling is correctly out of v1 scope** (documented numerical
  instability, no validated eccentric model — open research, not solved engineering).
- **The overall single-camera approach is validated elsewhere** (moderate-to-strong correlation
  with clinical reference tests), so the architecture is sound; the gap is specifically the
  raw-angle correction and empirical threshold validation.

---

## 8. Build phases (history)

- **Phase 1 — Scaffold & docs:** repo structure, documentation, env example, dependencies.
- **Phase 2 — API-compatible skeleton:** FastAPI startup, `/health`, `/api/movement/assess`,
  API-key auth, multipart parsing, task/view validation, response models, `FAKE_MODE`.
- **Phase 3 — Video & RTMPose inference:** video decode, metadata, frame subsampling, model
  loading, rtmlib inference, subject selection, CPU fallback.
- **Phase 4 — Quality & biomechanics MVP:** quality metrics, smoothing, kinematics, ROM
  aggregation, screening rules, temp-file cleanup.

Subsequent work (single-camera 3D groundwork, ChArUco calibration, MotionBERT lifting, both-leg
reporting, muscle overlay) is tracked in `AGENTS.md`.
