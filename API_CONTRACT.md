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

## `GET /health`

Returns:

```json
{ "status": "ok", "device": "cuda:0", "model_backend": "rtmlib", "model_loaded": true }
```

The `device` and `model_loaded` values reflect runtime state.
