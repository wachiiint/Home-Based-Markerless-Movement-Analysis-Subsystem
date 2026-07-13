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
