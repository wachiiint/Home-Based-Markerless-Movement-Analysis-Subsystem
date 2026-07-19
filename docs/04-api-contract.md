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
proposal's master doctor-facing output spec). The response shape (`app/schemas/response.py`)
already includes `gait_parameters`, `compensation`, `smoothness`, `symmetry_index_score`, and
`transformation_matrix_6dof` to match that schema, but these fields are empty/`None` in v1 — only
`joint_angles` and `pose_quality` are populated (see `05-evaluation-plan.md`).

## `GET /health`

Returns:

```json
{ "status": "ok", "device": "cuda:0", "model_backend": "rtmlib", "model_loaded": true }
```

The `device` and `model_loaded` values reflect runtime state.
