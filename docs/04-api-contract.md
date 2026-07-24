# API Contract

## `POST /api/movement/assess`

Header:

- `X-Internal-Service-Key`: must match `SERVICE_API_KEY` using constant-time comparison.

Multipart form fields:

- `patient_id`: string
- `task_type`: one of `hip_flexion`, `hip_extension`, `knee_flexion`, `knee_extension`, `ankle_dorsiflexion`, `ankle_plantarflexion`
- `view`: `frontal` or `lateral`; unknown values are treated as `frontal` and logged
- `file`: uploaded video

Success response must include five top-level keys:

- `session_id`
- `video_metadata`
- `clinical_metrics`
- `screening_result`
- `transformation_matrix_6dof`

`confidence_score` and `pose_quality.mean_keypoint_confidence` are fractions from 0 to 1.

This is a scoped subset of the schema defined in `docs/Project101_Team5.md` (the Team 5 project
proposal's master doctor-facing output spec). Of the schema's fields, `joint_angles`, `pose_quality`,
`smoothness`, and `symmetry_index_score` are populated today; `gait_parameters` (needs a walking task
plus foot-contact detection) and `compensation` (multi-joint) remain empty by design.
`transformation_matrix_6dof` carries a real camera→floor transform when the optional ChArUco
calibration succeeds.

`joint_angles` uses **side-prefixed keys** (`left_knee_rom_deg`, `right_knee_rom_deg`, …) because both
legs are analyzed on every clip; the type is still `dict[str, float]`, so the contract shape is
unchanged. `symmetry_index_score` is `None` unless both legs actually moved.

Additive fields beyond the five required keys: `analysis_mode`, `clinical_metrics.joint_angles_3d` /
`scale_mm_per_unit` / `scale_source`, `board_diagnostics`, and `guard_warnings`. The request also
accepts optional `subject_height_mm`, `device_make`, and `device_model`.

## `GET /health`

Returns:

```json
{ "status": "ok", "device": "cuda:0", "model_backend": "rtmlib", "model_loaded": true }
```

The `device` and `model_loaded` values reflect runtime state.
