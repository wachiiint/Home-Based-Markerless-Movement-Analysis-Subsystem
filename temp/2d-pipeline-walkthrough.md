# 2D Pipeline Walkthrough (worked example)

A study note tracing one real request end-to-end, kept in `temp/` (tracked so the team can read it;
will be removed at full launch). Example request:

```
task_type=knee_flexion  view=lateral  file=knee_flex_nocalib.mp4   (FAKE_MODE=false, CPU)
```

Result it produced: left knee, min 84.66°, max 177.43°, ROM 92.77°, mean conf 0.78,
valid_frame_ratio 1.0, risk "low", confidence 0.89, analysis_mode "2d".

---

## The lap, step by step

### 0. Entry — `app/main.py:142` `assess_movement()`
1. Normalize `view` (`main.py:150`) — unknown → `"frontal"`. Yours was valid `"lateral"`.
2. `validate_video_upload()` (`video_io.py:9`) — reads first 16 bytes, just checks "not empty".
3. `FAKE_MODE` false → `_run_real_analysis()` (`main.py:93`), which `save_upload()`s to a temp dir
   (`video_io.py:16`) then calls the orchestrator.

### 1. Orchestrator — `analyze_video()` (`video_analysis.py:207`)
- `read_video_metadata()` (`video_io.py:36`): fps/size/frame count → `duration_sec 15.04`
  (= 451 frames / 30 fps).
- `lifter is None` (3D off) ⇒ `calibrator is None` ⇒ no board detection.

### 2. Pass 1 — collect 2D poses (`_collect_pose_sequence`, `video_analysis.py:53`)
The frame loop:
- **Subsample** (`:66`): `sample_interval = round(30/10) = 3` → keep every 3rd frame → **151**
  processed frames.
- **Infer** (`:79`): `estimator.infer(frame)` → keypoints + scores for everyone in frame.
- **Pick person** (`:80`): `select_main_subject()` = `max(mean score)` — no tracking.
- **Annotate + store** (`:87`, `:94`): draw skeleton to `annotated.mp4`; append `FramePose2D`
  (`None` keypoints if nobody detected, so the timeline stays aligned).
- Returns `PoseSequence` — the central data structure.

### 3. Poses → angles (loop at `video_analysis.py:218`)
- **Choose side once** (`:222`): first usable frame → `_choose_side()` (`:42`) compares both legs'
  mean joint confidence, keeps the better. Picked `left`, then **locked for the whole clip**.
- **Angle per frame** (`_angle_for_frame`, `:32`): task's 3 joints from `TASK_CONFIGS[knee_flexion]`
  (`task_config.py:22` → vertex=knee, rays=hip+ankle). If any of the 3 scores < 0.4
  (`MIN_KEYPOINT_CONFIDENCE`) → drop frame.
- **Math** (`analysis/kinematics.py:4` → `math_utils.py:4`): `angle_degrees(hip, knee, ankle)` via `atan2`,
  folded to ≤180°. **180° = straight leg, smaller = more bent.**
- **Confidence sample** (`:229`): mean of **all 26** keypoint scores (not just the leg).

### 4. Reduce to metrics
- **Smooth** (`analysis/smoothing.py:1`): EMA, `0.4*new + 0.6*prev`.
- **ROM** (`analysis/kinematics.py:12`): `min`, `max`, `max-min` → `84.66 / 177.43 / 92.77`.
- **Quality** (`:235`): `valid_frame_ratio = valid_frames / processed_frames` = 1.0.

### 5. Screening (`screen_rom`, `analysis/screening.py:1`)
```
valid_frame_ratio 1.0 < 0.6?   no  -> no flag
mean_conf 0.78 < 0.5?          no  -> no flag
rom 92.77 < borderline 40?     no
rom 92.77 < expected 60?       no  -> risk "low"
confidence = 0.5*1.0 + 0.5*0.78 = 0.89
```
Thresholds `expected 60 / borderline 40` from `task_config.py:22`.

### 6. 3D augmentation no-ops (`_augment_with_3d`, `video_analysis.py:122`)
`if lifter is None: return result` (`:137`) → default `_ThreeDResult(analysis_mode="2d")`, all 3D
fields empty. Whole method is `try/except` (`:190`) so 3D can never break 2D.

### 7. Assemble + return (`build_assessment_response`, `response_mapper.py:16`)
Packs the fixed schema. `occlusion_warning = valid_frame_ratio < 0.8` (`:71`). Back in `main.py:163`
temp dir deleted, JSON returned.

**Full lap:** `main → save → analyze_video → [Pass1 infer → per-frame angle → smooth → ROM →
screen] → 3D no-op → response`.

---

## Observed simplifications (potential future work — not bugs)

1. **Side is chosen from one frame and locked** (`video_analysis.py:222`). A noisy first usable
   frame fixes the wrong/less-reliable leg for the whole clip.
2. **No subject tracking** (`pose/subject_selector.py`). Main subject = highest *mean* confidence per
   frame independently, so a clearer bystander can hijack it and the "main person" can flip between
   frames. (A near-empty `pose/tracking.py` stub used to sit here; it was deleted as dead code —
   the idea is still open work, just no longer a half-file.)
3. **`mean_keypoint_confidence` averages all 26 joints** (`video_analysis.py:229`), including
   face/arms, so it under-reports how confident the *leg* joints (the ones actually measured) were.
4. **Screening is rule-based** (`analysis/screening.py`), and the per-task thresholds in `task_config.py` are
   set by convention, not empirically validated. Raw 2D angles also have known joint-specific bias
   with no correction step. See `docs/05-evaluation-plan.md` "Literature-Informed Validation Risks".
5. **`occlusion_warning` implementation is a crude proxy** (`response_mapper.py:71`): it is purely
   `valid_frame_ratio < 0.8`, unrelated to actual occlusion detection, and its hardcoded `0.8`
   is *inconsistent* with the configurable `min_valid_frame_ratio` (default 0.6) used for the
   quality flag — two different thresholds on the same ratio. **Note:** the field *name* cannot be
   changed — it is part of the master contract (`Project101_Team5.md:134`) and the MediaPipe-compatible
   response, so any rename is a coordinated cross-repo contract change. The *implementation* can be
   improved behind the contract. (A duplicate `services/analysis/quality.py::compute_pose_quality`
   was found unused and has since been deleted; the live path computes this inline in the mapper.)
6. **`confidence_score` is a fixed 50/50 blend** (`analysis/screening.py:23`) of frame ratio and mean
   confidence — arbitrary weights. (Scheduled to change in P0 of `docs/08-scope-v2.md` to
   0.40/0.40/0.20 with a new `tracking_stability_score` term.)
7. **ROM = raw `max - min`** (`analysis/kinematics.py:12`) over the series — a single outlier frame
   (one spurious max or min) directly inflates ROM; no robust/percentile bounds.
8. **EMA smoothing is causal** (`analysis/smoothing.py`), so it lags the signal. Fine for min/max magnitude,
   but shifts *when* peaks occur.

---

## Q&A notes

**Q1 — Screening flags are rule-based; should the end goal be an ML model?**
**Decision: keep it rule-based** (to be confirmed with the doctor). Currently pure threshold rules
(`analysis/screening.py:11-21`). The evaluation plan's literature review points toward an *empirical* path
(filter metrics by test-retest ICC → correlate to a clinical reference → regularized model →
validate on held-out cohort) rather than a black-box classifier. For a *decision-support* tool
(not diagnosis), rule-based is a feature: transparent and explainable to a clinician. If anything is
added later it would most likely (a) correct raw-angle bias before screening and (b) replace
convention thresholds with validated ones — not a full ML risk classifier. Source of truth is
`docs/Project101_Team5.md`.

**Q2 — Is `occlusion_warning = valid_frame_ratio < 0.8` okay?**
**Decision: do NOT rename the field.** It is part of the master contract (`Project101_Team5.md:134`)
and the MediaPipe-compatible response, so a rename is a coordinated cross-repo change, not a local
one. The name itself is fine (occlusion/visibility is a MediaPipe concept). The *implementation* is
the weak part: it just means "too many unusable frames" (which can be occlusion, but also
out-of-frame, blur, low light, or no person), and its `0.8` disagrees with the configurable `0.6`
flag threshold. Improve behind the contract if desired (real per-joint visibility, single shared
threshold); leave the field name and shape alone.

**Q3 — Does the 3D path feed the screening / risk level?**
**No.** `risk_level`, `confidence_score`, and `flags` are computed entirely from the **2D** angle +
ROM (`video_analysis.py:233-245`), *before* `_augment_with_3d` runs. 3D is purely additive: it fills
the `_3d` metric fields and can flip `analysis_mode` to `"3d"`, but the risk assessment never
changes because of it. Even in `"3d"` mode, `risk_level` still derives from the 2D angle.

---

# 3D Lifting Walkthrough (the path that forks from 2D)

**Key model:** 2D always finishes first. Angles, ROM, and `risk_level` are computed from 2D pixels
(`video_analysis.py:233-245`) *before* 3D is attempted. 3D is **additive** — it fills the `_3d`
fields and may flip `analysis_mode`, but does **not** feed screening (see Q3).

The fork is one call: `_augment_with_3d()` (`video_analysis.py:248` → `:122`). When it fully runs
(`ENABLE_3D=true`, weights loaded, board present):

### Gate 0 — does 3D even start? (`video_analysis.py:137`)
`if lifter is None: return 2d`. The lifter exists only if, at startup, `build_lifter()`
(`lifter.py:127`) found the weights **and** passed `validate_lifter_io()` — a smoke test rejecting
any ONNX export whose output isn't `(T,17,3)` and finite. Fail-closed.

### Step A — Calibration (`:141`, `calibrator.finalize()`)
Recovers camera intrinsics + floor plane from the ChArUco board, builds `transformation_matrix_6dof`
(`camera_to_floor_6dof`). Sets `metric_possible = calibration.ok AND supports_3d_angle(task) AND
side`. If nothing needs 3D (`not (want_pose_3d or metric_possible)`) it bails to 2D here (`:154`).

### Step B — The lift (`lift_pose_sequence`, `pipeline.py:52`)
Takes the *same* `PoseSequence` the 2D path used, through four stages:
1. `sequence_to_arrays` (`pipeline.py:26`): dense `(T,26,2)`; **fills gaps** (frames with no subject
   get the nearest valid pose) so the lifter sees a continuous sequence; `valid_mask` records which
   frames were real.
2. `halpe26_to_h36m17` (`skeleton_convert.py:58`): remap 26 → 17-joint H36M layout (MotionBERT's
   training format). All joints map directly except mid-spine (H36M 7), **synthesised** as the
   pelvis–neck midpoint.
3. `crop_scale` (`normalize.py:18`): normalize to the **subject's bounding box** `[-1,1]`, *not* the
   image. (Docstring: image-normalization compresses predicted depth ~3× unless the subject fills
   the frame — a real correctness subtlety.)
4. `lifter.lift` (`lifter.py:85`): MotionBERT ONNX → `(T,17,3)` **root-relative** 3D (unitless).
   Clips longer than 243 frames (model's fixed temporal window) run a **sliding window with
   Hann-tapered blending** at the seams.

### Step C — Guard the lift (`bone_length_consistency`, `guards.py:21`)
A correct lift keeps femur/tibia lengths ~constant over time. Measures each bone's coefficient of
variation; if any exceeds `0.25`, the lift is garbage (`lift_ok=False`) → degrade to 2D. Catches
"silently wrong" depth that a shape check alone cannot.

### Step D — Metric angles + scale (only if `metric_possible and lift_ok`, `:161`)
- `angle_series_3d` (`angles_3d.py:33`): recomputes the joint angle in 3D via the **dot-product**
  form (`three_point_angle_3d` → `math_utils.py:14`), not `atan2` — generalises to 3D. → smooth →
  ROM → `joint_angles_3d` (keys suffixed `_3d`).
- `resolve_metric_scale` (`metric_scale.py`): **mm-per-unit** — primary from casting ankle rays to
  the floor plane, fallback from the patient's entered height.
- Sets `analysis_mode = "3d"`.
- **Ankle stays 2D even here**: `supports_3d_angle()` (`angles_3d.py:22`) is false for ankle tasks
  because H36M17 has no toe joint (ankle angle needs `big_toe`).

### Step E — Demo viewer payload (`if want_pose_3d`, `:179`)
`build_pose3d_payload` for the Three.js skeleton. Built **even if the bone guard failed**, but
flagged `lift_reliable=false` so the viewer warns. "It's a picture, not a clinical number."

### Fallbacks
Whole method is wrapped in `try/except` (`:190`) that resets to `"2d"` on any exception. Combined
with Gate 0, `metric_possible`, and the bone guard, there are **four** independent points that fall
back to 2D — which is why a normal run (no board) returns 2D cleanly with no warnings.

**One-line contrast:** 2D = pixels → `atan2` angle → screen. 3D = same poses → fill gaps →
26→17 remap → bbox-normalize → neural lift → bone-guard → dot-product angle + metric scale, bolted
on *beside* the 2D result and guarded so it never breaks it.
