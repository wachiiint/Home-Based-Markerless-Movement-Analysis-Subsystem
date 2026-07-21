# Evaluation Plan

## Tests

- Auth rejects missing or wrong service keys.
- API contract returns the five required top-level keys in `FAKE_MODE`.
- Unknown task type returns `400`.
- Unreadable video returns `422`.
- Response mapper emits the documented nested shape.
- Kinematics returns known 3-point angles and ROM values.

## Acceptance

- Runs locally without GPU.
- Uses `cuda:0` when available and configured.
- `/health` reports selected device and model state.
- `FAKE_MODE` supports backend integration without ML dependencies.
- No MotionBERT, no 3D lifting, no gait or symmetry analysis in v1.

## Literature-Informed Validation Risks

Reviewed against `dump/paper/Lower-limb tele-assessment manuscripts/` (six papers on
smartphone/webcam movement assessment, pose-estimation accuracy, real-time musculoskeletal
simulation, and Hill-type muscle model instability). Findings relevant to this service's pipeline:

- **Raw 2D joint angles carry systematic, joint-specific bias.** DRome (BioRob 2024) found
  uncorrected MoveNet joint angles had RMSE 7.3-15.7° vs. Vicon; error only fell below the ~6°
  clinical-acceptability bar after fitting a per-joint, per-movement regression correction. This
  service's `app/services/kinematics.py::three_point_angle` computes angles directly from RTMPose
  keypoints with no such correction, and `screening.py::screen_rom` compares the raw value against
  fixed thresholds in `app/models/task_config.py`.
- **ROM peak detection is most unreliable at end-of-range.** The PLOS ONE BlazePose ROM study found
  inter-rater ICC as low as 0.18-0.64 (vs. mocap) for joints where the estimated angle trajectory
  flattens near maximal flexion (self-occlusion/limb overlap), even though the true angle keeps
  changing. `kinematics.py::range_of_motion` (`max - min` over the raw angle series) is exactly the
  operation most exposed to this, and it is precisely where `screen_rom` draws its risk boundary.
- **No empirical reliability/validation pipeline exists yet.** The NeuFun-TS (MS) paper's approach —
  filter candidate metrics by test-retest ICC, correlate survivors against a clinical reference,
  combine into a regularized model, validate on a held-out cohort — is a candidate template if
  `expected_rom_deg`/`borderline_rom_deg` in `task_config.py` are ever meant to be defended
  empirically rather than set by convention.
- **Camera view/orientation is joint-specific.** Multiple studies (DRome, PLOS ONE) show accuracy
  depends on whether the joint is viewed sagittally or coronally, and on clothing contrast; worth
  confirming the demo UI steers patients into the validated orientation per `task_type`.
- **Richer biomechanical modeling (muscle force, Hill-type models) is correctly out of v1 scope.**
  The Hill-type muscle model review documents unresolved numerical-instability problems (negative
  stiffness on the descending force-length limb, no validated eccentric-contraction model) that are
  still open research, not solved engineering — reinforcing the "no gait or symmetry analysis in
  v1" boundary above rather than arguing for adding muscle-force estimation.
- **The overall single-camera approach is validated elsewhere.** Halo Movement (Amazon) and the
  PLOS ONE BlazePose study both show home-usable, single-RGB-camera pose estimation can reach
  moderate-to-strong correlation with clinical reference tests, so the chosen architecture (camera
  -> pose model -> joint angles -> screening) is sound; the gap is specifically in the raw-angle
  correction and empirical threshold validation steps above.

See `docs/Project101_Team5.md` for the master clinical feature/output requirement (the doctor-facing
`clinical_metrics` schema this service's `app/schemas/response.py` already mirrors in shape).
 